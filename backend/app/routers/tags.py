"""Catálogo de tecnologias e as competências do usuário.

Duas coisas diferentes com o mesmo vocabulário: `pathr_tag` é o catálogo
GLOBAL (uma "React" para todo mundo) e `pathr_user_tag` é o que uma pessoa
sabe sobre cada uma. A tela de Skills mistura as duas — lista o catálogo e
marca o que é seu — e é por isso que `GET /tags/mine` devolve as duas juntas
em vez de obrigar o frontend a cruzar dois arrays por id.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.services.tag_catalog import TagCatalog, normalize_category, slugify

router = APIRouter(prefix="/tags", tags=["competências"])


class UserTagUpsert(BaseModel):
    # Um dos dois: `tag_id` quando veio do catálogo, `name` quando a pessoa
    # digitou algo que talvez ainda não exista.
    tag_id: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=60)
    category: Optional[str] = Field(default=None, max_length=30)
    proficiency: int = Field(default=0, ge=0, le=5)
    is_target: bool = False


class UserTagPatch(BaseModel):
    proficiency: Optional[int] = Field(default=None, ge=0, le=5)
    is_target: Optional[bool] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("")
def list_catalog(
    q: str = "",
    category: str = "",
    limit: int = 200,
    supabase: Client = Depends(get_supabase),
    _current_user: dict = Depends(get_current_user),
):
    """Catálogo global, para busca e autocomplete. Ordenado por popularidade:
    quem digita "j" quer "Java" ou "JavaScript" antes de "Jenkins"."""
    query = supabase.table("pathr_tag").select("id,slug,name,category,color,icon,popularity")
    if category:
        query = query.eq("category", normalize_category(category))
    if q.strip():
        # ilike cobre o começo e o meio do nome; os apelidos ficam de fora
        # aqui porque a busca é interativa e o casamento por apelido é papel
        # da importação de currículo, não da digitação.
        query = query.ilike("name", f"%{q.strip()}%")
    return (
        query.order("popularity", desc=True)
        .order("name")
        .limit(max(1, min(limit, 500)))
        .execute()
        .data
        or []
    )


@router.get("/mine")
def list_mine(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """As competências do usuário, já com o nome e a categoria da tag."""
    rows = (
        supabase.table("pathr_user_tag")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
        or []
    )
    if not rows:
        return []

    tag_ids = list({str(row["tag_id"]) for row in rows})
    tags = (
        supabase.table("pathr_tag")
        .select("id,slug,name,category,color,icon")
        .in_("id", tag_ids)
        .execute()
        .data
        or []
    )
    by_id = {str(tag["id"]): tag for tag in tags}

    merged = []
    for row in rows:
        tag = by_id.get(str(row["tag_id"]))
        if not tag:
            # Tag apagada do catálogo — a linha do usuário perdeu o
            # referente. Omitir é melhor que mostrar uma competência sem nome.
            continue
        merged.append(
            {
                "id": str(row["id"]),
                "tag_id": str(row["tag_id"]),
                "slug": tag["slug"],
                "name": tag["name"],
                "category": tag["category"],
                "color": tag.get("color"),
                "proficiency": int(row.get("proficiency") or 0),
                "confidence": float(row.get("confidence") or 0),
                "is_target": bool(row.get("is_target")),
                "source": row.get("source"),
                "last_assessed_at": row.get("last_assessed_at"),
            }
        )
    merged.sort(key=lambda item: (-item["proficiency"], item["name"]))
    return merged


@router.post("/mine", status_code=status.HTTP_201_CREATED)
def upsert_mine(
    payload: UserTagUpsert,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Adiciona ou atualiza uma competência.

    `source='manual'` e `confidence=0.8`: quando a própria pessoa marca o
    nível, o sistema confia mais do que no que o currículo dizia (0.4) e menos
    do que num quiz respondido, que é a única evidência de verdade.
    """
    user_id = str(current_user["id"])
    if payload.tag_id:
        tag_rows = (
            supabase.table("pathr_tag").select("*").eq("id", payload.tag_id).limit(1).execute().data
        )
        if not tag_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecnologia não encontrada.")
        tag = tag_rows[0]
    elif payload.name:
        tag = TagCatalog(supabase).load().resolve(payload.name, payload.category or "")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Informe tag_id ou name."
        )

    fields: dict[str, Any] = {
        "proficiency": payload.proficiency,
        "is_target": payload.is_target,
        "source": "manual",
        "confidence": 0.8,
        "last_assessed_at": _now().isoformat(),
    }
    existing = (
        supabase.table("pathr_user_tag")
        .select("id")
        .eq("user_id", user_id)
        .eq("tag_id", str(tag["id"]))
        .limit(1)
        .execute()
        .data
    )
    if existing:
        row = (
            supabase.table("pathr_user_tag")
            .update(fields)
            .eq("id", existing[0]["id"])
            .execute()
            .data[0]
        )
    else:
        row = (
            supabase.table("pathr_user_tag")
            .insert({"user_id": user_id, "tag_id": str(tag["id"]), **fields})
            .execute()
            .data[0]
        )
    return {"id": str(row["id"]), "tag_id": str(tag["id"]), "slug": tag["slug"], "name": tag["name"],
            "proficiency": row["proficiency"], "is_target": row["is_target"]}


