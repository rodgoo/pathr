"""Registro de atividade, streak e XP.

`pathr_activity` é a fonte única: streak, heatmap, horas estudadas e XP saem
todos dela, em vez de cada módulo manter o próprio contador. Contador por
módulo é o caminho mais curto para dois números que discordam na mesma tela.

O dia usado é o dia LOCAL do usuário, não UTC. Derivar de `created_at` em UTC
faria quem estuda às 22h no Brasil registrar no dia seguinte — e um streak
que quebra sozinho à noite é pior que não ter streak.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from supabase import Client

# XP por tipo de ação. Escala deliberadamente achatada: a diferença entre um
# vídeo e uma atividade prática existe, mas não a ponto de fazer valer a pena
# "farmar" o barato — o que o plano quer é constância, não pontuação.
XP_BY_KIND = {
    "resource_done": 10,
    # Acima do quiz: reconhecer a alternativa certa entre quatro e mais
    # facil que produzir a explicacao do zero, e a escala de XP deve
    # refletir o esforco real -- senao empurra para o exercicio barato.
    "explanation_done": 35,
    "quiz_done": 25,
    "node_done": 60,
    "english_session": 20,
    "english_assessment": 40,
    "review_done": 8,
    "roadmap_created": 50,
    "resume_parsed": 20,
}


def local_today(timezone_name: Optional[str]) -> date:
    try:
        zone = ZoneInfo(timezone_name or "America/Sao_Paulo")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("America/Sao_Paulo")
    return datetime.now(zone).date()


def log_activity(
    supabase: Client,
    *,
    user: dict[str, Any],
    kind: str,
    title: str = "",
    ref_id: Optional[str] = None,
    minutes: int = 0,
    tag_ids: Optional[list[str]] = None,
    detail: Optional[dict] = None,
    xp: Optional[int] = None,
) -> Optional[dict]:
    """Registra a ação e atualiza o streak. Devolve o streak atualizado.

    Best-effort: uma falha aqui não pode desfazer o que a pessoa acabou de
    concluir. Perder uma linha de feed é um incômodo; perder a conclusão de um
    módulo é perder trabalho.
    """
    user_id = str(user["id"])
    today = local_today(user.get("timezone_name"))
    try:
        supabase.table("pathr_activity").insert(
            {
                "user_id": user_id,
                "kind": kind,
                "ref_id": ref_id,
                "title": title[:200] or None,
                "minutes": max(0, minutes),
                "xp": XP_BY_KIND.get(kind, 5) if xp is None else max(0, xp),
                "tag_ids": tag_ids or [],
                "detail": detail or {},
                "activity_date": today.isoformat(),
            }
        ).execute()
    except Exception:  # noqa: BLE001
        return None
    return touch_streak(supabase, user_id, today, minutes=minutes,
                        xp=XP_BY_KIND.get(kind, 5) if xp is None else xp)


def touch_streak(
    supabase: Client, user_id: str, today: date, *, minutes: int = 0, xp: int = 0
) -> Optional[dict]:
    """Avança o streak conforme o dia local.

    Três casos, e só três: mesmo dia (não conta de novo), dia seguinte
    (continua a sequência) e qualquer intervalo maior (recomeça em 1). O
    recorde nunca diminui — é histórico, não estado.
    """
    try:
        rows = (
            supabase.table("pathr_streak").select("*").eq("user_id", user_id).limit(1).execute().data
        )
    except Exception:  # noqa: BLE001
        return None

    if not rows:
        payload = {
            "user_id": user_id,
            "current": 1,
            "longest": 1,
            "last_active_date": today.isoformat(),
            "total_xp": max(0, xp),
            "total_minutes": max(0, minutes),
        }
        try:
            return supabase.table("pathr_streak").insert(payload).execute().data[0]
        except Exception:  # noqa: BLE001
            return None

    streak = rows[0]
    last_raw = streak.get("last_active_date")
    last = date.fromisoformat(str(last_raw)) if last_raw else None

    if last == today:
        current = int(streak.get("current") or 1)
    elif last == today - timedelta(days=1):
        current = int(streak.get("current") or 0) + 1
    else:
        current = 1

    update = {
        "current": current,
        "longest": max(int(streak.get("longest") or 0), current),
        "last_active_date": today.isoformat(),
        "total_xp": int(streak.get("total_xp") or 0) + max(0, xp),
        "total_minutes": int(streak.get("total_minutes") or 0) + max(0, minutes),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        return supabase.table("pathr_streak").update(update).eq("user_id", user_id).execute().data[0]
    except Exception:  # noqa: BLE001
        return None
