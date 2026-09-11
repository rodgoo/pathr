"""Biblioteca: material curado e o progresso do usuário nele.

`pathr_resource` é um catálogo GLOBAL, como as tags — um vídeo bom sobre JPA
serve para todo mundo que estuda JPA, e curar por usuário multiplicaria o
mesmo trabalho. O que é por pessoa mora em `pathr_user_resource`: salvo, em
andamento, concluído, nota, minutos gastos.

A curadoria é filtrada pelas tags do usuário, e é isso que faz a biblioteca
parecer pessoal sem ser duplicada.

Quem PREENCHE o catálogo é `POST /curate`, que delega a
services/resource_search.py. Até ele existir esta tabela só era lida, e a
biblioteca vinha vazia para todo mundo — o modelo estava pronto e a fonte
nunca chegou.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services import resource_search
from app.services import reader
from app.services.progress import log_activity

router = APIRouter(prefix="/library", tags=["biblioteca"])


class ResourceProgress(BaseModel):
    status: str = Field(default="saved", pattern="^(saved|in_progress|done|dismissed)$")
    progress_pct: int = Field(default=0, ge=0, le=100)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    minutes_spent: int = Field(default=0, ge=0, le=600)
    notes: Optional[str] = Field(default=None, max_length=2000)
    # Onde parou: "23:10", "capítulo 4", "seção sobre índices". Texto livre
    # porque metade da biblioteca é artigo e PDF, onde segundo não diz nada.
    position_note: Optional[str] = Field(default=None, max_length=200)
    # A posição do vídeo em segundos, mandada pelo player. 24h de teto é
    # absurdo para um material de estudo e ainda assim barra valor corrompido.
    position_seconds: Optional[int] = Field(default=None, ge=0, le=86_400)


# Até onde consumir material pode levar o nível sozinho. Ver
# `_aprendeu_com_o_material`.
_TETO_POR_CONSUMO = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_tag_ids(supabase: Client, user_id: str) -> list[str]:
    rows = (
        supabase.table("pathr_user_tag")
        .select("tag_id")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    return [str(row["tag_id"]) for row in rows]


@router.get("")
def list_resources(
    q: str = "",
    kind: str = "",
    language: str = "",
    only_mine: bool = True,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Material curado, por padrão filtrado pelas tags do usuário.

    `only_mine=false` abre o catálogo inteiro — útil para procurar algo que
    ainda não está no plano.
    """
    user_id = str(current_user["id"])
    query = supabase.table("pathr_resource").select("*")

    if kind:
        query = query.eq("kind", kind)
    if language:
        query = query.eq("language", language)
    if q.strip():
        query = query.ilike("title", f"%{q.strip()}%")
    if only_mine:
        tag_ids = _user_tag_ids(supabase, user_id)
        if not tag_ids:
            return []
        # `overlaps` no uuid[] — o recurso serve se citar QUALQUER tag do
        # usuário. Exigir todas devolveria quase nada.
        query = query.overlaps("tag_ids", tag_ids)

    resources = (
        query.order("quality_score", desc=True).limit(max(1, min(limit, 100))).execute().data or []
    )
    if not resources:
        return []

    progress = (
        supabase.table("pathr_user_resource")
        .select("*")
        .eq("user_id", user_id)
        .in_("resource_id", [str(item["id"]) for item in resources])
        .execute()
        .data
        or []
    )
    by_resource = {str(row["resource_id"]): row for row in progress}

    return [
        {
            **resource,
            "user_status": (by_resource.get(str(resource["id"])) or {}).get("status"),
            "user_progress_pct": (by_resource.get(str(resource["id"])) or {}).get("progress_pct", 0),
            "user_rating": (by_resource.get(str(resource["id"])) or {}).get("rating"),
            # É o que permite continuar de onde parou em vez de procurar de
            # novo — e por isso vem na listagem, não só no detalhe.
            "user_position_note": (by_resource.get(str(resource["id"])) or {}).get(
                "position_note"
            ),
            "user_position_seconds": (by_resource.get(str(resource["id"])) or {}).get(
                "position_seconds"
            ),
        }
        for resource in resources
    ]


# Quanto tempo o artigo extraído vale antes de ser buscado de novo. Artigo é
# corrigido e atualizado; um cache eterno mostraria para sempre a primeira
# versão vista. Sete dias é longo o bastante para uma leitura em partes não
# gastar duas buscas.
_VALIDADE_LEITURA = timedelta(days=7)