@router.patch("/mine/{user_tag_id}")
def patch_mine(
    user_tag_id: str,
    payload: UserTagPatch,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    update = payload.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para atualizar.")
    if "proficiency" in update:
        update["confidence"] = 0.8
        update["source"] = "manual"
        update["last_assessed_at"] = _now().isoformat()
    rows = (
        supabase.table("pathr_user_tag")
        .update(update)
        .eq("id", user_tag_id)
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competência não encontrada.")
    return rows[0]


@router.delete("/mine/{user_tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mine(
    user_tag_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Tira a competência do perfil. A tag global continua existindo — ela é
    de todo mundo."""
    supabase.table("pathr_user_tag").delete().eq("id", user_tag_id).eq(
        "user_id", str(current_user["id"])
    ).execute()

# ---------------------------------------------------------------------------
# O que aprender a seguir
# ---------------------------------------------------------------------------

# Quanto tempo a lista vale antes de ser refeita. Trinta dias porque o que
# muda aqui e o mercado, nao a pessoa: a resposta para "o que um fullstack
# Java precisa saber" e praticamente a mesma daqui a uma semana.
_VALIDADE_SUGESTOES = timedelta(days=30)

_SUGESTOES_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "sugestoes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nome": {"type": "STRING"},
                    "categoria": {"type": "STRING"},
                    "motivo": {"type": "STRING"},
                    "demanda": {"type": "STRING"},
                },
                "required": ["nome", "categoria", "motivo", "demanda"],
            },
        }
    },
    "required": ["sugestoes"],
}

_SISTEMA_SUGESTOES = (
    "Voce orienta a carreira de pessoas de tecnologia no Brasil. Responde em "
    "portugues do Brasil, com franqueza e sem entusiasmo de folheto. Recomenda "
    "o que o mercado de fato pede para o objetivo declarado, nao o que esta na "
    "moda esta semana."
)

# Quanto o mercado usa aquilo. Sao tres respostas possiveis e nao uma nota,
# porque "76% de relevancia" seria um numero inventado com cara de medido.
_DEMANDAS = {"consolidada", "em alta", "aposta"}


@router.get("/suggestions")
async def suggest_tags(
    refresh: bool = False,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O que estudar a seguir, a partir do objetivo — e por quê.

    A biblioteca já cura MATERIAL para as tags que a pessoa tem. O que faltava
    é o passo anterior: descobrir quais tags deveria ter. Quem escreve "quero
    ser fullstack Java" sabe o destino e não necessariamente o caminho — e a
    lacuna entre os dois é onde alguém gasta meses estudando o que não era o
    mais importante.

    Cada sugestão vem com o motivo e com o quanto o mercado usa aquilo:
    consolidada (está em toda vaga há anos), em alta (crescendo de verdade) ou
    aposta (vale conhecer, ainda não é exigido). A distinção importa porque a
    resposta honesta para quem quer empregabilidade quase nunca é a tecnologia
    mais nova.

    O que a pessoa JÁ TEM é excluído — sugerir Java a quem declarou Java é o
    tipo de conselho que faz desconfiar de todo o resto.
    """
    user_id = str(current_user["id"])
    perfil = (
        supabase.table("pathr_profile")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]

    objetivo = _objetivo_de(perfil)
    if not objetivo:
        # Sem objetivo não há o que sugerir, e um palpite genérico ("aprenda
        # Docker") seria pior que a lista vazia: a tela pede o objetivo.
        return {"objetivo": None, "sugestoes": [], "geradas_em": None}

    guardadas = _sugestoes_guardadas(perfil, objetivo)
    if guardadas is not None and not refresh:
        return {
            "objetivo": objetivo,
            "sugestoes": _sem_as_que_ja_tem(supabase, user_id, guardadas),
            "geradas_em": perfil.get("tech_suggestions_at"),
        }

    try:
        resultado = await generate_json(
            _SISTEMA_SUGESTOES, _pedido_de_sugestoes(perfil, objetivo), _SUGESTOES_SCHEMA
        )
    except AiProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    sugestoes = _linhas_de_sugestao(resultado.content.get("sugestoes") or [])
    agora = _now().isoformat()
    supabase.table("pathr_profile").update(
        {
            "tech_suggestions": sugestoes,
            "tech_suggestions_at": agora,
            "tech_suggestions_for": objetivo,
        }
    ).eq("user_id", user_id).execute()

    return {
        "objetivo": objetivo,
        "sugestoes": _sem_as_que_ja_tem(supabase, user_id, sugestoes),
        "geradas_em": agora,
    }


def _objetivo_de(perfil: dict[str, Any]) -> str:
    """A frase que descreve para onde a pessoa quer ir."""
    for campo in ("target_role", "headline", "current_role"):
        valor = str(perfil.get(campo) or "").strip()
        if valor:
            return valor
    metas = perfil.get("goals") or []
    return str(metas[0]).strip() if metas else ""


def _sugestoes_guardadas(perfil: dict[str, Any], objetivo: str) -> Optional[list[dict[str, Any]]]:
    """A lista gravada, se ainda vale para ESTE objetivo.

    O objetivo entra na conta junto com o prazo: trocar "quero ser fullstack
    Java" por "quero ser SRE" e continuar vendo as sugestoes do plano antigo
    por mais 29 dias seria pior do que nao sugerir nada.
    """
    guardadas = perfil.get("tech_suggestions") or []
    if not guardadas:
        return None
    if str(perfil.get("tech_suggestions_for") or "") != objetivo:
        return None
    quando = perfil.get("tech_suggestions_at")
    if not quando:
        return None
    try:
        gerada_em = datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
    except ValueError:
        return None
    return guardadas if _now() - gerada_em <= _VALIDADE_SUGESTOES else None


def _pedido_de_sugestoes(perfil: dict[str, Any], objetivo: str) -> str:
    senioridade = str(perfil.get("seniority") or "").strip()
    anos = perfil.get("years_experience")
    quem = f"Senioridade declarada: {senioridade}." if senioridade else ""
    if anos:
        quem += f" Tempo de experiencia: {anos} anos."
    return (
        f"OBJETIVO DECLARADO: {objetivo}.\n{quem}\n\n"
        "Liste de 6 a 8 tecnologias que essa pessoa precisa dominar para chegar "
        "la, da mais importante para a menos.\n"
        "- nome: o nome da tecnologia como o mercado a chama.\n"
        "- categoria: uma de linguagem, framework, banco, cloud, devops, dados, "
        "ia, arquitetura, testes, seguranca, mobile, frontend, backend, "
        "ferramenta, metodologia.\n"
        "- motivo: UMA frase dizendo por que ela importa para ESTE objetivo. "
        "Concreta: o que a pessoa consegue fazer com ela, ou onde ela aparece.\n"
        "- demanda: consolidada se esta em vaga ha anos, em alta se cresce de "
        "verdade agora, aposta se ainda nao e exigida mas vale conhecer.\n"
        "Prefira o que e amplamente usado e bem visto ao que e novidade."
    )


def _linhas_de_sugestao(brutas: list[Any]) -> list[dict[str, Any]]:
    """Limpa o que veio do modelo. O que nao tem nome nao entra."""
    saida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in brutas:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("nome") or "").strip()[:60]
        if not nome or slugify(nome) in vistos:
            continue
        vistos.add(slugify(nome))
        demanda = str(item.get("demanda") or "").strip().lower()
        saida.append(
            {
                "name": nome,
                "category": normalize_category(item.get("categoria")),
                "reason": str(item.get("motivo") or "").strip()[:240],
                # Fora das tres respostas possiveis vira "consolidada": e a
                # leitura conservadora, e a que menos empurra alguem para uma
                # tecnologia que o mercado ainda nao pede.
                "demand": demanda if demanda in _DEMANDAS else "consolidada",
            }
        )
    return saida[:8]


def _sem_as_que_ja_tem(
    supabase: Client, user_id: str, sugestoes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Tira da lista o que a pessoa já declarou.

    Filtrado na LEITURA e não na gravação: a pessoa adiciona uma sugestão e
    ela some da lista na hora seguinte, sem precisar refazer a chamada de IA.
    """
    if not sugestoes:
        return []
    minhas = (
        supabase.table("pathr_user_tag")
        .select("tag_id")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    if not minhas:
        return sugestoes
    linhas = (
        supabase.table("pathr_tag")
        .select("slug")
        .in_("id", [str(item["tag_id"]) for item in minhas])
        .execute()
        .data
        or []
    )
    tenho = {str(linha["slug"]) for linha in linhas}
    return [item for item in sugestoes if slugify(item["name"]) not in tenho]

