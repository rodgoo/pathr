"""Relatos: reclamações e sugestões, com foto opcional, para a moderação.

Quem usa o app relata em Configurações › Relatar. Quem modera — as contas em
`settings.moderator_emails` — vê todos os relatos na mesma aba, muda o status e
deixa uma nota.

## A foto nunca é uma URL

O desenho óbvio de "anexar captura de tela" é aceitar um endereço de imagem e
mostrá-lo num `<img>` ou num link na tela da moderação. Esse é o caminho de
XSS mais valioso do app: o código roda na sessão de quem MODERA. Aqui:

1. A foto sobe como arquivo e tem a assinatura dos bytes conferida — JPG, PNG
   ou WebP de verdade, não o que o nome ou o cabeçalho dizem.
2. O caminho no bucket é escolhido pelo servidor (`<id do relato>.<ext>`).
3. Ela só sai por GET /relatos/{id}/foto, para o autor e para a moderação,
   com `nosniff` e uma CSP `sandbox` que não deixa nada executar mesmo que um
   arquivo disfarçado passasse pela checagem.

Nenhum texto do relato vira link: mensagem e página chegam à tela como texto,
e o React os escapa.

## Quem não modera não descobre que a moderação existe

As rotas de moderação respondem 404 para qualquer outra conta, e não 403: um
403 confirmaria que a rota existe e que há alguém com mais poder do outro lado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.deps import get_current_user
from app.routers.profile import _IMAGENS, _tipo_real
from app.services import limites
from app.services.moderacao import e_moderador

router = APIRouter(prefix="/relatos", tags=["relatos"])

_TIPOS = {"reclamacao", "sugestao"}
_STATUS = {"aberto", "em_analise", "resolvido"}
_FOTO_MAX_MB = 5


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nao_encontrado(detalhe: str = "Relato não encontrado.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detalhe)


def _publico(relato: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(relato["id"]),
        "kind": relato.get("kind"),
        "message": relato.get("message"),
        "page": relato.get("page"),
        "has_attachment": bool(relato.get("attachment_path")),
        "status": relato.get("status"),
        "moderator_note": relato.get("moderator_note"),
        "created_at": relato.get("created_at"),
        "updated_at": relato.get("updated_at"),
    }


def _guardar_foto(supabase: Client, caminho: str, dados: bytes, tipo: str) -> None:
    """Sobe a foto. Se o bucket ainda não existe, cria privado e tenta de novo.

    Criar na primeira vez em vez de exigir um passo manual antes do deploy:
    um relato perdido porque ninguém rodou o bootstrap é o tipo de falha que
    só aparece quando alguém tenta reclamar de algo.
    """
    bucket = supabase.storage.from_(settings.report_bucket)
    try:
        bucket.upload(caminho, dados, {"content-type": tipo, "upsert": "false"})
        return
    except Exception as exc:  # noqa: BLE001
        if "not found" not in str(exc).lower() and "bucket" not in str(exc).lower():
            raise
    supabase.storage.create_bucket(settings.report_bucket, options={"public": False})
    supabase.storage.from_(settings.report_bucket).upload(
        caminho, dados, {"content-type": tipo, "upsert": "false"}
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def relatar(
    tipo: str = Form(...),
    mensagem: str = Form(...),
    pagina: Optional[str] = Form(default=None),
    foto: Optional[UploadFile] = File(default=None),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Envia um relato. A foto é opcional; se vier, precisa ser imagem de verdade."""
    user_id = str(current_user["id"])
    tipo = (tipo or "").strip().lower()
    mensagem = (mensagem or "").strip()
    if tipo not in _TIPOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escolha reclamação ou sugestão.")
    if len(mensagem) < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conte um pouco mais: ao menos 10 caracteres.")
    if len(mensagem) > 3000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use no máximo 3000 caracteres.")

    dados: Optional[bytes] = None
    tipo_foto: Optional[str] = None
    if foto is not None and (foto.filename or foto.size):
        dados = await foto.read()
        if dados:
            if len(dados) > _FOTO_MAX_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Imagem acima de {_FOTO_MAX_MB} MB.",
                )
            tipo_foto = _tipo_real(dados)
            if tipo_foto is None:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="A foto precisa ser JPG, PNG ou WebP.",
                )
        else:
            dados = None

    # Depois das validações: um formulário com erro não gasta a cota do dia.
    limites.consumir(supabase, limites.RELATO_POR_USUARIO, user_id)

    linha = (
        supabase.table("pathr_report")
        .insert(
            {
                "user_id": user_id,
                "kind": tipo,
                "message": mensagem,
                "page": (pagina or "").strip()[:60] or None,
                "status": "aberto",
            }
        )
        .execute()
        .data[0]
    )

    if dados and tipo_foto:
        caminho = f"{linha['id']}.{_IMAGENS[tipo_foto]}"
        try:
            _guardar_foto(supabase, caminho, dados, tipo_foto)
        except Exception:  # noqa: BLE001
            # O relato vale sem a foto; perder o texto porque o anexo falhou
            # seria perder a reclamação inteira. A pessoa é avisada.
            return {**_publico(linha), "aviso": "O relato foi enviado, mas a foto não pôde ser guardada."}
        linha = (
            supabase.table("pathr_report")
            .update({"attachment_path": caminho, "attachment_type": tipo_foto})
            .eq("id", linha["id"])
            .execute()
            .data
            or [linha]
        )[0]
    return _publico(linha)


