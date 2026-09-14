"""Currículo: envio, leitura por IA e importação das competências.

O fluxo tem quatro passos e cada um é uma requisição separada, de propósito:

1. `POST /resumes` — recebe o arquivo, guarda e responde na hora.
2. `POST /resumes/{id}/parse` — chama a IA. É a única parte lenta (2 a 15s)
   e a única que pode falhar por cota de terceiro, então fica isolada: o
   upload nunca é perdido porque a IA estava fora.
3. `GET /resumes/{id}` — o que a IA leu, para a pessoa revisar.
4. `POST /resumes/{id}/apply` — só depois da revisão as tecnologias viram
   `pathr_user_tag`. Nada entra no perfil sem alguém confirmar, porque a
   proficiência estimada de um currículo é palpite e o roadmap inteiro é
   construído em cima dela.

Reenviar o mesmo arquivo não gasta chamada de IA: o SHA-256 do conteúdo é
chave (`content_hash`), e um envio repetido reaproveita o `parsed` anterior.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from supabase import Client

from app.ai_providers import AiProviderError
from app.config import settings
from app.database import get_supabase
from app.services.upload import ler_com_limite
from app.deps import get_current_user
from app.services import cifra
from app.services.resume_parser import parse_resume_with_fallback
from app.services.tag_catalog import TagCatalog
from app.services.text_extract import extract_text, normalize_kind

router = APIRouter(prefix="/resumes", tags=["currículo"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owned(supabase: Client, resume_id: str, user_id: str) -> dict[str, Any]:
    rows = (
        supabase.table("pathr_resume")
        .select("*")
        .eq("id", resume_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currículo não encontrado.")
    return _decifrado(rows[0])


def _decifrado(resume: dict[str, Any]) -> dict[str, Any]:
    """A linha com o texto extraído e os dados lidos em claro, para uso nesta
    requisição. No banco os dois ficam cifrados (services/cifra.py): o
    currículo tem nome, e-mail, telefone e histórico de quem o enviou."""
    user_id = str(resume.get("user_id") or "")
    return {
        **resume,
        "raw_text": cifra.decifrar(resume.get("raw_text"), cifra.ctx_curriculo_texto(user_id)),
        "parsed": cifra.decifrar_json(resume.get("parsed"), cifra.ctx_curriculo_dados(user_id)),
    }


def _public(resume: dict[str, Any]) -> dict[str, Any]:
    """O que o frontend vê. `raw_text` fica de fora: é grande e só serve para
    diagnóstico no servidor."""
    return {
        "id": str(resume["id"]),
        "filename": resume["filename"],
        "mime_type": resume["mime_type"],
        "size_bytes": resume["size_bytes"],
        "status": resume["status"],
        "error": resume.get("error"),
        "is_primary": bool(resume.get("is_primary")),
        "parsed": resume.get("parsed") or {},
        "created_at": resume.get("created_at"),
        "parsed_at": resume.get("parsed_at"),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Recebe o arquivo e devolve na hora, sem chamar IA."""
    kind = normalize_kind(file.filename or "", file.content_type or "")
    if not kind:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato não aceito. Envie PDF, DOCX, ODT, RTF, TXT ou MD.",
        )

    data = await ler_com_limite(
        file, settings.max_resume_mb * 1024 * 1024, f"Arquivo acima de {settings.max_resume_mb} MB."
    )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    user_id = str(current_user["id"])
    content_hash = hashlib.sha256(data).hexdigest()

    # Mesmo arquivo já lido antes: devolve o resultado em vez de gastar IA.
    existing = (
        supabase.table("pathr_resume")
        .select("*")
        .eq("user_id", user_id)
        .eq("content_hash", content_hash)
        .eq("status", "parsed")
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return {**_public(_decifrado(existing[0])), "reused": True}

    extraction = extract_text(data, kind)
    storage_path = _store_file(supabase, user_id, content_hash, kind, data, file.content_type)

    created = (
        supabase.table("pathr_resume")
        .insert(
            {
                "user_id": user_id,
                "filename": (file.filename or f"curriculo.{kind}")[:200],
                "mime_type": file.content_type or "application/octet-stream",
                "size_bytes": len(data),
                "content_hash": content_hash,
                "storage_path": storage_path,
                "raw_text": cifra.cifrar(extraction.text[:200_000] or None, cifra.ctx_curriculo_texto(user_id)),
                "status": "pending",
                # Nota da extração já entra aqui: se o PDF for digitalizado,
                # o usuário vê o motivo antes mesmo de mandar ler.
                "error": extraction.note or None,
            }
        )
        .execute()
        .data[0]
    )
    return {**_public(_decifrado(created)), "reused": False}


def _store_file(
    supabase: Client,
    user_id: str,
    content_hash: str,
    kind: str,
    data: bytes,
    content_type: Optional[str],
) -> Optional[str]:
    """Sobe para o Supabase Storage. Best-effort: guardar o arquivo é bom para
    reprocessar depois, mas a leitura em si não depende disso — os bytes já
    estão em mãos nesta requisição."""
    path = f"{user_id}/{content_hash}.{kind}"
    try:
        supabase.storage.from_(settings.resume_bucket).upload(
            path,
            # Cifrado: quem abrir o bucket por fora vê bytes sem sentido.
            cifra.cifrar_bytes(data, cifra.ctx_arquivo(settings.resume_bucket, path)),
            {"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )
    except Exception:  # noqa: BLE001
        return None
    return path


@router.get("")
def list_resumes(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    rows = (
        supabase.table("pathr_resume")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    return [_public(_decifrado(row)) for row in rows]


@router.get("/{resume_id}")
def get_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _public(_owned(supabase, resume_id, str(current_user["id"])))


@router.post("/{resume_id}/parse")
async def parse_resume_endpoint(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Lê o currículo com IA. É aqui que a rotação de provedores atua.

    O trabalho roda na própria requisição em vez de numa fila: a pessoa está
    olhando a tela de "lendo seu currículo" e o tempo total é de segundos.
    Uma fila só valeria a pena se houvesse trabalho em lote, que não há.
    """
    user_id = str(current_user["id"])
    resume = _owned(supabase, resume_id, user_id)

    if resume["status"] == "parsed":
        return _public(resume)

    data = _load_file(supabase, resume)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="O arquivo não está mais disponível. Envie o currículo novamente.",
        )

    kind = normalize_kind(resume["filename"], resume["mime_type"]) or "pdf"
    extraction = extract_text(data, kind)

    supabase.table("pathr_resume").update({"status": "parsing", "error": None}).eq(
        "id", resume_id
    ).execute()

    job_id = _open_ai_job(supabase, user_id, resume_id)
    try:
        parsed, ai_result = await parse_resume_with_fallback(
            data=data, kind=kind, extraction=extraction
        )
    except (AiProviderError, ValueError) as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        supabase.table("pathr_resume").update({"status": "failed", "error": detail}).eq(
            "id", resume_id
        ).execute()
        _close_ai_job(supabase, job_id, status="failed", error=detail)
        if isinstance(exc, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Não consegui ler este arquivo: {detail}.",
            ) from exc
        raise

    updated = (
        supabase.table("pathr_resume")
        .update(
            {
                "parsed": cifra.cifrar_json(parsed, cifra.ctx_curriculo_dados(user_id)),
                "status": "parsed",
                "error": None,
                "parsed_at": _now().isoformat(),
            }
        )
        .eq("id", resume_id)
        .execute()
        .data[0]
    )
    _close_ai_job(
        supabase,
        job_id,
        status="done",
        provider=ai_result.provider,
        model=ai_result.model,
        tokens=ai_result.tokens,
        latency_ms=ai_result.latency_ms,
        output={"tecnologias": len(parsed.get("tecnologias") or [])},
    )
    return _public(_decifrado(updated))


def _load_file(supabase: Client, resume: dict) -> Optional[bytes]:
    path = resume.get("storage_path")
    if not path:
        return None
    try:
        dados = supabase.storage.from_(settings.resume_bucket).download(path)
    except Exception:  # noqa: BLE001
        return None
    return cifra.decifrar_bytes(dados, cifra.ctx_arquivo(settings.resume_bucket, path))


def _open_ai_job(supabase: Client, user_id: str, resume_id: str) -> Optional[str]:
    try:
        row = (
            supabase.table("pathr_ai_job")
            .insert(
                {
                    "user_id": user_id,
                    "kind": "resume_parse",
                    "status": "running",
                    "input_ref": resume_id,
                }
            )
            .execute()
            .data[0]
        )
        return str(row["id"])
    except Exception:  # noqa: BLE001 — auditoria não pode derrubar o recurso
        return None


def _close_ai_job(
    supabase: Client,
    job_id: Optional[str],
    *,
    status: str,
    provider: str = "",
    model: str = "",
    tokens: int = 0,
    latency_ms: int = 0,
    output: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    if not job_id:
        return
    try:
        supabase.table("pathr_ai_job").update(
            {
                "status": status,
                "provider": provider or None,
                "model": model or None,
                # O provedor reporta o total; separar prompt de completion
                # exigiria um campo que nem toda API devolve.
                "completion_tokens": tokens,
                "latency_ms": latency_ms,
                "output": output or {},
                "error": error,
                "finished_at": _now().isoformat(),
            }
        ).eq("id", job_id).execute()
    except Exception:  # noqa: BLE001
        pass


@router.post("/{resume_id}/apply")
def apply_resume(
    resume_id: str,
    payload: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Importa as competências revisadas para o perfil.

    O corpo é opcional. Sem ele, entra o que a IA leu; com ele, entra o que a
    pessoa corrigiu na tela de revisão:

        {"tecnologias": [{"nome": "Java", "proficiencia": 2, "is_target": true}],
         "aplicar_perfil": true}

    Cada tecnologia vira (ou atualiza) uma linha em `pathr_user_tag` com
    `source='cv'` e `confidence=0.4` — baixa de propósito: currículo é o que a
    pessoa escreveu sobre si, e um quiz respondido depois sobe essa nota.
    Tecnologia fora do catálogo global cria a tag, então o catálogo cresce com
    o uso real em vez de precisar prever tudo.
    """
    user_id = str(current_user["id"])
    resume = _owned(supabase, resume_id, user_id)
    if resume["status"] != "parsed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Leia o currículo antes de importar as competências.",
        )

    parsed = resume.get("parsed") or {}
    body = payload or {}
    technologies = body.get("tecnologias")
    if not isinstance(technologies, list):
        technologies = parsed.get("tecnologias") or []

    catalog = TagCatalog(supabase).load()
    imported: list[dict[str, Any]] = []
    for item in technologies:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nome") or "").strip()
        if not name:
            continue
        tag = catalog.resolve(name, str(item.get("categoria") or ""))
        proficiency = max(0, min(5, int(item.get("proficiencia") or 0)))
        _upsert_user_tag(
            supabase,
            user_id=user_id,
            tag_id=str(tag["id"]),
            proficiency=proficiency,
            # Sem proficiência comprovada, a tecnologia entra como meta de
            # estudo — é exatamente o que o roadmap precisa cobrir.
            is_target=bool(item.get("is_target", proficiency == 0)),
        )
        imported.append({"tag_id": str(tag["id"]), "slug": tag["slug"], "name": tag["name"],
                         "proficiency": proficiency})

    if body.get("aplicar_perfil", True):
        _apply_profile_fields(supabase, user_id, parsed)

    supabase.table("pathr_resume").update({"is_primary": False}).eq("user_id", user_id).execute()
    supabase.table("pathr_resume").update({"is_primary": True}).eq("id", resume_id).execute()

    _log_activity(supabase, user_id, resume_id, len(imported))
    return {"imported": len(imported), "tags": imported}


def _upsert_user_tag(
    supabase: Client, *, user_id: str, tag_id: str, proficiency: int, is_target: bool
) -> None:
    """Cria ou atualiza a competência do usuário.

    Update em vez de insert cego porque (user_id, tag_id) é UNIQUE e reenviar
    um currículo revisado é caso comum — a segunda importação deve corrigir a
    primeira, não estourar.
    """
    fields = {
        "proficiency": proficiency,
        "confidence": 0.4,
        "source": "cv",
        "is_target": is_target,
        "last_assessed_at": _now().isoformat(),
    }
    existing = (
        supabase.table("pathr_user_tag")
        .select("id")
        .eq("user_id", user_id)
        .eq("tag_id", tag_id)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        supabase.table("pathr_user_tag").update(fields).eq("id", existing[0]["id"]).execute()
    else:
        supabase.table("pathr_user_tag").insert(
            {"user_id": user_id, "tag_id": tag_id, **fields}
        ).execute()


def _apply_profile_fields(supabase: Client, user_id: str, parsed: dict[str, Any]) -> None:
    """Preenche o perfil com o que o currículo trouxe, sem apagar o que a
    pessoa já tinha escrito à mão."""
    current = (
        supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data
    )
    existing = current[0] if current else {}

    candidates = {
        "current_role": parsed.get("cargo_atual"),
        "seniority": parsed.get("senioridade"),
        "years_experience": parsed.get("anos_experiencia") or None,
        "bio": parsed.get("resumo"),
        "linkedin_url": parsed.get("linkedin"),
        "github_url": parsed.get("github"),
    }
    update = {
        field: value
        for field, value in candidates.items()
        if value and not existing.get(field)
    }
    if not update:
        return
    update["updated_at"] = _now().isoformat()
    supabase.table("pathr_profile").update(update).eq("user_id", user_id).execute()


def _log_activity(supabase: Client, user_id: str, resume_id: str, imported: int) -> None:
    try:
        supabase.table("pathr_activity").insert(
            {
                "user_id": user_id,
                "kind": "resume_parsed",
                "ref_id": resume_id,
                "title": f"Currículo lido — {imported} competências importadas",
                "xp": 20,
                "detail": {"imported": imported},
                "activity_date": _now().date().isoformat(),
            }
        ).execute()
    except Exception:  # noqa: BLE001
        pass


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Apaga o currículo e o arquivo. As competências já importadas ficam —
    elas passaram por revisão e agora são do perfil, não do arquivo."""
    resume = _owned(supabase, resume_id, str(current_user["id"]))
    path = resume.get("storage_path")
    if path:
        try:
            supabase.storage.from_(settings.resume_bucket).remove([path])
        except Exception:  # noqa: BLE001
            pass
    supabase.table("pathr_resume").delete().eq("id", resume_id).execute()
