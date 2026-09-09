"""Perfil, preferências e o painel de progresso.

`GET /profile/overview` é a única rota que a tela inicial chama: ela junta
streak, atividade, progresso do roadmap e nível de idioma numa resposta só.
Deixar o dashboard montar isso com cinco requisições paralelas colocaria o
tempo da tela no pior caso das cinco, e nenhuma delas é reaproveitada em
outro lugar.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.schemas.auth import SignupRequest

router = APIRouter(prefix="/profile", tags=["perfil"])


class ProfileUpdate(BaseModel):
    # Perguntados no cadastro, editáveis aqui: sem isto uma cidade digitada
    # errada seria permanente. A data reusa a mesma validação de idade do
    # cadastro — a regra é a mesma, e duplicá-la deixaria as duas divergirem.
    birth_date: Optional[date] = None
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=60)
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)

    headline: Optional[str] = Field(default=None, max_length=200)
    current_role: Optional[str] = Field(default=None, max_length=120)
    target_role: Optional[str] = Field(default=None, max_length=120)
    seniority: Optional[str] = Field(default=None, max_length=40)
    years_experience: Optional[float] = Field(default=None, ge=0, le=60)
    weekly_hours: Optional[int] = Field(default=None, ge=1, le=80)
    learning_style: Optional[str] = Field(default=None, max_length=20)
    goals: Optional[list[Any]] = None
    bio: Optional[str] = Field(default=None, max_length=2000)
    linkedin_url: Optional[str] = Field(default=None, max_length=300)
    github_url: Optional[str] = Field(default=None, max_length=300)

    _idade = field_validator("birth_date")(
        lambda cls, valor: valor if valor is None else SignupRequest._idade_plausivel(valor)
    )


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    locale: Optional[str] = Field(default=None, max_length=10)
    timezone_name: Optional[str] = Field(default=None, max_length=60)
    theme: Optional[str] = Field(default=None, pattern="^(light|dark|system)$")
    onboarding_completed: Optional[bool] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _one(supabase: Client, table: str, user_id: str) -> dict[str, Any]:
    rows = supabase.table(table).select("*").eq("user_id", user_id).limit(1).execute().data
    return rows[0] if rows else {}


@router.get("")
def get_profile(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _one(supabase, "pathr_profile", str(current_user["id"]))


@router.patch("")
def update_profile(
    payload: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Só os campos enviados mudam — `exclude_unset` é o que separa "não
    mandei este campo" de "quero apagar este campo"."""
    update = payload.model_dump(exclude_unset=True)
    if not update:
        return _one(supabase, "pathr_profile", str(current_user["id"]))
    update["updated_at"] = _now().isoformat()
    rows = (
        supabase.table("pathr_profile")
        .update(update)
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
    )
    return rows[0] if rows else {}


@router.patch("/account")
def update_account(
    payload: AccountUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Nome e preferências da conta. E-mail e senha têm rotas próprias em
    /auth, porque mudar qualquer um dos dois mexe em sessão."""
    update = payload.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para atualizar.")
    rows = (
        supabase.table("pathr_user").update(update).eq("id", str(current_user["id"])).execute().data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
    user = rows[0]
    return {
        "id": str(user["id"]),
        "name": user.get("name"),
        "email": user.get("email"),
        "locale": user.get("locale"),
        "timezone_name": user.get("timezone_name"),
        "theme": user.get("theme"),
        "onboarding_completed": bool(user.get("onboarding_completed")),
    }


@router.get("/overview")
def overview(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Tudo que a tela inicial mostra, numa resposta."""
    user_id = str(current_user["id"])
    streak = _one(supabase, "pathr_streak", user_id)
    english = _one(supabase, "pathr_english_profile", user_id)
    profile = _one(supabase, "pathr_profile", user_id)

    roadmap_rows = (
        supabase.table("pathr_roadmap")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_primary", True)
        .limit(1)
        .execute()
        .data
    )
    roadmap = roadmap_rows[0] if roadmap_rows else None

    nodes: list[dict] = []
    if roadmap:
        nodes = (
            supabase.table("pathr_roadmap_node")
            .select("id,title,kind,status,progress_pct,week_start,week_end,estimated_hours,parent_id,order_index")
            .eq("roadmap_id", roadmap["id"])
            .order("order_index")
            .execute()
            .data
            or []
        )

    return {
        "profile": profile,
        "streak": streak,
        "english": {
            "enabled": bool(english.get("enabled")),
            "cefr_level": english.get("cefr_level"),
            "target_level": english.get("target_level"),
        },
        "roadmap": _roadmap_summary(roadmap, nodes),
        "activity": _activity_summary(supabase, user_id),
    }


def _roadmap_summary(roadmap: Optional[dict], nodes: list[dict]) -> Optional[dict]:
    """Progresso do plano, contado a partir dos nós.

    Vem dos nós e não de um contador guardado no roadmap porque um contador
    desatualizado por uma falha no meio de uma atualização mentiria em silêncio
    — e o percentual é a primeira coisa que a pessoa olha.
    """
    if not roadmap:
        return None
    trackable = [node for node in nodes if node.get("kind") != "phase"]
    done = [node for node in trackable if node.get("status") == "done"]
    current = next((node for node in trackable if node.get("status") == "doing"), None)
    return {
        "id": str(roadmap["id"]),
        "title": roadmap.get("title"),
        "horizon_weeks": roadmap.get("horizon_weeks"),
        "weekly_hours": roadmap.get("weekly_hours"),
        "status": roadmap.get("status"),
        "total_nodes": len(trackable),
        "done_nodes": len(done),
        "progress_pct": round(100 * len(done) / len(trackable)) if trackable else 0,
        "current_node": current,
    }


def _activity_summary(supabase: Client, user_id: str) -> dict[str, Any]:
    """Últimos 365 dias, agregados por dia — a fonte do heatmap.

    Uma consulta só, agregada em Python: são no máximo alguns milhares de
    linhas por usuário e uma RPC no Postgres seria mais uma coisa para manter
    em sincronia com o schema.
    """
    since = (date.today() - timedelta(days=365)).isoformat()
    rows = (
        supabase.table("pathr_activity")
        .select("activity_date,minutes,xp,kind")
        .eq("user_id", user_id)
        .gte("activity_date", since)
        .execute()
        .data
        or []
    )

    by_day: dict[str, dict[str, int]] = {}
    total_minutes = 0
    total_xp = 0
    for row in rows:
        day = str(row["activity_date"])
        bucket = by_day.setdefault(day, {"minutes": 0, "count": 0, "xp": 0})
        minutes = int(row.get("minutes") or 0)
        xp = int(row.get("xp") or 0)
        bucket["minutes"] += minutes
        bucket["xp"] += xp
        bucket["count"] += 1
        total_minutes += minutes
        total_xp += xp

    return {
        "days": [{"date": day, **values} for day, values in sorted(by_day.items())],
        "active_days": len(by_day),
        "total_minutes": total_minutes,
        "total_xp": total_xp,
    }


@router.get("/activity")
def activity_feed(
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Feed cronológico. `limit` é limitado no servidor: um cliente pedindo
    100 mil linhas não deve conseguir."""
    return (
        supabase.table("pathr_activity")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 100)))
        .execute()
        .data
        or []
    )