@router.get("/meus")
def meus_relatos(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    linhas = (
        supabase.table("pathr_report").select("*").eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True).limit(50).execute().data or []
    )
    return [_publico(linha) for linha in linhas]


# ---------------------------------------------------------------------------
# Moderação
# ---------------------------------------------------------------------------


def _so_moderacao(user: dict[str, Any]) -> None:
    if not e_moderador(user):
        raise _nao_encontrado("Não encontrado.")


def _id_valido(relato_id: str) -> str:
    try:
        return str(UUID(relato_id))
    except ValueError as exc:
        raise _nao_encontrado() from exc


@router.get("/moderacao")
def listar_para_moderacao(
    situacao: str = Query("abertos", pattern="^(abertos|todos|resolvidos)$"),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Os relatos de todo mundo, com quem relatou — só para a moderação."""
    _so_moderacao(current_user)
    consulta = supabase.table("pathr_report").select("*")
    if situacao == "abertos":
        consulta = consulta.neq("status", "resolvido")
    elif situacao == "resolvidos":
        consulta = consulta.eq("status", "resolvido")
    linhas = consulta.order("created_at", desc=True).limit(200).execute().data or []

    autores = {
        str(u["id"]): u
        for u in (
            supabase.table("pathr_user").select("id,name,username,email")
            .in_("id", list({str(l["user_id"]) for l in linhas}) or ["00000000-0000-0000-0000-000000000000"])
            .execute().data or []
        )
    }
    saida = []
    for linha in linhas:
        autor = autores.get(str(linha["user_id"]), {})
        saida.append(
            {
                **_publico(linha),
                # O e-mail aparece para a moderação porque responder a quem
                # relatou é parte do trabalho; nenhuma outra conta o recebe.
                "author": {
                    "name": autor.get("name"),
                    "username": autor.get("username"),
                    "email": autor.get("email"),
                },
            }
        )
    return saida


class Moderacao(BaseModel):
    status: str = Field(pattern="^(aberto|em_analise|resolvido)$")
    moderator_note: Optional[str] = Field(default=None, max_length=2000)


@router.patch("/{relato_id}")
def moderar(
    relato_id: str,
    payload: Moderacao,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _so_moderacao(current_user)
    relato_id = _id_valido(relato_id)
    atualizadas = (
        supabase.table("pathr_report")
        .update(
            {
                "status": payload.status,
                "moderator_note": (payload.moderator_note or "").strip() or None,
                "updated_at": _agora(),
            }
        )
        .eq("id", relato_id)
        .execute()
        .data
    )
    if not atualizadas:
        raise _nao_encontrado()
    return _publico(atualizadas[0])


@router.get("/{relato_id}/foto")
def foto_do_relato(
    relato_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """A foto do relato, para quem relatou e para a moderação. Para mais ninguém."""
    relato_id = _id_valido(relato_id)
    linhas = supabase.table("pathr_report").select("*").eq("id", relato_id).limit(1).execute().data or []
    relato = linhas[0] if linhas else None
    if (
        not relato
        or not relato.get("attachment_path")
        or (str(relato["user_id"]) != str(current_user["id"]) and not e_moderador(current_user))
    ):
        raise _nao_encontrado("Foto não encontrada.")
    tipo = relato.get("attachment_type")
    if tipo not in _IMAGENS:
        raise _nao_encontrado("Foto não encontrada.")
    try:
        dados = supabase.storage.from_(settings.report_bucket).download(relato["attachment_path"])
    except Exception as exc:  # noqa: BLE001
        raise _nao_encontrado("Foto não encontrada.") from exc
    # Conferida de novo na saída: o que está no bucket é o que vai para a tela
    # de quem modera, e um arquivo trocado lá por fora não pode chegar como
    # outra coisa.
    if _tipo_real(dados) != tipo:
        raise _nao_encontrado("Foto não encontrada.")
    return Response(
        content=dados,
        media_type=tipo,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="relato.{_IMAGENS[tipo]}"',
            # Vale mesmo em desenvolvimento, onde a CSP global fica de fora:
            # nesta resposta nada executa, nem se for aberta direto na aba.
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )
