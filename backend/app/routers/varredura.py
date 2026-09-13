"""A varredura diária: o que a rotina agendada lê e o resumo que ela manda.

## Quem chama

Uma rotina agendada do Claude, uma vez por dia (ver docs/varredura-diaria.md).
Ela revisa o código e as dependências, lê daqui os relatos e os erros do
servidor, grava tudo nas duas bases da página PathR no Notion e, por último,
pede aqui o e-mail de resumo.

## Por que o e-mail sai daqui, e não da rotina

A chave do Brevo fica no servidor. A rotina só manda os achados dela; os
números de relatos e de erros o servidor conta sozinho — um resumo que
dependesse da rotina para contar os relatos poderia dizer "0 relatos" num dia
em que ela falhou em lê-los.

## O segredo

`X-Pathr-Scan-Secret`, separado do segredo do disparo de avisos. Com ele se lê
os relatos das últimas horas SEM autor (nem nome, nem e-mail, nem @) e se
manda no máximo um e-mail por dia, e só para a moderação.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.services import email as emails
from app.services import erros

router = APIRouter(prefix="/jobs/varredura", tags=["operação"])

CABECALHO = "X-Pathr-Scan-Secret"
FUSO = ZoneInfo("America/Sao_Paulo")
# Um dia com folga para a rotina que atrasa, sem deixar buraco entre um dia e
# o seguinte. Um relato pode aparecer em dois resumos seguidos; nunca em nenhum.
JANELA_HORAS = 26


def _confere_segredo(request: Request) -> None:
    if not settings.scan_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Varredura desligada: SCAN_SECRET não está configurado.",
        )
    # compare_digest pelo mesmo motivo de routers/jobs.py: `==` vaza pelo tempo.
    if not secrets.compare_digest(request.headers.get(CABECALHO, ""), settings.scan_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Segredo inválido.")


def _desde(horas: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()


def _relatos(supabase: Client, horas: int) -> list[dict[str, Any]]:
    linhas = (
        supabase.table("pathr_report")
        .select("id,kind,message,page,status,attachment_path,created_at")
        .gte("created_at", _desde(horas))
        .order("created_at")
        .execute()
        .data
        or []
    )
    # Sem user_id, nome ou e-mail: o Notion não precisa saber quem relatou, e
    # o que não sai daqui não vaza de lá.
    return [
        {
            "id": str(linha["id"]),
            "tipo": linha.get("kind"),
            "mensagem": linha.get("message"),
            "pagina": linha.get("page"),
            "status": linha.get("status"),
            "tem_foto": bool(linha.get("attachment_path")),
            "criado_em": linha.get("created_at"),
        }
        for linha in linhas
    ]


def _erros(supabase: Client, horas: int) -> list[dict[str, Any]]:
    linhas = (
        supabase.table("pathr_error_event")
        .select("fingerprint,method,route,error_type,message,location,occurred_at")
        .gte("occurred_at", _desde(horas))
        .limit(5000)
        .execute()
        .data
        or []
    )
    return erros.agrupar(linhas)


@router.get("/dados")
def dados(
    request: Request,
    horas: int = Query(JANELA_HORAS, ge=1, le=24 * 7),
    supabase: Client = Depends(get_supabase),
):
    """Relatos e erros (agrupados por defeito) das últimas `horas`."""
    _confere_segredo(request)
    return {"horas": horas, "relatos": _relatos(supabase, horas), "erros": _erros(supabase, horas)}


Severidade = Literal["critico", "alto", "medio", "baixo"]
Categoria = Literal["bug", "vulnerabilidade", "sugestao"]


class Achado(BaseModel):
    categoria: Categoria
    severidade: Severidade = "medio"
    titulo: str = Field(min_length=3, max_length=200)


class Resumo(BaseModel):
    achados: list[Achado] = Field(default_factory=list, max_length=300)
    notion_url: str | None = None

    @field_validator("notion_url")
    @classmethod
    def _so_notion(cls, valor: str | None) -> str | None:
        # O endereço vira botão no e-mail da moderação. Aceitar qualquer URL
        # faria do resumo um jeito de mandar link arbitrário "em nome do PathR".
        if not valor:
            return None
        if not valor.startswith(("https://www.notion.so/", "https://notion.so/")):
            raise ValueError("notion_url precisa ser um endereço https do notion.so")
        return valor


def contar(achados: list[Achado], relatos: list[dict], grupos_de_erro: list[dict]) -> dict[str, Any]:
    """Os números do e-mail. Vulnerabilidade conta como bug (com a severidade
    dela) e aparece também em separado — é o que o resumo pede: "X bugs, X
    deles críticos…"."""
    problemas = [a for a in achados if a.categoria in ("bug", "vulnerabilidade")]
    return {
        "bugs": len(problemas),
        "vulnerabilidades": sum(1 for a in problemas if a.categoria == "vulnerabilidade"),
        "por_severidade": {
            s: sum(1 for a in problemas if a.severidade == s) for s in ("critico", "alto", "medio", "baixo")
        },
        "sugestoes": sum(1 for a in achados if a.categoria == "sugestao"),
        "erros": len(grupos_de_erro),
        "ocorrencias_de_erro": sum(int(g["ocorrencias"]) for g in grupos_de_erro),
        "relatos_bug": sum(1 for r in relatos if r["tipo"] == "reclamacao"),
        "relatos_sugestao": sum(1 for r in relatos if r["tipo"] == "sugestao"),
    }


_ORDEM = {"critico": 0, "alto": 1, "medio": 2, "baixo": 3}


@router.post("/resumo")
def resumo(request: Request, corpo: Resumo, supabase: Client = Depends(get_supabase)):
    """Manda o e-mail do dia para a moderação. No máximo um por dia (fuso de SP)."""
    _confere_segredo(request)
    hoje = datetime.now(FUSO).date()

    ja = (
        supabase.table("pathr_scan_run").select("id").eq("ran_on", hoje.isoformat()).limit(1).execute().data
    )
    if ja:
        return {"enviado": False, "motivo": "o resumo de hoje já saiu", "data": hoje.isoformat()}

    numeros = contar(corpo.achados, _relatos(supabase, JANELA_HORAS), _erros(supabase, JANELA_HORAS))
    destaques = [
        a.titulo
        for a in sorted((a for a in corpo.achados if a.categoria != "sugestao"), key=lambda a: _ORDEM[a.severidade])
    ]

    enviados = sum(
        1
        for destino in settings.moderator_emails
        if emails.send_scan_summary(destino, numeros, destaques, corpo.notion_url)
    )
    if enviados:
        # Só trava o dia se ALGUM e-mail saiu: travar antes deixaria uma falha
        # do Brevo sem resumo até amanhã, sem a rotina poder tentar de novo.
        supabase.table("pathr_scan_run").insert({"ran_on": hoje.isoformat(), "summary": numeros}).execute()
    return {"enviado": bool(enviados), "data": hoje.isoformat(), "numeros": numeros}