@router.get("/{resource_id}/reader")
def read_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O artigo extraído, para ler DENTRO do PathR.

    Metade dos sites recusa ser exibida num quadro, e o bloqueio não é
    detectável pelo JavaScript — o quadro só fica em branco. Por isso quem
    busca é o servidor. Ver services/reader.py.

    O resultado fica na linha do RECURSO, que é compartilhada: uma busca serve
    todo mundo que abrir o mesmo material, em vez de cada leitor bater de novo
    no site de origem pelo mesmo texto.
    """
    linhas = (
        supabase.table("pathr_resource")
        .select("id,title,url,provider,author,kind,reader_html,reader_words,reader_status,reader_error,reader_fetched_at")
        .eq("id", resource_id)
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado.")
    recurso = linhas[0]

    if not _leitura_vencida(recurso):
        return _leitura_publica(recurso)

    campos: dict[str, Any] = {"reader_fetched_at": _now().isoformat()}
    try:
        leitura = reader.ler(recurso["url"])
    except reader.LeituraIndisponivel as exc:
        # Falhar aqui não é erro do app: o site pode estar fora, recusar robôs
        # ou não ter texto extraível. A tela mostra o motivo e o link original,
        # que é uma resposta melhor que um quadro vazio.
        campos.update({"reader_status": "failed", "reader_error": exc.motivo[:300]})
    else:
        campos.update(
            {
                "reader_status": "ok",
                "reader_html": leitura.html,
                "reader_words": leitura.palavras,
                "reader_error": None,
            }
        )
    supabase.table("pathr_resource").update(campos).eq("id", resource_id).execute()
    return _leitura_publica({**recurso, **campos})


def _leitura_vencida(recurso: dict[str, Any]) -> bool:
    if recurso.get("reader_status") != "ok" or not recurso.get("reader_html"):
        return True
    buscado = recurso.get("reader_fetched_at")
    if not buscado:
        return True
    try:
        quando = datetime.fromisoformat(str(buscado).replace("Z", "+00:00"))
    except ValueError:
        return True
    return _now() - quando > _VALIDADE_LEITURA


def _leitura_publica(recurso: dict[str, Any]) -> dict[str, Any]:
    """O que a tela precisa. A fonte vai junto SEMPRE: o modo leitura não
    substitui o original, e quem escreveu merece o crédito e a visita."""
    return {
        "id": str(recurso["id"]),
        "title": recurso.get("title"),
        "url": recurso.get("url"),
        "provider": recurso.get("provider") or recurso.get("author"),
        "status": recurso.get("reader_status") or "pending",
        "html": recurso.get("reader_html") if recurso.get("reader_status") == "ok" else None,
        "words": recurso.get("reader_words"),
        "error": recurso.get("reader_error"),
    }


@router.put("/{resource_id}/progress")
def set_progress(
    resource_id: str,
    payload: ResourceProgress,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Salva, retoma ou conclui um material."""
    user_id = str(current_user["id"])
    resource = (
        supabase.table("pathr_resource")
        .select("id,title,tag_ids,duration_min")
        .eq("id", resource_id)
        .limit(1)
        .execute()
        .data
    )
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado.")
    resource = resource[0]

    fields: dict[str, Any] = payload.model_dump(exclude_none=True)
    if payload.status == "done":
        fields["progress_pct"] = 100
        fields["completed_at"] = _now().isoformat()
        # Concluído não tem "onde parei": manter a marca faria a tela oferecer
        # retomar um material que a pessoa já terminou.
        fields["position_note"] = None
        fields["position_seconds"] = None

    existing = (
        supabase.table("pathr_user_resource")
        .select("id,status")
        .eq("user_id", user_id)
        .eq("resource_id", resource_id)
        .limit(1)
        .execute()
        .data
    )
    was_done = bool(existing) and existing[0].get("status") == "done"

    if existing:
        row = (
            supabase.table("pathr_user_resource")
            .update(fields)
            .eq("id", existing[0]["id"])
            .execute()
            .data[0]
        )
    else:
        row = (
            supabase.table("pathr_user_resource")
            .insert({"user_id": user_id, "resource_id": resource_id, **fields})
            .execute()
            .data[0]
        )

    # Só registra atividade na PRIMEIRA conclusão: reabrir e marcar de novo
    # não deveria render XP e streak outra vez.
    if payload.status == "done" and not was_done:
        _aprendeu_com_o_material(supabase, user_id, resource)
        log_activity(
            supabase,
            user=current_user,
            kind="resource_done",
            title=resource.get("title") or "",
            ref_id=resource_id,
            minutes=payload.minutes_spent or int(resource.get("duration_min") or 0),
            tag_ids=[str(tag) for tag in (resource.get("tag_ids") or [])],
        )

    return row


