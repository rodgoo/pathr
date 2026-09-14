"""Perfil, preferências e o painel de progresso.

`GET /profile/overview` é a única rota que a tela inicial chama: ela junta
streak, atividade, progresso do roadmap e nível de idioma numa resposta só.
Deixar o dashboard montar isso com cinco requisições paralelas colocaria o
tempo da tela no pior caso das cinco, e nenhuma delas é reaproveitada em
outro lugar.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.services.upload import ler_com_limite
from app.deps import get_current_user
from app.services import cifra, geo, imagem, progresso
from app.services.progress import minutos_de_leitura
from app.schemas.auth import SignupRequest

router = APIRouter(prefix="/profile", tags=["perfil"])
logger = logging.getLogger("pathr.privacidade")


class ProfileUpdate(BaseModel):
    # Perguntados no cadastro, editáveis aqui: sem isto uma cidade digitada
    # errada seria permanente. A data reusa a mesma validação de idade do
    # cadastro — a regra é a mesma, e duplicá-la deixaria as duas divergirem.
    birth_date: Optional[date] = None
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=60)
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    # Raio das vagas presenciais e híbridas; 0 = só remotas.
    job_radius_km: Optional[int] = Field(default=None, ge=0, le=1000)

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
    if perfil.get("birth_date"):
        perfil["birth_date"] = cifra.decifrar(
            perfil["birth_date"], cifra.ctx_nascimento(str(perfil.get("user_id") or ""))
        )
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

    if update.get("birth_date") is not None:
        # Cifrada no banco (services/cifra.py); a validação de idade já rodou
        # sobre a data em claro, no modelo.
        update["birth_date"] = cifra.cifrar(
            update["birth_date"].isoformat(), cifra.ctx_nascimento(str(current_user["id"]))
        )
    update["updated_at"] = _now().isoformat()
    rows = (
        supabase.table("pathr_profile")
        .update(update)
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
    )
    if rows and ("city" in update or "state" in update):
        # O fuso sai de onde a pessoa mora: é por ele que o "dia" do streak, da
        # sequência com os amigos e dos avisos por e-mail vira à meia-noite
        # dela. Com o padrão de Brasília, quem mora em Manaus perdia a
        # sequência às 23h locais.
        try:
            supabase.table("pathr_user").update(
                {"timezone_name": geo.fuso_de(rows[0].get("city"), rows[0].get("state"))}
            ).eq("id", str(current_user["id"])).execute()
        except Exception:  # noqa: BLE001
            logger.warning("não consegui atualizar o fuso de %s", current_user["id"])
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
        "has_avatar": bool(user.get("avatar_path")),
    }


# Tipos de imagem aceitos -> extensão do arquivo no bucket.
#
# Lista fechada, e conferida pelos BYTES e não pelo `content-type` que o
# navegador declara: o cabeçalho é escolhido por quem envia, e aceitar por ele
# deixaria qualquer arquivo entrar com o rótulo de imagem.
_IMAGENS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# A assinatura de cada formato nos primeiros bytes. É o que separa uma imagem
# de verdade de um arquivo renomeado.
_ASSINATURAS = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def _tipo_real(data: bytes) -> Optional[str]:
    """O formato que os bytes dizem ser, ou None se não for imagem aceita."""
    for assinatura, tipo in _ASSINATURAS:
        if data.startswith(assinatura):
            return tipo
    # WebP: "RIFF????WEBP" — o tamanho fica entre as duas marcas.
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Troca a foto de perfil.

    Substitui no lugar em vez de acumular: a foto anterior não é histórico de
    nada, e guardar todas encheria o bucket com o que ninguém vai olhar.
    """
    data = await ler_com_limite(
        file, settings.max_avatar_mb * 1024 * 1024, f"Imagem acima de {settings.max_avatar_mb} MB."
    )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    tipo = _tipo_real(data)
    if tipo is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato não aceito. Envie JPG, PNG ou WebP.",
        )

    # Reduzida a 512 px e sem EXIF (services/imagem.py): a foto da câmera tinha
    # megabytes e demorava a aparecer em toda tela.
    data = imagem.reduzir(data, tipo)
    user_id = str(current_user["id"])
    caminho = f"{user_id}/avatar.{_IMAGENS[tipo]}"
    try:
        supabase.storage.from_(settings.avatar_bucket).upload(
            caminho,
            cifra.cifrar_bytes(data, cifra.ctx_arquivo(settings.avatar_bucket, caminho)),
            {"content-type": tipo, "upsert": "true"},
        )
    except Exception as exc:  # noqa: BLE001
        # Aqui NÃO é best-effort, ao contrário do currículo: lá os bytes já
        # tinham sido lidos e o arquivo era só para reprocessar depois; aqui o
        # arquivo é o recurso. Gravar o caminho de algo que não subiu deixaria
        # a tela pedindo uma imagem que não existe.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não consegui guardar a imagem. Tente de novo.",
        ) from exc

    # A extensão muda quando o formato muda (era .png, agora .jpg), e a antiga
    # ficaria órfã ocupando espaço e podendo ser servida por engano.
    anterior = current_user.get("avatar_path")
    if anterior and anterior != caminho:
        _remove_do_bucket(supabase, anterior)

    supabase.table("pathr_user").update({"avatar_path": caminho}).eq("id", user_id).execute()
    return {"has_avatar": True}


