"""Feature flags: cada recurso do app ligado para Todos, só Admin, ou Ninguém.

## Por que um registro em código, e não só uma tabela

O `REGISTRO` abaixo é a lista do que EXISTE — a fonte da verdade de quais
flags o app conhece, com rótulo, descrição e o estado padrão de cada um. Um
recurso novo nasce aqui, com um padrão seguro (em geral "admin", para o dono
testar antes de abrir). A tabela `pathr_feature_flag` guarda só o que foi
MUDADO na tela de admin — uma linha por override. Flag sem linha usa o padrão
do registro.

Assim: apagar a tabela não some com nenhum recurso (volta ao padrão), e um
recurso removido do código simplesmente ignora a linha órfã.

## Quem decide

A resolução é sempre no SERVIDOR. A tela recebe só o mapa `{chave: ligado}`
para o usuário atual (`GET /features`); nunca o estado cru nem a regra. "admin"
quer dizer super admin (services/moderacao.e_super_admin) — é o "somente admin"
que o dono pediu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from supabase import Client

from app.services.moderacao import e_super_admin

# Os três estados que um flag pode ter. Ordem = a ordem do toggle na tela.
ESTADOS = ("todos", "admin", "ninguem")


@dataclass(frozen=True)
class Recurso:
    chave: str
    rotulo: str
    descricao: str
    padrao: str  # um de ESTADOS


# O catálogo. Recurso novo entra aqui. Padrão "admin" = só o dono vê até abrir.
REGISTRO: tuple[Recurso, ...] = (
    Recurso(
        "candidaturas",
        "Candidaturas",
        "Fila diária de vagas, carta de apresentação sob medida e envio automático "
        "do currículo por e-mail para as vagas com contato.",
        "admin",
    ),
    Recurso(
        "noticias",
        "Notícias",
        "Eventos e anúncios de tecnologia perto da cidade da pessoa, com prazo de "
        "inscrição, adicionar ao calendário e confirmação de presença.",
        "todos",
    ),
)

_POR_CHAVE = {r.chave: r for r in REGISTRO}


def _overrides(supabase: Client) -> dict[str, str]:
    """Os estados gravados na tela de admin. Falha de leitura não derruba nada:
    sem override, cada flag fica no padrão do registro."""
    try:
        linhas = supabase.table("pathr_feature_flag").select("key,state").execute().data or []
    except Exception:  # noqa: BLE001
        return {}
    return {
        str(l["key"]): str(l["state"])
        for l in linhas
        if str(l.get("key")) in _POR_CHAVE and str(l.get("state")) in ESTADOS
    }


def estados(supabase: Client) -> dict[str, str]:
    """Estado atual de cada flag conhecido: o padrão do registro com o override
    do banco por cima."""
    base = {r.chave: r.padrao for r in REGISTRO}
    base.update(_overrides(supabase))
    return base


def _ligado(estado: str, admin: bool) -> bool:
    if estado == "todos":
        return True
    if estado == "admin":
        return admin
    return False  # ninguem


def habilitadas_para(user: dict[str, Any], supabase: Client) -> dict[str, bool]:
    """`{chave: ligado}` para ESTE usuário — o que a tela precisa e só isso."""
    admin = e_super_admin(user)
    return {chave: _ligado(estado, admin) for chave, estado in estados(supabase).items()}


def catalogo_para_admin(supabase: Client) -> list[dict[str, Any]]:
    """A lista completa para a tela de admin: rótulo, descrição, estado e padrão."""
    atuais = estados(supabase)
    return [
        {
            "key": r.chave,
            "label": r.rotulo,
            "description": r.descricao,
            "state": atuais[r.chave],
            "default": r.padrao,
        }
        for r in REGISTRO
    ]


def existe(chave: str) -> bool:
    return chave in _POR_CHAVE
