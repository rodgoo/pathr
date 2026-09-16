"""A fila diária de candidaturas: ver, escrever a carta e enviar o currículo.

O porquê e as regras estão em services/candidaturas.py. Aqui ficam as rotas e,
principalmente, o cuidado com o envio.

## Dois caminhos, porque as vagas são de dois tipos

- **Tem e-mail de contato**: o app manda a carta com o currículo em anexo, e a
  candidatura fica registrada como enviada.
- **Pede para responder no site** (Gupy, LinkedIn, formulário próprio com
  perguntas): ninguém responde isso no lugar da pessoa — cada vaga pergunta uma
  coisa, e inventar resposta em nome dela seria mentir para o recrutador. A
  resposta traz o LINK da vaga para ela abrir e responder, com a carta já
  escrita para copiar, e o botão que marca como enviada.

## Por que o envio é limitado

Enviar e-mail pelo domínio do PathR para um endereço digitado por quem usa o
app é, sem cuidado, um relay de spam de graça — e quem perde a reputação de
envio (e com ela todos os e-mails de confirmação de conta) é o app. Então:

- só dá para enviar para uma candidatura que EXISTE na fila daquela pessoa;
- há teto diário por conta;
- cada envio vira evento de segurança, com o destino registrado;
- o remetente é o PathR (é dele o domínio autenticado), mas o `Reply-To` é a
  pessoa: a empresa responde para ela.
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services import candidaturas as servico
from app.services import email as email_service
from app.services import limites

router = APIRouter(prefix="/candidaturas", tags=["candidaturas"])


class PedidoDeEnvio(BaseModel):
    """O envio de uma candidatura.

    Sem `email`, não há para onde mandar (a vaga pede para responder no site):
    a candidatura é só MARCADA como enviada, que é o que a pessoa faz depois de
    responder as perguntas por lá.
    """

    email: Optional[EmailStr] = None
    carta: Optional[str] = Field(default=None, max_length=6000)
    assunto: Optional[str] = Field(default=None, max_length=200)


@router.get("")
def listar(
    dias: int = 30,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """A fila de hoje e o histórico recente."""
    user_id = str(current_user["id"])
    hoje = servico.hoje_de(current_user)
    desde = hoje - timedelta(days=max(1, min(dias, 180)))
    linhas = [servico.para_api(linha, user_id) for linha in servico.fila(supabase, user_id, desde)]
    return {
        "hoje": hoje.isoformat(),
        "por_dia": servico.POR_DIA,
        "candidaturas": linhas,
        "enviadas": sum(1 for linha in linhas if linha["status"] == "enviada"),
    }


@router.post("/gerar", status_code=status.HTTP_201_CREATED)
async def gerar(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Monta a fila de hoje agora, sem esperar o horário do agendador."""
    user_id = str(current_user["id"])
    limites.consumir(supabase, limites.FILA_DE_VAGAS, user_id)
    novas = await servico.montar_fila(supabase, current_user)
    return {"novas": [servico.para_api(linha, user_id) for linha in novas]}


@router.post("/{application_id}/carta")
async def carta(
    application_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Escreve (ou reescreve) a carta de apresentação desta vaga."""
    user_id = str(current_user["id"])
    limites.consumir(supabase, limites.CARTA_POR_USUARIO, user_id)
    linha = servico.uma(supabase, user_id, application_id)
    return servico.para_api(await servico.escrever_carta(supabase, current_user, linha), user_id)


@router.post("/{application_id}/enviar")
async def enviar(
    application_id: str,
    payload: PedidoDeEnvio,
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Envia o currículo para a vaga, ou registra que você se candidatou.

    Com e-mail de destino, o app manda a carta com o currículo em anexo. Sem
    ele, só marca como enviada — é o caminho de quem respondeu as perguntas no
    site da empresa, que é a maioria das vagas.
    """
    user_id = str(current_user["id"])
    linha = servico.uma(supabase, user_id, application_id)

    if not payload.email:
        return servico.para_api(servico.marcar(supabase, user_id, application_id, "enviada"), user_id)

    limites.consumir(supabase, limites.ENVIO_DE_CANDIDATURA, user_id)

    carta_texto = (payload.carta or "").strip()
    if not carta_texto:
        carta_texto = (servico.para_api(linha, user_id).get("letter") or "").strip()
        if not carta_texto:
            linha = await servico.escrever_carta(supabase, current_user, linha)
            carta_texto = (servico.para_api(linha, user_id).get("letter") or "").strip()
    assunto = (payload.assunto or linha.get("subject") or f"Candidatura — {linha.get('title')}").strip()[:200]

    anexo_nome, anexo_base64 = _curriculo_em_anexo(supabase, user_id)
    if not anexo_base64:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Não achei seu currículo para anexar. Envie o arquivo na aba Currículo.",
        )

    enviado = email_service.send_application(
        to_email=str(payload.email),
        subject=assunto,
        carta=carta_texto,
        candidato_nome=str(current_user.get("name") or ""),
        candidato_email=str(current_user.get("email") or ""),
        anexo_nome=anexo_nome,
        anexo_base64=anexo_base64,
    )
    if not enviado:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não consegui enviar o e-mail agora. Tente de novo em alguns minutos.",
        )

    _registrar_envio(supabase, request, user_id, str(payload.email), str(linha.get("url") or ""))
    atualizada = servico.marcar(
        supabase, user_id, application_id, "enviada", {"to_email": str(payload.email)}
    )
    return servico.para_api(atualizada, user_id)


@router.post("/{application_id}/descartar")
def descartar(
    application_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    return servico.para_api(servico.marcar(supabase, user_id, application_id, "descartada"), user_id)


def _curriculo_em_anexo(supabase: Client, user_id: str) -> tuple[str, str]:
    """O arquivo do currículo principal, em base64 para o anexo."""
    import base64

    from app.routers.resumes import _load_file

    linhas = (
        supabase.table("pathr_resume").select("*").eq("user_id", user_id)
        .order("is_primary", desc=True).order("created_at", desc=True).limit(1).execute().data or []
    )
    if not linhas:
        return "", ""
    conteudo = _load_file(supabase, linhas[0])
    if not conteudo:
        return "", ""
    nome = str(linhas[0].get("filename") or "curriculo.pdf")
    return nome[:120], base64.b64encode(conteudo).decode()


def _registrar_envio(supabase: Client, request: Request, user_id: str, destino: str, vaga: str) -> None:
    """Todo envio fica registrado: é o que permite ver abuso do envio."""
    from app.routers.auth import _log_event

    try:
        _log_event(
            supabase,
            "candidatura_enviada",
            user_id=user_id,
            request=request,
            detail={"destino": destino[:120], "vaga": vaga[:200]},
        )
    except Exception:  # noqa: BLE001 — registro não pode derrubar o envio
        pass