def _aprendeu_com_o_material(
    supabase: Client, user_id: str, recurso: dict[str, Any]
) -> None:
    """Concluir um material sobe a proficiência nas tecnologias dele.

    Era o buraco no meio do produto: o app media o nível pelo que a pessoa
    RESPONDIA e ignorava o que ela CONSUMIA. Terminar cinco vídeos e três
    artigos sobre Docker não mexia em nada — o sistema seguia perguntando como
    se ela nunca tivesse aberto o assunto, e a dificuldade dos quizzes não
    andava.

    Sobe UM nível por vez e para em 2 ("aprendiz"). O teto é mais baixo que o
    de concluir um módulo (3, "autônomo") de propósito: assistir e ler
    comprovam contato, não autonomia. Quem quiser passar de 2 entrega um
    módulo, acerta um quiz ou edita o próprio nível — e aí há evidência.

    Best-effort como o `log_activity`: perder a subida custa uma calibragem;
    derrubar a conclusão custa o que a pessoa acabou de estudar.
    """
    try:
        tag_ids = [str(tag) for tag in (recurso.get("tag_ids") or [])]
        if not tag_ids:
            return
        linhas = (
            supabase.table("pathr_user_tag")
            .select("id,proficiency,confidence")
            .eq("user_id", user_id)
            .in_("tag_id", tag_ids)
            .execute()
            .data
            or []
        )
        for linha in linhas:
            atual = int(linha.get("proficiency") or 0)
            if atual >= _TETO_POR_CONSUMO:
                continue
            supabase.table("pathr_user_tag").update(
                {
                    "proficiency": atual + 1,
                    # A confiança sobe menos que no módulo concluído: a
                    # evidência aqui é mais fraca, e o número precisa dizer
                    # isso a quem for ler depois.
                    "confidence": min(1.0, float(linha.get("confidence") or 0.5) + 0.1),
                    "source": "library",
                    "last_assessed_at": _now().isoformat(),
                }
            ).eq("id", linha["id"]).execute()
    except Exception:  # noqa: BLE001
        return