@router.delete("/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Remove a foto. As iniciais voltam a aparecer."""
    caminho = current_user.get("avatar_path")
    if caminho:
        _remove_do_bucket(supabase, caminho)
    supabase.table("pathr_user").update({"avatar_path": None}).eq(
        "id", str(current_user["id"])
    ).execute()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/avatar")
def get_avatar(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Devolve os bytes da foto de quem está logado.

    A imagem sai por aqui, e não por URL pública do bucket, para continuar
    valendo a sessão: quem não está logado não alcança a foto de ninguém.
    """
    caminho = current_user.get("avatar_path")
    if not caminho:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil.")
    try:
        data = cifra.decifrar_bytes(
            supabase.storage.from_(settings.avatar_bucket).download(caminho),
            cifra.ctx_arquivo(settings.avatar_bucket, caminho),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Foto de perfil não encontrada."
        ) from exc
    extensao = caminho.rsplit(".", 1)[-1]
    tipo = next((t for t, ext in _IMAGENS.items() if ext == extensao), "application/octet-stream")
    # `private` porque a resposta depende de quem está logado: um cache
    # compartilhado poderia entregar a foto de uma pessoa para outra.
    return Response(content=data, media_type=tipo, headers={"Cache-Control": "private, max-age=60"})


def _remove_do_bucket(supabase: Client, caminho: str) -> None:
    """Best-effort: um arquivo órfão custa bytes; falhar a troca da foto por
    causa da limpeza do anterior custa a ação que a pessoa pediu."""
    try:
        supabase.storage.from_(settings.avatar_bucket).remove([caminho])
    except Exception:  # noqa: BLE001
        return


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
        "roadmap": _roadmap_summary(roadmap, nodes, supabase, user_id),
        "activity": _activity_summary(supabase, user_id),
    }


def _roadmap_summary(
    roadmap: Optional[dict], nodes: list[dict], supabase: Optional[Client] = None, user_id: str = ""
) -> Optional[dict]:
    """Progresso do plano, contado a partir dos nós.

    Vem dos nós e não de um contador guardado no roadmap porque um contador
    desatualizado por uma falha no meio de uma atualização mentiria em silêncio
    — e o percentual é a primeira coisa que a pessoa olha.
    """
    if not roadmap:
        return None
    trackable = [node for node in nodes if node.get("kind") != "phase"]
    # O mesmo cálculo do roadmap: o que se fez na lista da semana conta.
    avanco = (
        progresso.avanco_por_modulo(progresso.checklists_do_usuario(supabase, user_id, str(roadmap["id"])))
        if supabase is not None and user_id
        else {}
    )
    trackable = progresso.com_avanco(trackable, avanco)
    current = next((node for node in trackable if node.get("status") == "doing"), None)
    return {
        "id": str(roadmap["id"]),
        "title": roadmap.get("title"),
        "horizon_weeks": roadmap.get("horizon_weeks"),
        "weekly_hours": roadmap.get("weekly_hours"),
        "status": roadmap.get("status"),
        **progresso.resumo(trackable, avanco),
        "current_node": current,
    }


def _activity_summary(supabase: Client, user_id: str) -> dict[str, Any]:
    """Últimos 365 dias, agregados por dia — a fonte do heatmap.

    Uma consulta só, agregada em Python: são no máximo alguns milhares de
    linhas por usuário e uma RPC no Postgres seria mais uma coisa para manter
    em sincronia com o schema.
    """
    since = (date.today() - timedelta(days=366)).isoformat()
    rows = (
        supabase.table("pathr_activity")
        .select("activity_date,minutes,xp,kind,title,ref_id,detail,created_at")
        .eq("user_id", user_id)
        .gte("activity_date", since)
        .order("created_at")
        .execute()
        .data
        or []
    )
    materiais = _materiais_das_atividades(supabase, rows)

    by_day: dict[str, dict[str, Any]] = {}
    total_minutes = 0
    total_xp = 0
    for row in rows:
        day = str(row["activity_date"])
        bucket = by_day.setdefault(day, {"minutes": 0, "count": 0, "xp": 0, "items": []})
        minutes, estimado = _minutos_da_atividade(row, materiais)
        xp = int(row.get("xp") or 0)
        bucket["minutes"] += minutes
        bucket["xp"] += xp
        bucket["count"] += 1
        # O que foi feito no dia, para o painel dizer ao passar o mouse:
        # "Artigo: Learn to Use GitHub Actions · 14 min". Sem isto o quadrado
        # verde só dizia "4 atividades", e não havia como saber quais.
        material = materiais.get(str(row.get("ref_id") or ""), {})
        bucket["items"].append(
            {
                "kind": row.get("kind"),
                "resource_kind": (row.get("detail") or {}).get("resource_kind")
                or material.get("kind"),
                "title": row.get("title") or "",
                "minutes": minutes,
                "estimated": estimado,
            }
        )
        total_minutes += minutes
        total_xp += xp

    return {
        "days": [{"date": day, **values} for day, values in sorted(by_day.items())],
        "active_days": len(by_day),
        "total_minutes": total_minutes,
        "total_xp": total_xp,
    }


def _materiais_das_atividades(
    supabase: Client, rows: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Tipo e tamanho dos materiais citados nas atividades, numa consulta só."""
    ids = sorted(
        {str(r["ref_id"]) for r in rows if r.get("kind") == "resource_done" and r.get("ref_id")}
    )
    if not ids:
        return {}
    linhas = (
        supabase.table("pathr_resource")
        .select("id,kind,duration_min,reader_words")
        .in_("id", ids)
        .execute()
        .data
        or []
    )
    return {str(linha["id"]): linha for linha in linhas}


def _minutos_da_atividade(
    row: dict[str, Any], materiais: dict[str, dict[str, Any]]
) -> tuple[int, bool]:
    """Os minutos de uma atividade — e se foram estimados.

    Até a correção em `library.set_progress`, concluir um artigo gravava ZERO
    minutos: artigo não tem duração cadastrada. As linhas antigas continuam
    assim no banco, e reescrevê-las mudaria o histórico por baixo de quem o
    registrou. A estimativa é feita aqui, na leitura, e marcada como tal — o
    painel mostra "≈ 14 min" em vez de fingir que foi cronometrado.
    """
    minutos = int(row.get("minutes") or 0)
    if minutos or row.get("kind") != "resource_done":
        return minutos, False
    material = materiais.get(str(row.get("ref_id") or ""), {})
    estimado = int(material.get("duration_min") or 0) or minutos_de_leitura(
        material.get("reader_words")
    )
    return estimado, estimado > 0


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
    # As quatro abaixo entraram depois da lista e ficaram de fora da exportacao
    # ate aqui: quem pedia os proprios dados recebia um arquivo sem as
    # explicacoes, os rascunhos e os checklists que tinha escrito.
    "pathr_walkthrough",
    "pathr_explanation",
    "pathr_activity_draft",
    "pathr_activity_exercise",
    "pathr_knowledge_item",
    "pathr_doubt_thread",
    "pathr_doubt_message",
    "pathr_weekly_checklist",
    "pathr_user_course",
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
        curriculo["parsed"] = _ou_indisponivel(
            lambda: cifra.decifrar_json(curriculo.get("parsed"), cifra.ctx_curriculo_dados(user_id))
        )
    for perfil in dados.get("pathr_profile") or []:
        perfil["birth_date"] = _ou_indisponivel(
            lambda: cifra.decifrar(perfil.get("birth_date"), cifra.ctx_nascimento(user_id))
        )

    dados["relatos"] = _relatos_para_exportar(supabase, user_id)
    dados["amizades"] = _amizades_para_exportar(supabase, user_id)
    return dados


def _relatos_para_exportar(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    """Os relatos da pessoa, com a resposta da moderação. O caminho interno da
    foto não sai: é detalhe do storage, não dado dela — sai só se havia foto."""
    try:
        linhas = supabase.table("pathr_report").select("*").eq("user_id", user_id).execute().data or []
    except Exception:  # noqa: BLE001
        return []
    for linha in linhas:
        linha["tinha_foto"] = bool(linha.pop("attachment_path", None))
        linha.pop("attachment_type", None)
        for coluna in ("message", "moderator_note"):
            linha[coluna] = _ou_indisponivel(
                lambda: cifra.decifrar(linha.get(coluna), cifra.ctx_relato(user_id, coluna))
            )
    return linhas


def _ou_indisponivel(ler):
    """Um campo que não decifra (chave trocada sem a antiga) não derruba a
    exportação inteira: sai marcado, e o resto do arquivo vai."""
    try:
        return ler()
    except cifra.CifraIndisponivel:
        return "(não foi possível decifrar)"


def _amizades_para_exportar(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    """Amizades e convites, com o @ da outra pessoa — e só o @.

    O arquivo é da pessoa que pediu; nome, e-mail ou foto da outra ponta são
    dados de outra conta e não entram."""
    try:
        linhas = (
            supabase.table("pathr_friendship").select("*")
            .or_(f"requester_id.eq.{user_id},addressee_id.eq.{user_id}")
            .execute().data or []
        )
        outros = [
            str(l["addressee_id"] if str(l["requester_id"]) == user_id else l["requester_id"]) for l in linhas
        ]
        arrobas = {
            str(u["id"]): u.get("username")
            for u in (
                supabase.table("pathr_user").select("id,username").in_("id", outros).execute().data or []
            )
        } if outros else {}
    except Exception:  # noqa: BLE001
        return []
    saida = []
    for linha in linhas:
        enviei = str(linha["requester_id"]) == user_id
        outro = str(linha["addressee_id"] if enviei else linha["requester_id"])
        if linha.get("status") == "accepted":
            situacao = "amigos"
        else:
            situacao = "convite enviado" if enviei else "convite recebido"
        saida.append({"com": arrobas.get(outro), "situacao": situacao, "desde": linha.get("created_at")})
    return saida


def _apagar_arquivos(supabase: Client, bucket: str, caminhos: list[str]) -> None:
    """Remove arquivos do storage sem derrubar a exclusão da conta.

    Se o storage falhar, a conta é apagada mesmo assim — manter a conta viva
    por causa de um arquivo seria o pior dos dois mundos — e a falha fica no
    log com o bucket e a quantidade, para a limpeza ser refeita à mão."""
    caminhos = [c for c in caminhos if c]
    if not caminhos:
        return
    try:
        supabase.storage.from_(bucket).remove(caminhos)
    except Exception:  # noqa: BLE001
        logger.warning("exclusão de conta: %d arquivo(s) ficaram em %s", len(caminhos), bucket, exc_info=True)


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

    # Os ARQUIVOS primeiro, enquanto as linhas que dizem onde eles estão ainda
    # existem. A cascata do banco apaga as linhas, mas não sabe nada do storage:
    # antes disto o currículo, a foto e as fotos dos relatos ficavam nos buckets
    # depois de a pessoa mandar apagar tudo.
    def caminhos(tabela: str, coluna: str) -> list[str]:
        try:
            return [
                str(l[coluna])
                for l in supabase.table(tabela).select(coluna).eq("user_id", user_id).execute().data or []
                if l.get(coluna)
            ]
        except Exception:  # noqa: BLE001
            return []

    _apagar_arquivos(supabase, settings.resume_bucket, caminhos("pathr_resume", "storage_path"))
    _apagar_arquivos(supabase, settings.report_bucket, caminhos("pathr_report", "attachment_path"))
    _apagar_arquivos(supabase, settings.avatar_bucket, [current_user.get("avatar_path") or ""])

    # Tabelas que a lista de exportação não cobre, mas que são da pessoa:
    # relatos, amizades (as duas pontas) e a trilha de segurança — IP e
    # navegador de cada login não têm por que sobreviver à conta.
    extras = (
        ("pathr_report", "user_id"),
        ("pathr_friendship", "requester_id"),
        ("pathr_friendship", "addressee_id"),
        ("pathr_security_event", "user_id"),
    )
    for tabela in _TABELAS_DO_USUARIO:
        try:
            supabase.table(tabela).delete().eq("user_id", user_id).execute()
        except Exception:  # noqa: BLE001
            continue
    for tabela, coluna in extras:
        try:
            supabase.table(tabela).delete().eq(coluna, user_id).execute()
        except Exception:  # noqa: BLE001
            continue
    supabase.table("pathr_user").delete().eq("id", user_id).execute()
    return None
