"""Pessoas: nome de usuário, amizades e quem sugerir.

## O que outra conta vê

Um **cartão**: nome, @username, foto, cidade e UF, objetivo, senioridade e as
tecnologias em que a pessoa está. Nunca e-mail, data de nascimento ou
qualquer coisa de que a conta dependa para entrar. O cartão é o mesmo em
sugestão, busca e lista de amigos — um formato só é um lugar só para errar.

## Quem aparece

- **Sugestões**: só quem deixou `discoverable` ligado. A ordem vem da
  proximidade (mesma cidade, depois mesma UF) e do que as duas pessoas têm em
  comum (tecnologias, objetivo).
- **Busca**: parcial por nome ou @username, também só entre as encontráveis.
  O @username EXATO acha qualquer conta — é como alguém que recebeu o seu
  @ numa conversa te adiciona, e é o que "não aparecer nas sugestões" não
  deveria impedir.

## Por que recusar apaga

Um convite recusado some, e não vira uma linha "recusado". Guardar a recusa
deixaria quem convidou descobrir, numa segunda tentativa, que foi recusado —
e é informação que só serve para constranger.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.deps import client_ip, get_current_user
from app.services import cifra, limites, sequencia_dupla, usernames
from app.services.progress import local_today

router = APIRouter(prefix="/social", tags=["pessoas"])

# Quantas tecnologias vão no cartão. Mais que isso vira parágrafo, e o cartão
# existe para ser lido de relance numa lista.
_STACK_NO_CARTAO = 5


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Nome de usuário
# ---------------------------------------------------------------------------


def ocupados(supabase: Client, nomes: list[str], exceto_user_id: Optional[str] = None) -> set[str]:
    """Dos nomes dados, os que já têm dono. Uma consulta por lote."""
    if not nomes:
        return set()
    linhas = (
        supabase.table("pathr_user")
        .select("id,username")
        .in_("username", [usernames.normalizar(n) for n in nomes])
        .execute()
        .data
        or []
    )
    return {
        str(linha["username"]).lower()
        for linha in linhas
        if not exceto_user_id or str(linha["id"]) != exceto_user_id
    }


def gerar_para(supabase: Client, nome_completo: str) -> str:
    """Um nome livre derivado do nome completo — o de quem pulou a escolha."""
    escolhido = usernames.primeiro_livre(
        usernames.candidatos(nome_completo), lambda lote: ocupados(supabase, lote)
    )
    # Com 500 candidatos esgotados só sobra um sufixo que ninguém terá.
    if escolhido is None:
        from secrets import token_hex

        escolhido = f"{usernames.candidatos(nome_completo)[0][:17]}_{token_hex(3)}"
    return escolhido


class Disponibilidade(BaseModel):
    username: str
    disponivel: bool
    problema: Optional[str] = None
    sugestoes: list[str] = []


def _disponibilidade(
    supabase: Client, desejado: str, nome: str, exceto: Optional[str] = None
) -> Disponibilidade:
    alvo = usernames.normalizar(desejado)
    problema = usernames.problema(alvo)
    livre = problema is None and alvo not in ocupados(supabase, [alvo], exceto)
    sugestoes: list[str] = []
    if not livre:
        possiveis = usernames.sugestoes_para(alvo, nome) if problema is None else usernames.candidatos(nome or alvo)
        tomados = ocupados(supabase, possiveis[:40], exceto)
        sugestoes = [s for s in possiveis[:40] if s not in tomados][:4]
    return Disponibilidade(
        username=alvo,
        disponivel=livre,
        problema=problema or (None if livre else "Este nome de usuário já está em uso."),
        sugestoes=sugestoes,
    )


@router.get("/username/disponivel", response_model=Disponibilidade)
def username_disponivel(
    request: Request,
    username: str = Query("", max_length=40),
    nome: str = Query("", max_length=120),
    supabase: Client = Depends(get_supabase),
):
    """Confere um nome de usuário e sugere alternativas — sem precisar de conta.

    Aberta porque o cadastro precisa dela antes de haver sessão. É também o
    jeito mais barato de alguém testar quais @ existem, por isso o limite por
    IP. O que ela revela ("este @ existe") já é público no próprio produto.
    """
    limites.consumir(supabase, limites.USERNAME_POR_IP, client_ip(request))
    if not username.strip():
        candidatos = usernames.candidatos(nome) if nome.strip() else []
        tomados = ocupados(supabase, candidatos[:40])
        livres = [c for c in candidatos[:40] if c not in tomados]
        return Disponibilidade(
            username="", disponivel=False, problema=None, sugestoes=livres[:4]
        )
    return _disponibilidade(supabase, username, nome)


class TrocaDeUsername(BaseModel):
    username: str = Field(min_length=1, max_length=40)


@router.put("/username", response_model=Disponibilidade)
def trocar_username(
    payload: TrocaDeUsername,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Troca o próprio @. Ocupado ou inválido devolve 409 com sugestões."""
    user_id = str(current_user["id"])
    resultado = _disponibilidade(supabase, payload.username, current_user.get("name") or "", user_id)
    if resultado.username == str(current_user.get("username") or "").lower():
        return Disponibilidade(username=resultado.username, disponivel=True)
    if not resultado.disponivel:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"mensagem": resultado.problema, "sugestoes": resultado.sugestoes},
        )
    try:
        supabase.table("pathr_user").update({"username": resultado.username}).eq("id", user_id).execute()
    except Exception as exc:  # noqa: BLE001
        # O índice único recusou: outra pessoa pegou o nome entre a checagem e
        # a gravação.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"mensagem": "Este nome de usuário acabou de ser escolhido por outra pessoa.",
                    "sugestoes": resultado.sugestoes},
        ) from exc
    return resultado


class Privacidade(BaseModel):
    discoverable: bool


@router.get("/privacidade", response_model=Privacidade)
def ler_privacidade(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    linhas = (
        supabase.table("pathr_profile").select("discoverable")
        .eq("user_id", str(current_user["id"])).limit(1).execute().data or []
    )
    return Privacidade(discoverable=bool((linhas[0] if linhas else {}).get("discoverable", True)))


@router.put("/privacidade", response_model=Privacidade)
def gravar_privacidade(
    payload: Privacidade,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    supabase.table("pathr_profile").update({"discoverable": payload.discoverable}).eq(
        "user_id", str(current_user["id"])
    ).execute()
    return payload


# ---------------------------------------------------------------------------
# Cartões
# ---------------------------------------------------------------------------

_NENHUM_ID = "00000000-0000-0000-0000-000000000000"

# Caracteres que o filtro `or=(...)` do PostgREST interpreta como sintaxe:
# numa busca, uma vírgula ou um parêntese digitado viraria operador, e um `*`
# ou `%` viraria curinga para listar todo mundo.
_SINTAXE_DO_FILTRO = frozenset("%_*,().:\\")


def _relacoes(supabase: Client, user_id: str) -> dict[str, dict[str, Any]]:
    """Toda amizade e todo convite da pessoa, pelo id da outra ponta."""
    linhas = (
        supabase.table("pathr_friendship")
        .select("*")
        .or_(f"requester_id.eq.{user_id},addressee_id.eq.{user_id}")
        .execute()
        .data
        or []
    )
    saida: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        pediu = str(linha["requester_id"])
        outro = str(linha["addressee_id"]) if pediu == user_id else pediu
        if linha["status"] == "accepted":
            relacao = "amigos"
        elif pediu == user_id:
            relacao = "enviado"
        else:
            relacao = "recebido"
        saida[outro] = {"relacao": relacao, "friendship_id": str(linha["id"])}
    return saida


def _cartoes(
    supabase: Client, user_ids: list[str], relacoes: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Os cartões de várias pessoas, em quatro consultas — não quatro por pessoa."""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    usuarios = (
        supabase.table("pathr_user").select("id,name,username,avatar_path")
        .in_("id", ids).execute().data or []
    )
    perfis = {
        str(p["user_id"]): p
        for p in (
            supabase.table("pathr_profile")
            .select("user_id,city,state,target_role,headline,current_role,seniority")
            .in_("user_id", ids).execute().data or []
        )
    }
    competencias = (
        supabase.table("pathr_user_tag").select("user_id,tag_id,proficiency")
        .in_("user_id", ids).execute().data or []
    )
    ids_de_tag = list({str(c["tag_id"]) for c in competencias}) or [_NENHUM_ID]
    nomes_de_tag = {
        str(t["id"]): t["name"]
        for t in (
            supabase.table("pathr_tag").select("id,name").in_("id", ids_de_tag).execute().data or []
        )
    }
    por_usuario: dict[str, list[dict[str, Any]]] = {}
    for item in competencias:
        por_usuario.setdefault(str(item["user_id"]), []).append(item)

    cartoes: dict[str, dict[str, Any]] = {}
    for usuario in usuarios:
        uid = str(usuario["id"])
        perfil = perfis.get(uid, {})
        # Stack: o que a pessoa domina mais primeiro. É o que outra pessoa
        # quer saber para decidir se aquele contato ajuda no que ela estuda.
        tags = sorted(por_usuario.get(uid, []), key=lambda c: -(c.get("proficiency") or 0))
        stack = [nomes_de_tag[str(t["tag_id"])] for t in tags if str(t["tag_id"]) in nomes_de_tag]
        relacao = relacoes.get(uid, {})
        cartoes[uid] = {
            "username": usuario.get("username"),
            "name": usuario.get("name"),
            "has_avatar": bool(usuario.get("avatar_path")),
            "city": perfil.get("city"),
            "state": perfil.get("state"),
            "objetivo": perfil.get("target_role") or perfil.get("headline"),
            "cargo": perfil.get("current_role"),
            "senioridade": perfil.get("seniority"),
            "stack": stack[:_STACK_NO_CARTAO],
            "relacao": relacao.get("relacao", "nenhuma"),
            "friendship_id": relacao.get("friendship_id"),
            "_tag_ids": {str(t["tag_id"]) for t in tags},
            "_ids_por_nome": {
                nomes_de_tag[str(t["tag_id"])]: str(t["tag_id"]) for t in tags if str(t["tag_id"]) in nomes_de_tag
            },
        }
    return cartoes


def _publico(cartao: dict[str, Any], minhas_tags: set[str] | None = None) -> dict[str, Any]:
    """O cartão sem os campos internos, com o que as duas contas têm em comum.

    `em_comum` são os nomes do `stack` do cartão que quem olha também tem;
    `mesma_stack` diz se os dois conjuntos de tecnologias são iguais. Sai
    daqui, e não da tela, porque só o servidor sabe as tags de quem olha sem
    uma consulta a mais.
    """
    publico = {k: v for k, v in cartao.items() if not k.startswith("_")}
    minhas = minhas_tags or set()
    dele = cartao.get("_tag_ids") or set()
    comuns = dele & minhas
    publico["em_comum"] = [
        nome for nome in cartao.get("stack") or [] if cartao.get("_ids_por_nome", {}).get(nome) in comuns
    ]
    publico["mesma_stack"] = bool(dele) and dele == minhas
    return publico


def _minhas_tags(supabase: Client, user_id: str) -> set[str]:
    return {
        str(linha["tag_id"])
        for linha in supabase.table("pathr_user_tag").select("tag_id").eq("user_id", user_id).execute().data or []
    }


def _palavras(texto: Optional[str]) -> set[str]:
    return {p for p in re.findall(r"[a-zà-ú0-9]+", (texto or "").lower()) if len(p) > 2}


def pontuar(eu: dict[str, Any], outro: dict[str, Any]) -> float:
    """O quanto vale sugerir `outro` para `eu`.

    Proximidade pesa mais que afinidade: a localidade foi o critério pedido, e
    é a que abre porta para estudar junto, evento, indicação de vaga. Afinidade
    desempata — duas pessoas da mesma cidade estudando Java aparecem antes de
    uma que estuda Excel.
    """
    minha_uf = (eu.get("state") or "").strip().lower()
    minha_cidade = (eu.get("city") or "").strip().lower()
    pontos = 0.0
    if minha_uf and minha_uf == (outro.get("state") or "").strip().lower():
        pontos += 6 if minha_cidade and minha_cidade == (outro.get("city") or "").strip().lower() else 3
    em_comum = len(eu.get("_tag_ids", set()) & outro.get("_tag_ids", set()))
    pontos += min(em_comum, 5) * 0.8
    if _palavras(eu.get("objetivo")) & _palavras(outro.get("objetivo")):
        pontos += 1.5
    return pontos


@router.get("/pessoas/sugestoes")
def sugestoes(
    limit: int = Query(12, ge=1, le=30),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Quem a pessoa talvez conheça ou queira conhecer: perto, e parecido."""
    user_id = str(current_user["id"])
    relacoes = _relacoes(supabase, user_id)
    meu_perfil = (
        supabase.table("pathr_profile").select("state").eq("user_id", user_id)
        .limit(1).execute().data or [{}]
    )[0]

    # Primeiro quem é da mesma UF, depois o resto — até 300 candidatos. Em
    # base grande é o recorte que mantém a pontuação barata; em base pequena,
    # pega todo mundo.
    candidatos: list[str] = []
    for mesma_uf in (True, False):
        consulta = (
            supabase.table("pathr_profile").select("user_id")
            .eq("discoverable", True).neq("user_id", user_id)
        )
        if mesma_uf:
            if not meu_perfil.get("state"):
                continue
            consulta = consulta.eq("state", meu_perfil["state"])
        for linha in consulta.limit(300).execute().data or []:
            uid = str(linha["user_id"])
            if uid not in candidatos and uid not in relacoes:
                candidatos.append(uid)
        if len(candidatos) >= 300:
            break

    cartoes = _cartoes(supabase, [user_id, *candidatos[:300]], relacoes)
    eu = cartoes.get(user_id, {})
    ordenados = sorted(
        (cartoes[c] for c in candidatos[:300] if c in cartoes),
        key=lambda cartao: -pontuar(eu, cartao),
    )
    return [_publico(c, eu.get("_tag_ids")) for c in ordenados[:limit]]


@router.get("/pessoas/busca")
def buscar(
    q: str = Query(..., min_length=2, max_length=40),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Por @username ou nome. O @ exato acha qualquer conta; o resto, só as encontráveis."""
    user_id = str(current_user["id"])
    limites.consumir(supabase, limites.BUSCA_POR_USUARIO, user_id)
    termo = usernames.normalizar(q)
    # Fora os caracteres que o filtro do PostgREST interpreta: numa busca, uma
    # vírgula ou parêntese digitado viraria sintaxe, não texto.
    seguro = "".join(letra for letra in q.strip().lstrip("@") if letra not in _SINTAXE_DO_FILTRO)
    if len(seguro) < 2:
        return []

    exatos = (
        supabase.table("pathr_user").select("id").eq("username", termo)
        .limit(1).execute().data or []
    )
    parciais = (
        supabase.table("pathr_user").select("id")
        .or_(f"username.ilike.{seguro}*,name.ilike.*{seguro}*")
        .limit(40).execute().data or []
    )
    ids_parciais = [str(linha["id"]) for linha in parciais]
    encontraveis = {
        str(p["user_id"])
        for p in (
            supabase.table("pathr_profile").select("user_id").eq("discoverable", True)
            .in_("user_id", ids_parciais or [_NENHUM_ID]).execute().data or []
        )
    }
    ids = [str(linha["id"]) for linha in exatos] + [i for i in ids_parciais if i in encontraveis]
    ids = [i for i in dict.fromkeys(ids) if i != user_id][:20]
    cartoes = _cartoes(supabase, ids, _relacoes(supabase, user_id))
    minhas = _minhas_tags(supabase, user_id)
    return [_publico(cartoes[i], minhas) for i in ids if i in cartoes]


# ---------------------------------------------------------------------------
# Amizade
# ---------------------------------------------------------------------------


def _id_por_username(supabase: Client, username: str) -> str:
    linhas = (
        supabase.table("pathr_user").select("id")
        .eq("username", usernames.normalizar(username)).limit(1).execute().data or []
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pessoa não encontrada.")
    return str(linhas[0]["id"])


@router.get("/amigos")
def listar_amigos(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Amigos, convites recebidos e convites enviados — separados."""
    user_id = str(current_user["id"])
    relacoes = _relacoes(supabase, user_id)
    cartoes = _cartoes(supabase, list(relacoes), relacoes)
    minhas = _minhas_tags(supabase, user_id)
    grupos: dict[str, list[dict[str, Any]]] = {"amigos": [], "recebidos": [], "enviados": []}
    chave = {"amigos": "amigos", "recebido": "recebidos", "enviado": "enviados"}
    # A sequência em dupla só existe entre amigos: ela revela em que dias a
    # outra pessoa estudou (ver services/sequencia_dupla.py).
    hoje = local_today(current_user.get("timezone_name"))
    meus_dias: set | None = None
    for outro, relacao in relacoes.items():
        if outro not in cartoes:
            continue
        cartao = _publico(cartoes[outro], minhas)
        if relacao["relacao"] == "amigos":
            if meus_dias is None:
                meus_dias = sequencia_dupla.dias_de_estudo(supabase, user_id, hoje)
            cartao["sequencia"] = sequencia_dupla.calcular(
                meus_dias, sequencia_dupla.dias_de_estudo(supabase, outro, hoje), hoje
            )
        grupos[chave[relacao["relacao"]]].append(cartao)
    for lista in grupos.values():
        lista.sort(key=lambda c: (c.get("name") or "").lower())
    return grupos


@router.post("/amigos/{username}", status_code=status.HTTP_201_CREATED)
def convidar(
    username: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Convida. Se a outra pessoa já tinha convidado, vira amizade na hora.

    Aceitar o convite cruzado em vez de recusar o segundo: as duas pessoas
    querem a mesma coisa, e dizer "ela já te convidou, vá aceitar" seria pôr
    burocracia entre duas pessoas que concordam.
    """
    user_id = str(current_user["id"])
    outro = _id_por_username(supabase, username)
    if outro == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode se adicionar.")

    existente = _relacoes(supabase, user_id).get(outro)
    if existente:
        if existente["relacao"] == "recebido":
            supabase.table("pathr_friendship").update(
                {"status": "accepted", "responded_at": _agora()}
            ).eq("id", existente["friendship_id"]).execute()
            return {"relacao": "amigos"}
        return {"relacao": existente["relacao"]}

    limites.consumir(supabase, limites.CONVITE_POR_USUARIO, user_id)
    try:
        supabase.table("pathr_friendship").insert(
            # `status` explícito, e não o default do banco: a regra de quem
            # pode aceitar lê este campo, e ela não pode depender de o padrão
            # da coluna nunca mudar.
            {"requester_id": user_id, "addressee_id": outro, "status": "pending"}
        ).execute()
    except Exception:  # noqa: BLE001
        # O índice do par recusou: um convite cruzado chegou no mesmo instante.
        # O estado real está no banco; responder com ele é mais honesto que 500.
        return {"relacao": _relacoes(supabase, user_id).get(outro, {}).get("relacao", "enviado")}
    return {"relacao": "enviado"}


def _convite_de(supabase: Client, friendship_id: str, user_id: str) -> dict[str, Any]:
    """O convite, se a pessoa é uma das pontas dele. Senão, 404 — e não 403.

    403 diria que o convite existe e é de outra pessoa; um id adivinhado não
    pode confirmar nem isso.
    """
    try:
        UUID(friendship_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite não encontrado.")
    linhas = (
        supabase.table("pathr_friendship").select("*").eq("id", friendship_id)
        .or_(f"requester_id.eq.{user_id},addressee_id.eq.{user_id}")
        .limit(1).execute().data or []
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite não encontrado.")
    return linhas[0]


@router.post("/convites/{friendship_id}/aceitar")
def aceitar(
    friendship_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Só quem RECEBEU aceita. Quem enviou não pode aceitar o próprio convite."""
    user_id = str(current_user["id"])
    convite = _convite_de(supabase, friendship_id, user_id)
    if str(convite["addressee_id"]) != user_id or convite["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite não encontrado.")
    supabase.table("pathr_friendship").update(
        {"status": "accepted", "responded_at": _agora()}
    ).eq("id", friendship_id).eq("addressee_id", user_id).execute()
    return {"relacao": "amigos"}


@router.delete("/convites/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
def recusar_ou_cancelar(
    friendship_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Recusar (quem recebeu), cancelar (quem enviou) ou desfazer a amizade.

    Os três apagam a linha. Ver o topo do arquivo sobre por que a recusa não
    fica registrada.
    """
    user_id = str(current_user["id"])
    _convite_de(supabase, friendship_id, user_id)
    supabase.table("pathr_friendship").delete().eq("id", friendship_id).or_(
        f"requester_id.eq.{user_id},addressee_id.eq.{user_id}"
    ).execute()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pessoas/{username}/avatar")
def avatar_de(
    username: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """A foto de outra pessoa — só se ela é encontrável ou tem relação com você.

    Pela API e não por URL pública do bucket, pelo mesmo motivo da foto
    própria: quem não está logado não alcança a foto de ninguém. E quem se
    escondeu das sugestões não fica com a foto exposta a qualquer conta que
    adivinhe o @.
    """
    user_id = str(current_user["id"])
    linhas = (
        supabase.table("pathr_user").select("id,avatar_path")
        .eq("username", usernames.normalizar(username)).limit(1).execute().data or []
    )
    alvo = linhas[0] if linhas else None
    if not alvo or not alvo.get("avatar_path"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil.")
    outro = str(alvo["id"])
    if outro != user_id and outro not in _relacoes(supabase, user_id):
        perfil = (
            supabase.table("pathr_profile").select("discoverable").eq("user_id", outro)
            .limit(1).execute().data or [{}]
        )[0]
        if not perfil.get("discoverable", True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil.")
    try:
        dados = cifra.decifrar_bytes(
            supabase.storage.from_(settings.avatar_bucket).download(alvo["avatar_path"]),
            cifra.ctx_arquivo(settings.avatar_bucket, alvo["avatar_path"]),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil.") from exc
    extensao = str(alvo["avatar_path"]).rsplit(".", 1)[-1].lower()
    tipo = {"png": "image/png", "webp": "image/webp"}.get(extensao, "image/jpeg")
    return Response(content=dados, media_type=tipo, headers={"Cache-Control": "private, max-age=300"})
