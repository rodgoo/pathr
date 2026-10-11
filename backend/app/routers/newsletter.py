"""Newsletter do admin: escolher temas e dias, procurar notícias, receber no e-mail.

## Quem alcança

Só o super admin (`settings.super_admin_emails`); para qualquer outra conta
estas rotas respondem 404, como as de /admin. A edição vai SÓ para o e-mail da
conta que configurou — não há lista de destinatários, e por isso não há
inscrição, cancelamento nem link público.

## As rotas

- `GET  /admin/newsletter`        configuração, combinações, últimas edições
- `PUT  /admin/newsletter/config` temas, ângulos, frequência, dias e hora
- `POST /admin/newsletter/buscar` procura agora e devolve as matérias, sem enviar
- `POST /admin/newsletter/enviar` manda agora: as matérias escolhidas na tela,
  ou (sem `itens`) uma edição montada com a configuração salva
- `POST /jobs/newsletter`         o cron horário; vê quem está na hora

Enviar para o próprio e-mail não pede a chave de acesso (ao contrário de banir
ou desligar o site): o pior caso é o admin receber uma mensagem a mais.

## O interruptor

`newsletter_ativa` (uma chave de `pathr_feature_flag`) é o botão geral do
painel de Operação. Desligado, nada sai — nem o cron, nem o "enviar agora".
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.routers.admin import exigir_super_admin
from app.routers.auth import _log_event
from app.services import newsletter as servico
from app.services.moderacao import e_super_admin, esta_banido

router = APIRouter(tags=["newsletter"])
logger = logging.getLogger("pathr.newsletter")

CABECALHO = "X-Pathr-Jobs-Secret"
_PAUSADA = "A newsletter está pausada em Configurações › Operação."
_SEM_FONTE = "Nenhuma fonte de busca configurada: defina TAVILY_API_KEY ou BRAVE_API_KEY."

Frequencia = Literal["diaria", "dias_uteis", "fim_de_semana", "semanal", "mensal", "personalizada"]


class ConfigEntrada(BaseModel):
    enabled: bool = False
    topics: list[str] = Field(default_factory=list, max_length=40)
    angles: list[str] = Field(default_factory=lambda: [servico.ANGULO_PADRAO], max_length=10)
    frequency: Frequencia = "semanal"
    weekdays: list[int] = Field(default_factory=lambda: [0], max_length=7)
    month_day: int = Field(1, ge=1, le=28)
    send_hour: int = Field(8, ge=0, le=23)
    items_per_topic: int = Field(2, ge=1, le=servico.MAX_ITENS_POR_CONSULTA)

    @field_validator("weekdays")
    @classmethod
    def _dias_validos(cls, dias: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in dias):
            raise ValueError("os dias da semana vão de 0 (segunda) a 6 (domingo)")
        return sorted(set(dias))

    @model_validator(mode="after")
    def _coerente(self) -> "ConfigEntrada":
        self.topics = servico.normalizar_temas(self.topics)
        self.angles = servico.normalizar_angulos(self.angles)
        if self.frequency in ("semanal", "personalizada") and not self.weekdays:
            raise ValueError("escolha ao menos um dia da semana")
        if self.frequency == "semanal" and len(self.weekdays) != 1:
            raise ValueError("na frequência semanal vale um dia só; para vários, use personalizada")
        if self.enabled and not self.topics:
            raise ValueError("escolha ao menos uma tecnologia antes de ligar o envio")
        total = servico.quantas_consultas(self.topics, self.angles)
        if total > servico.MAX_CONSULTAS:
            raise ValueError(
                f"{total} combinações é demais (limite {servico.MAX_CONSULTAS}): "
                "tire alguma tecnologia ou ângulo"
            )
        return self


class Materia(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=8, max_length=2000)
    fonte: str = Field("", max_length=120)
    resumo: str = Field("", max_length=1000)
    imagem: str | None = Field(None, max_length=1000)
    publicado_em: str | None = None
    topico: str = Field("", max_length=80)
    categoria: str = Field(servico.ANGULO_PADRAO, max_length=20)


class Busca(BaseModel):
    """Sem campos: procura com a configuração SALVA. Com `topics`/`angles`,
    experimenta uma combinação sem salvá-la."""

    topics: list[str] | None = Field(None, max_length=40)
    angles: list[str] | None = Field(None, max_length=10)
    dias: int | None = Field(None, ge=1, le=31)


class Envio(BaseModel):
    itens: list[Materia] | None = Field(None, max_length=60)


def _config_publica(config: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    agora_local = datetime.now(timezone.utc).astimezone(servico.fuso_do(user))
    proximo = servico.proximo_envio(config, agora_local)
    return {
        "enabled": bool(config.get("enabled")),
        "topics": config.get("topics") or [],
        "angles": servico.normalizar_angulos(config.get("angles") or []),
        "frequency": config.get("frequency"),
        "weekdays": config.get("weekdays") or [],
        "month_day": config.get("month_day"),
        "send_hour": config.get("send_hour"),
        "items_per_topic": config.get("items_per_topic"),
        "last_sent_on": config.get("last_sent_on"),
        "next_send_on": proximo.isoformat() if proximo else None,
    }


def _edicoes(supabase: Client, user_id: str, limite: int = 10) -> list[dict[str, Any]]:
    linhas = (
        supabase.table("pathr_newsletter_issue").select("id,subject,kind,items,sent_on,created_at")
        .eq("user_id", user_id).order("created_at", desc=True).limit(limite).execute().data or []
    )
    return [
        {
            "id": str(l["id"]),
            "assunto": l.get("subject"),
            "tipo": l.get("kind"),
            "enviada_em": l.get("sent_on"),
            "quantidade": len(l.get("items") or []),
            "itens": l.get("items") or [],
        }
        for l in linhas
    ]


def _catalogo() -> dict[str, Any]:
    return {
        "angulos": [{"key": k, "rotulo": v["rotulo"]} for k, v in servico.ANGULOS.items()],
        "frequencias": list(servico.FREQUENCIAS),
        "limites": {
            "max_temas": servico.MAX_TEMAS,
            "max_consultas": servico.MAX_CONSULTAS,
            "max_itens_por_busca": servico.MAX_ITENS_POR_CONSULTA,
        },
    }


@router.get("/admin/newsletter")
def painel(
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    user_id = str(admin["id"])
    config = servico.ler_config(supabase, user_id)
    return {
        "config": _config_publica(config, admin),
        "combinacoes": servico.combinacoes(config["topics"], config["angles"]),
        "edicoes": _edicoes(supabase, user_id),
        "ativa": servico.interruptor_ligado(supabase),
        "fontes": servico.fontes_configuradas(),
        "email_configurado": bool(settings.brevo_api_key and settings.brevo_from_email),
        "destino": str(admin.get("email") or ""),
        # O fuso em que `send_hour` vale: o da conta, e é ele que a tela diz.
        "fuso": str(servico.fuso_do(admin)),
        **_catalogo(),
    }


@router.get("/newsletter")
def edicoes_enviadas(
    limite: int = Query(20, ge=1, le=100),
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    """As edições que saíram, da mais nova para a mais antiga, com as matérias.

    É a leitura da newsletter dentro do app (como o arquivo de um site): o
    e-mail some na caixa de entrada, isto não. Só o super admin, como o resto —
    não há leitura pública porque não há público.
    """
    return {"edicoes": _edicoes(supabase, str(admin["id"]), limite)}


@router.get("/newsletter/{edicao_id}")
def edicao(
    edicao_id: str,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    try:
        uuid.UUID(edicao_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edição não encontrada.")
    linhas = (
        supabase.table("pathr_newsletter_issue").select("id,subject,kind,items,sent_on,created_at")
        .eq("id", edicao_id).eq("user_id", str(admin["id"])).limit(1).execute().data or []
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edição não encontrada.")
    linha = linhas[0]
    itens = linha.get("items") or []
    return {
        "id": str(linha["id"]),
        "assunto": linha.get("subject"),
        "tipo": linha.get("kind"),
        "enviada_em": linha.get("sent_on"),
        "quantidade": len(itens),
        "itens": itens,
        # Agrupado como o e-mail: por tecnologia, na ordem em que saiu.
        "grupos": [{"topico": t, "itens": i} for t, i in servico.agrupar(itens)],
    }


@router.put("/admin/newsletter/config")
def salvar_config(
    corpo: ConfigEntrada,
    request: Request,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    user_id = str(admin["id"])
    agora = datetime.now(timezone.utc).isoformat()
    supabase.table("pathr_newsletter_config").upsert(
        {
            "user_id": user_id,
            "enabled": corpo.enabled,
            "topics": corpo.topics,
            "angles": corpo.angles,
            "frequency": corpo.frequency,
            "weekdays": corpo.weekdays,
            "month_day": corpo.month_day,
            "send_hour": corpo.send_hour,
            "items_per_topic": corpo.items_per_topic,
            "updated_at": agora,
        },
        on_conflict="user_id",
    ).execute()
    _log_event(
        supabase, "admin_newsletter_config", user_id=user_id, request=request,
        detail={"enabled": corpo.enabled, "frequency": corpo.frequency, "topics": len(corpo.topics)},
    )
    config = servico.ler_config(supabase, user_id)
    return {
        "config": _config_publica(config, admin),
        "combinacoes": servico.combinacoes(config["topics"], config["angles"]),
    }


@router.post("/admin/newsletter/buscar")
async def buscar(
    corpo: Busca,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    """Procura agora e devolve as matérias, sem enviar nada. É onde o admin
    confere o que a combinação traz antes de mandar."""
    if not any(servico.fontes_configuradas().values()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_SEM_FONTE)
    user_id = str(admin["id"])
    config = servico.ler_config(supabase, user_id)
    temas = servico.normalizar_temas(corpo.topics if corpo.topics is not None else config["topics"])
    angulos = servico.normalizar_angulos(corpo.angles if corpo.angles is not None else config["angles"])
    if not temas:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Escolha ao menos uma tecnologia.")
    if servico.quantas_consultas(temas, angulos) > servico.MAX_CONSULTAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Combinações demais (limite {servico.MAX_CONSULTAS}).",
        )
    dias = corpo.dias or servico.janela_em_dias(config, datetime.now(timezone.utc).date())
    itens = await servico.procurar(
        temas, angulos, dias, servico.urls_ja_enviadas(supabase, user_id), servico.MAX_ITENS_POR_CONSULTA
    )
    return {
        "dias": dias,
        "combinacoes": servico.combinacoes(temas, angulos),
        "itens": itens,
    }


@router.post("/admin/newsletter/enviar")
async def enviar_agora(
    corpo: Envio,
    request: Request,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    if not servico.interruptor_ligado(supabase):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_PAUSADA)
    user_id = str(admin["id"])
    config = servico.ler_config(supabase, user_id)

    itens = None
    if corpo.itens is not None:
        itens = servico.limpar_selecao([m.model_dump() for m in corpo.itens])
        if not itens:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma matéria válida para enviar."
            )
    elif not any(servico.fontes_configuradas().values()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_SEM_FONTE)
    elif not config["topics"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Escolha ao menos uma tecnologia."
        )

    resultado = await servico.enviar_edicao(supabase, admin, config, kind="manual", itens=itens)
    _log_event(
        supabase, "admin_newsletter_send", user_id=user_id, request=request,
        detail={"enviado": resultado["enviado"], "itens": resultado.get("itens", 0)},
    )
    return resultado


def _confere_segredo(request: Request) -> None:
    if not settings.jobs_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Disparo desligado: JOBS_SECRET não está configurado.",
        )
    # compare_digest e não `==`: comparação de texto vaza, pelo tempo, quantos
    # caracteres iniciais estavam certos (mesmo motivo de routers/jobs.py).
    if not secrets.compare_digest(request.headers.get(CABECALHO, ""), settings.jobs_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Segredo inválido.")


@router.post("/jobs/newsletter")
async def disparar(request: Request, supabase: Client = Depends(get_supabase)) -> dict[str, Any]:
    """Manda as edições devidas nesta hora. Chamado pelo cron, de hora em hora.

    Uma conta com problema não impede as outras (hoje só há uma, mas o laço
    não deve depender disso), e nada é levantado: o cron precisa de um 200 com
    o que aconteceu, e não de um 500 que o faça repetir a chamada.
    """
    _confere_segredo(request)
    if not servico.interruptor_ligado(supabase):
        return {"ativa": False, "avaliadas": 0, "enviadas": 0}

    agora_utc = datetime.now(timezone.utc)
    configs = supabase.table("pathr_newsletter_config").select("*").eq("enabled", True).execute().data or []
    enviadas = 0
    for linha in configs:
        user_id = str(linha["user_id"])
        try:
            usuarios = (
                supabase.table("pathr_user").select("id,email,name,timezone_name,banned_at")
                .eq("id", user_id).limit(1).execute().data or []
            )
            user = usuarios[0] if usuarios else None
            # Quem deixou de ser admin, ou foi banido, para de receber já.
            if not user or esta_banido(user) or not e_super_admin(user):
                continue
            config = {**servico.PADRAO, **linha}
            local = agora_utc.astimezone(servico.fuso_do(user))
            if not servico.esta_devida(config, local, agora_utc):
                continue
            resultado = await servico.enviar_edicao(
                supabase, user, config, kind="agendada", agora_utc=agora_utc
            )
            enviadas += 1 if resultado["enviado"] else 0
        except Exception:  # noqa: BLE001
            logger.warning("newsletter falhou para %s", user_id, exc_info=True)
    return {"ativa": True, "avaliadas": len(configs), "enviadas": enviadas}