@router.get("/mine")
def my_library(
    status_filter: str = "",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O que o usuário salvou ou começou, com os dados do material junto."""
    query = (
        supabase.table("pathr_user_resource")
        .select("*")
        .eq("user_id", str(current_user["id"]))
    )
    if status_filter:
        query = query.eq("status", status_filter)
    rows = query.order("created_at", desc=True).limit(200).execute().data or []
    if not rows:
        return []

    resources = (
        supabase.table("pathr_resource")
        .select("*")
        .in_("id", [str(row["resource_id"]) for row in rows])
        .execute()
        .data
        or []
    )
    by_id = {str(item["id"]): item for item in resources}
    return [
        {**row, "resource": by_id.get(str(row["resource_id"]))}
        for row in rows
        if by_id.get(str(row["resource_id"]))
    ]


# ---------------------------------------------------------------------------
# Curadoria — quem escreve no catálogo
# ---------------------------------------------------------------------------

# Quantas tags uma chamada pode buscar. O limite é de COTA, não de tempo:
# `search.list` do YouTube custa 100 das 10.000 unidades diárias do app
# inteiro, então três tags por clique são 300 unidades. Quem abre um módulo
# com seis tecnologias recebe as três mais carentes agora e as outras na
# chamada seguinte, em vez de o primeiro usuário do dia consumir a cota de
# todos.
_MAX_TAGS_PER_CALL = 3


@router.post("/curate")
async def curate_library(
    node_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Busca material novo para as tags do usuário (ou as de um módulo).

    Devolve o que ENTROU, não o que existe: a tela chama isto e recarrega a
    lista, e um resumo do catálogo inteiro aqui só duplicaria o GET.

    Não é idempotente por acaso — é por carência. Chamar duas vezes seguidas
    não busca duas vezes, porque `pathr_tag.curated_at` segura a segunda; o
    retorno nesse caso traz `tags_buscadas: []`, e é assim que a tela sabe
    dizer "já procuramos há pouco" em vez de "não achamos nada".
    """
    user_id = str(current_user["id"])

    if node_id:
        node = _owned_node(supabase, node_id, user_id)
        wanted = [str(tag) for tag in (node.get("tag_ids") or [])]
    else:
        wanted = _user_tag_ids(supabase, user_id)

    if not wanted:
        return {
            "novos": 0,
            "tags_buscadas": [],
            "motivo": "Nenhuma tecnologia associada ainda — preencha o perfil ou gere o roadmap.",
        }

    tags = (
        supabase.table("pathr_tag")
        .select("id,name,slug,category,curated_at")
        .in_("id", wanted)
        .execute()
        .data
        or []
    )
    pendentes = [tag for tag in tags if resource_search.needs_curation(tag)][:_MAX_TAGS_PER_CALL]

    if not pendentes:
        return {
            "novos": 0,
            "tags_buscadas": [],
            "motivo": "Essas tecnologias foram buscadas há pouco. A curadoria repete a cada 14 dias.",
        }

    novos = 0
    for tag in pendentes:
        candidatos = await resource_search.search_for_tag(tag)
        novos += _absorve(supabase, candidatos, str(tag["id"]))
        # Carimba mesmo quando a busca não achou nada: sem isso, uma tag sem
        # material seria rebuscada a cada clique e gastaria a cota inteira
        # justamente no assunto que não tem resultado.
        supabase.table("pathr_tag").update({"curated_at": _now().isoformat()}).eq(
            "id", str(tag["id"])
        ).execute()

    # Sem `log_activity` aqui, de propósito. Ela não só escreve no feed: ela
    # chama `touch_streak`, que avança a sequência de dias mesmo com xp=0. Um
    # clique em "procurar material" viraria um dia estudado, e o streak
    # passaria a medir cliques em vez de estudo — justo o número que o app usa
    # para dizer à pessoa que ela está sendo constante. Procurar material não é
    # estudar; ler o que foi encontrado é, e isso já entra por `resource_done`.
    fontes = resource_search.sources_enabled()
    return {
        "novos": novos,
        "tags_buscadas": [tag.get("name") or tag.get("slug") for tag in pendentes],
        "motivo": None
        if novos
        else (
            "Nenhum material novo passou na verificação de link."
            if any(fontes.values())
            else "Nenhuma fonte de busca configurada no servidor."
        ),
    }


def _absorve(supabase: Client, candidatos: list, tag_id: str) -> int:
    """Grava os candidatos e devolve quantos são NOVOS.

    Não usa upsert com `on_conflict=url` de propósito. O catálogo é global e um
    mesmo vídeo serve a várias tags: um upsert sobrescreveria `tag_ids` com a
    tag desta rodada, e o vídeo que servia Docker e Kubernetes passaria a
    servir só o último. Aqui a linha que já existe recebe a tag NOVA somada às
    que ela já tinha.
    """
    if not candidatos:
        return 0

    urls = [item.url for item in candidatos]
    existentes = {
        row["url"]: row
        for row in (
            supabase.table("pathr_resource").select("id,url,tag_ids").in_("url", urls).execute().data
            or []
        )
    }

    inserir = []
    for candidato in candidatos:
        atual = existentes.get(candidato.url)
        if atual is None:
            inserir.append(candidato.to_row())
            continue

        ja_tem = {str(tag) for tag in (atual.get("tag_ids") or [])}
        if tag_id not in ja_tem:
            supabase.table("pathr_resource").update(
                {"tag_ids": sorted(ja_tem | {tag_id})}
            ).eq("id", atual["id"]).execute()

    if inserir:
        try:
            supabase.table("pathr_resource").insert(inserir).execute()
        except Exception:  # noqa: BLE001
            # O lote falha inteiro se UMA url já existir — e isso acontece
            # quando duas buscas da mesma tag correm juntas (o botão da tela e
            # a busca em segundo plano do checklist). Um por um, o repetido
            # falha sozinho e o resto entra.
            entraram = 0
            for linha in inserir:
                try:
                    supabase.table("pathr_resource").insert(linha).execute()
                    entraram += 1
                except Exception:  # noqa: BLE001
                    continue
            return entraram
    return len(inserir)


def _owned_node(supabase: Client, node_id: str, user_id: str) -> dict[str, Any]:
    """O módulo é deste usuário?

    Mesma checagem em dois passos de roadmap.py: `pathr_roadmap_node` não tem
    `user_id` — ele pertence ao roadmap, e é o roadmap que pertence a alguém.
    Sem isto, um id adivinhado gastaria a cota de busca de outra pessoa.
    """
    rows = (
        supabase.table("pathr_roadmap_node").select("*").eq("id", node_id).limit(1).execute().data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado.")
    node = rows[0]
    owner = (
        supabase.table("pathr_roadmap")
        .select("id")
        .eq("id", node["roadmap_id"])
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado.")
    return node
