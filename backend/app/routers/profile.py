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
    notifications: Optional[dict[str, bool]] = None

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


# Os avisos por e-mail, com o padrão de cada um. Mora no código e não no banco
# porque o padrão é decisão de produto: mudá-lo aqui vale para todo mundo que
# nunca abriu a aba, sem uma linha de UPDATE.
#
# Ligados por padrão os que a pessoa pediu implicitamente ao criar um plano de
# estudos (o lembrete e o resumo); desligados os que interrompem sem ela ter
# pedido (novidades do produto e o aviso noturno de sequência em risco).
AVISOS: dict[str, bool] = {
    "lembrete_diario": True,
    "resumo_semanal": True,
    "novidades": False,
    "correcao_pronta": True,
    "sequencia_em_risco": False,
}


def _com_avisos(perfil: dict[str, Any]) -> dict[str, Any]:
    """O perfil com os avisos completos.

    O banco guarda só o que a pessoa mexeu; a resposta entrega as cinco chaves
    sempre. Sem isso o frontend teria que conhecer os padrões também, e os dois
    lados sairiam de sincronia no primeiro aviso novo.
    """
    guardado = perfil.get("notifications") or {}
    perfil["notifications"] = {
        chave: bool(guardado.get(chave, padrao)) for chave, padrao in AVISOS.items()
    }
    return perfil


@router.get("")
def get_profile(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _com_avisos(_one(supabase, "pathr_profile", str(current_user["id"])))


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
        return _com_avisos(_one(supabase, "pathr_profile", str(current_user["id"])))

    if "notifications" in update:
        # Só as chaves conhecidas entram, e o que veio é MESCLADO ao que já
        # existe: a tela manda um interruptor por vez, e substituir o objeto
        # inteiro apagaria os outros quatro a cada clique.
        atual = (_one(supabase, "pathr_profile", str(current_user["id"])) or {}).get(
            "notifications"
        ) or {}
        recebido = update["notifications"] or {}
        update["notifications"] = {
            **atual,
            **{k: bool(v) for k, v in recebido.items() if k in AVISOS},
        }

    update["updated_at"] = _now().isoformat()
    rows = (
        supabase.table("pathr_profile")
        .update(update)
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
    )
    return _com_avisos(rows[0]) if rows else {}


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
    # Com varios idiomas por pessoa, "o" perfil de idioma deixou de existir.
    # A tela inicial mostra um cartao so, entao mostra o que esta LIGADO --
    # e, entre varios ligados, o de nivel medido mais recente. Sem esta
    # escolha explicita, a linha exibida seria a que o banco devolvesse
    # primeiro, e mudaria sozinha entre um carregamento e outro.
    idiomas = (
        supabase.table("pathr_english_profile")
        .select("*")
        .eq("user_id", user_id)
        .eq("enabled", True)
        .order("last_assessment_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    english = idiomas[0] if idiomas else _one(supabase, "pathr_english_profile", user_id)
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


# ---------------------------------------------------------------------------
# Privacidade: levar os dados embora, ou apagar tudo
# ---------------------------------------------------------------------------

# As tabelas que guardam algo DA pessoa. `pathr_tag` e `pathr_resource` ficam
# de fora: são catálogos globais, iguais para todo mundo, e exportá-los daria
# a impressão de que o app coletou 91 tecnologias sobre quem pediu o arquivo.
_TABELAS_DO_USUARIO = (
    "pathr_profile",
    "pathr_user_tag",
    "pathr_resume",
    "pathr_roadmap",
    "pathr_quiz",
    "pathr_attempt",
    "pathr_review_item",
    "pathr_activity",
    "pathr_streak",
    "pathr_user_resource",
    "pathr_english_profile",
    "pathr_english_assessment",
    "pathr_english_session",
    "pathr_english_vocab",
)


@router.get("/export")
def export_data(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Tudo o que este app guarda sobre a pessoa, em JSON.

    Devolve o conteúdo e não um link de download: o volume é de kilobytes, e
    gerar arquivo em storage criaria uma URL com os dados de alguém esperando
    ser esquecida lá. O navegador monta o arquivo no cliente.

    Sem `password_hash`, sem `mfa_secret`, sem token de sessão — exportar
    credencial não é transparência, é vazamento com consentimento aparente.
    """
    user_id = str(current_user["id"])
    dados: dict[str, Any] = {
        "exportado_em": _now().isoformat(),
        "conta": {
            campo: current_user.get(campo)
            for campo in ("id", "email", "name", "locale", "timezone_name", "created_at")
        },
    }
    for tabela in _TABELAS_DO_USUARIO:
        try:
            dados[tabela] = (
                supabase.table(tabela).select("*").eq("user_id", user_id).execute().data or []
            )
        except Exception:  # noqa: BLE001
            # Uma tabela que falha não pode levar a exportação inteira junto:
            # quem pede os dados costuma estar de saída, e um erro aqui
            # devolveria nada em vez de quase tudo.
            dados[tabela] = []

    # O currículo sai sem o texto extraído: são páginas de dado pessoal que a
    # pessoa já tem no arquivo original, e que inchariam o JSON sem acrescentar.
    for curriculo in dados.get("pathr_resume") or []:
        curriculo.pop("raw_text", None)
    return dados


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Apaga a conta e tudo que pende dela.

    Apagar `pathr_user` bastaria — as chaves estrangeiras são ON DELETE
    CASCADE. O laço explícito existe para o caso em que uma tabela nova entre
    sem a cascata declarada: aqui ela aparece na lista e é apagada; sem o laço,
    ficaria órfã no banco em silêncio.

    Sem confirmação por e-mail nem carência: a tela já confirma, e um app que
    guarda o que a pessoa mandou apagar por mais alguns dias está guardando o
    que ela mandou apagar.
    """
    user_id = str(current_user["id"])
    for tabela in _TABELAS_DO_USUARIO:
        try:
            supabase.table(tabela).delete().eq("user_id", user_id).execute()
        except Exception:  # noqa: BLE001
            continue
    supabase.table("pathr_user").delete().eq("id", user_id).execute()
    return None
