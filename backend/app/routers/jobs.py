"""O disparo horário dos avisos por e-mail.

## Por que um endpoint, e não um agendador dentro do app

A máquina na Fly suspende quando ninguém usa (`min_machines_running = 0`), e
agendador em processo dormindo não dispara nada. Quem chama é um cron externo
(.github/workflows/emails.yml), de hora em hora; a própria requisição acorda a
máquina. O segredo no cabeçalho é o que separa o cron de qualquer um.

## De hora em hora, e a decisão é por pessoa

O servidor roda em UTC e quem estuda vive no fuso dela. A cada hora o disparo
percorre as contas e pergunta que horas são para CADA uma — ver
services/notifications.py. `pathr_email_log` guarda o que já saiu hoje, e é
essa trava, e não a hora exata, que impede o e-mail repetido.

Nada aqui é enviado sem ter o que dizer: lembrete de lista vazia e resumo de
semana vazia são silêncio de propósito. Remetente que manda e-mail à toa é
remetente que a pessoa aprende a ignorar.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.routers.profile import AVISOS
from app.services import email as emails
from app.services import candidaturas, faxina, notifications, weekly_plan

router = APIRouter(prefix="/jobs", tags=["operação"])
logger = logging.getLogger("pathr.jobs")

CABECALHO = "X-Pathr-Jobs-Secret"


def _confere_segredo(request: Request) -> None:
    if not settings.jobs_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Disparo de avisos desligado: JOBS_SECRET não está configurado.",
        )
    # compare_digest e não `==`: comparação de texto vaza, pelo tempo, quantos
    # caracteres iniciais estavam certos.
    if not secrets.compare_digest(request.headers.get(CABECALHO, ""), settings.jobs_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Segredo inválido.")


def _um(supabase: Client, tabela: str, user_id: str) -> dict[str, Any]:
    linhas = supabase.table(tabela).select("*").eq("user_id", user_id).limit(1).execute().data
    return linhas[0] if linhas else {}


def _fuso(nome: str) -> ZoneInfo:
    try:
        return ZoneInfo(nome or "America/Sao_Paulo")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("America/Sao_Paulo")


def _checklist(supabase: Client, user_id: str, segunda) -> dict[str, Any]:
    linhas = (
        supabase.table("pathr_weekly_checklist")
        .select("items")
        .eq("user_id", user_id)
        .eq("week_start", segunda.isoformat())
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else {}


def _minutos(supabase: Client, user_id: str, de, ate) -> int:
    linhas = (
        supabase.table("pathr_activity")
        .select("activity_date,minutes")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    total = 0
    for linha in linhas:
        dia = str(linha.get("activity_date") or "")[:10]
        if de.isoformat() <= dia <= ate.isoformat():
            total += int(linha.get("minutes") or 0)
    return total


VAGAS_DO_DIA = "vagas_do_dia"
# A chave da preferência que liga o envio sem confirmação (routers/profile.AVISOS).
AUTOMATICO = "candidatura_automatica"

# Quantas filas de vaga uma rodada monta. Cada uma busca em várias fontes, e a
# rodada é uma requisição HTTP com tempo limite: com muita gente na mesma
# janela, o resto fica para a rodada da hora seguinte (a janela da manhã tem
# duas) e para o dia seguinte. Ninguém perde nada: a fila é diária.
_FILAS_POR_RODADA = 25


async def _fila_de_vagas(
    supabase: Client,
    user: dict,
    local,
    preferencias: dict[str, Any],
    ja_enviados: set[str],
    montadas: int,
) -> bool:
    """Monta a fila de vagas de hoje e avisa por e-mail. Devolve se avisou.

    Só de manhã, uma vez por dia (a trava é o `pathr_email_log`, como nos
    outros avisos), só para quem tem currículo analisado — sem currículo não há
    o que enviar nem com o que comparar — e só para quem não desligou o aviso.
    """
    if montadas >= _FILAS_POR_RODADA or VAGAS_DO_DIA in ja_enviados:
        return False
    if not preferencias.get(VAGAS_DO_DIA, True) or not (8 <= local.hour <= 9):
        return False
    user_id = str(user["id"])
    tem_curriculo = (
        supabase.table("pathr_resume").select("id").eq("user_id", user_id).eq("status", "parsed")
        .limit(1).execute().data
    )
    if not tem_curriculo:
        return False

    novas = await candidaturas.montar_fila(supabase, user)
    if not novas:
        return False

    # Envio automático: só para quem ligou, e só onde dá para enviar de verdade
    # (anúncio com e-mail de contato). O resto fica na fila com o link.
    enviadas: list[dict[str, Any]] = []
    if preferencias.get(AUTOMATICO):
        try:
            enviadas = await candidaturas.enviar_automaticamente(supabase, user, novas)
        except Exception:  # noqa: BLE001 — falha no envio não pode calar o aviso
            logger.warning("envio automático falhou para %s", user_id, exc_info=True)
    ids_enviados = {str(linha["id"]) for linha in enviadas}

    return emails.send_daily_jobs(
        str(user.get("email") or ""),
        str(user.get("name") or ""),
        [
            {
                "titulo": str(linha.get("title") or ""),
                "empresa": str(linha.get("company") or ""),
                "local": str(linha.get("location") or ("Remota" if linha.get("remote") else "")),
                "enviada": str(linha["id"]) in ids_enviados,
            }
            for linha in novas
        ],
    )


def _enviar(supabase: Client, user: dict, kind: str, hoje_local) -> bool:
    """Monta e manda um aviso. Devolve se saiu — o que não tem conteúdo não sai."""
    user_id = str(user["id"])
    destino, nome = user.get("email"), user.get("name") or ""
    if not destino:
        return False

    if kind == notifications.LEMBRETE:
        itens = (_checklist(supabase, user_id, weekly_plan.inicio_da_semana(hoje_local)).get("items")) or []
        pendentes = [i for i in itens if not i.get("feito")]
        if not pendentes:
            return False
        return emails.send_daily_plan(
            destino,
            nome,
            [str(i.get("titulo") or "") for i in pendentes],
            sum(int(i.get("minutos") or 0) for i in pendentes),
        )

    if kind == notifications.RESUMO:
        passada = weekly_plan.inicio_da_semana(hoje_local) - timedelta(days=7)
        itens = (_checklist(supabase, user_id, passada).get("items")) or []
        if not itens:
            return False
        streak = _um(supabase, "pathr_streak", user_id)
        return emails.send_weekly_summary(
            destino,
            nome,
            sum(1 for i in itens if i.get("feito")),
            len(itens),
            _minutos(supabase, user_id, passada, passada + timedelta(days=6)),
            int(streak.get("current") or 0),
        )

    if kind == notifications.RISCO:
        streak = _um(supabase, "pathr_streak", user_id)
        return emails.send_streak_at_risk(destino, nome, int(streak.get("current") or 0))

    return False


@router.post("/emails")
async def disparar_avisos(request: Request, supabase: Client = Depends(get_supabase)):
    """Manda os avisos devidos nesta hora. Chamado pelo cron, de hora em hora.

    É aqui também que a fila diária de candidaturas é montada, no começo da
    manhã de cada pessoa — é o que faz a busca de vagas acontecer 24/7 no
    servidor, sem depender de nenhum computador ligado.
    """
    _confere_segredo(request)
    agora = datetime.now(timezone.utc)

    usuarios = (
        supabase.table("pathr_user").select("id,email,name,timezone_name").execute().data or []
    )
    enviados: list[str] = []
    filas_montadas = 0
    for user in usuarios:
        user_id = str(user["id"])
        try:
            local = agora.astimezone(_fuso(user.get("timezone_name")))
            hoje_local = local.date()
            perfil = _um(supabase, "pathr_profile", user_id)
            preferencias = {**AVISOS, **(perfil.get("notifications") or {})}

            ja = {
                linha["kind"]
                for linha in (
                    supabase.table("pathr_email_log")
                    .select("kind")
                    .eq("user_id", user_id)
                    .eq("sent_on", hoje_local.isoformat())
                    .execute()
                    .data
                    or []
                )
            }
            atividade = (
                supabase.table("pathr_activity")
                .select("id")
                .eq("user_id", user_id)
                .eq("activity_date", hoje_local.isoformat())
                .limit(1)
                .execute()
                .data
            )
            streak = _um(supabase, "pathr_streak", user_id)

            for kind in notifications.devidos(
                local, preferencias, bool(atividade), int(streak.get("current") or 0), ja
            ):
                if _enviar(supabase, user, kind, hoje_local):
                    # Só registra o que SAIU. Gravar antes deixaria um e-mail
                    # que falhou no Brevo bloqueado até amanhã.
                    supabase.table("pathr_email_log").insert(
                        {"user_id": user_id, "kind": kind, "sent_on": hoje_local.isoformat()}
                    ).execute()
                    enviados.append(kind)

            if await _fila_de_vagas(supabase, user, local, preferencias, ja, filas_montadas):
                filas_montadas += 1
                supabase.table("pathr_email_log").insert(
                    {"user_id": user_id, "kind": VAGAS_DO_DIA, "sent_on": hoje_local.isoformat()}
                ).execute()
                enviados.append(VAGAS_DO_DIA)
        except Exception:  # noqa: BLE001
            # Uma conta com dado estranho não pode impedir os avisos das outras.
            logger.warning("aviso falhou para %s", user_id, exc_info=True)

    # Depois dos avisos, e à parte deles: a faxina falhar não pode custar um
    # e-mail, e um e-mail falhar não pode deixar a tabela crescer.
    return {
        "usuarios": len(usuarios),
        "enviados": len(enviados),
        "tipos": sorted(set(enviados)),
        "faxina": faxina.apagar_eventos_velhos(supabase, agora),
        "contas_nao_confirmadas": faxina.apagar_contas_nao_confirmadas(supabase, agora),
    }
