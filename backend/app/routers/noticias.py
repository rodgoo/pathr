"""Notícias: eventos de tecnologia perto da pessoa.

- `GET  /noticias` — os eventos futuros perto da cidade do perfil (ou de
  qualquer lugar, sem cidade cadastrada), atualizando a região primeiro se
  fizer tempo que ninguém buscou (ver services/noticias.atualizar_regiao).
- `POST /noticias/{id}/presenca` — o "Eu vou!".
- `DELETE /noticias/{id}/presenca` — desfaz.
- `GET  /noticias/{id}/calendario.ics` — o arquivo para o "Adicionar ao
  calendário" da tela.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services import features, limites, noticias

# Cada varredura é busca paga (Tavily/Brave) e dezenas de chamadas de IA, e a
# cidade do perfil é texto livre: sem um teto por conta, trocar a cidade e
# reabrir a tela dispararia varreduras novas sem parar, driblando o cache de
# 12 h que é POR cidade.
BUSCA_DE_EVENTOS = limites.Regra(
    "busca-eventos",
    1,
    timedelta(minutes=30),
    "Você já buscou eventos há pouco. Tente de novo daqui a alguns minutos.",
)


def recurso_ligado(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Recusa quem não tem o recurso "noticias" ligado — no SERVIDOR, não só na
    navegação (mesmo padrão de routers/candidaturas.py).

    404 e não 403: para quem não tem o recurso, ele não existe.
    """
    if not features.habilitadas_para(current_user, supabase).get("noticias", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso indisponível.")
    return current_user


router = APIRouter(
    prefix="/noticias",
    tags=["notícias"],
    # No router, e não em cada rota: rota nova nasce fechada.
    dependencies=[Depends(recurso_ligado)],
)

# O mesmo padrão da tela de Vagas (RAIO_PADRAO_KM no frontend): sem escolha
# própria da pessoa, 50 km é o que separa "perto o bastante para ir" de
# "a cidade inteira do estado".
_RAIO_PADRAO_KM = 50.0


def _id_valido(event_id: str) -> None:
    """id malformado não pode virar erro do PostgREST não tratado (500
    genérico pelo middleware) — mesmo padrão de quizzes.py._id_valido,
    relatos.py._id_valido e social.py._convite_de."""
    try:
        uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado.")


def _evento_da_pessoa(supabase: Client, user_id: str, event_id: str) -> dict:
    """O evento futuro, se existir — 404 e não 403: um id adivinhado não pode
    confirmar que o evento existe."""
    _id_valido(event_id)
    linhas = (
        supabase.table("pathr_news_event").select("*").eq("id", event_id).limit(1).execute().data or []
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado.")
    return linhas[0]


@router.get("")
def listar(
    fundo: BackgroundTasks,
    raio_km: float = Query(_RAIO_PADRAO_KM, ge=0, le=1000),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Os eventos que já estão no banco — AGORA — e a varredura em segundo plano.

    Antes, a busca e a leitura das páginas aconteciam DENTRO desta requisição:
    dezenas de páginas e chamadas de IA, minutos de espera, e a tela presa num
    "Buscando eventos…" que muitas vezes nunca terminava (e, quando a
    requisição morria, nada ficava gravado — a abertura seguinte recomeçava do
    zero).

    Agora a resposta sai na hora com o que existe, e `atualizando` diz à tela
    que vale reconsultar em instantes. É a mesma escolha da fila de vagas: o
    trabalho pesado não mora no caminho da tela.
    """
    user_id = str(current_user["id"])
    perfil = (
        supabase.table("pathr_profile").select("city,state").eq("user_id", user_id).limit(1).execute().data
        or [{}]
    )[0]
    cidade, uf = perfil.get("city"), perfil.get("state")

    atualizando = noticias.precisa_buscar(supabase, cidade, uf)
    if atualizando:
        # Teto por conta. Estourado, a lista sai igual, só sem disparar outra
        # varredura: 429 aqui deixaria a tela sem os eventos que já existem.
        try:
            limites.consumir(supabase, BUSCA_DE_EVENTOS, user_id)
        except HTTPException as erro:
            if erro.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
            atualizando = False

    if atualizando:
        # Roda depois da resposta sair, no mesmo processo. `atualizar_regiao`
        # marca a região antes de começar, então duas telas abertas juntas não
        # disparam duas varreduras.
        fundo.add_task(noticias.varrer_em_fundo, supabase, cidade, uf)

    return {
        "eventos": noticias.listar_por_regiao(supabase, user_id, cidade, uf, raio_km),
        "atualizando": atualizando,
    }


@router.post("/{event_id}/presenca", status_code=status.HTTP_204_NO_CONTENT)
def confirmar(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _evento_da_pessoa(supabase, str(current_user["id"]), event_id)
    noticias.confirmar_presenca(supabase, str(current_user["id"]), event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{event_id}/presenca", status_code=status.HTTP_204_NO_CONTENT)
def desfazer(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _id_valido(event_id)
    noticias.cancelar_presenca(supabase, str(current_user["id"]), event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{event_id}/calendario.ics")
def calendario(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    evento = _evento_da_pessoa(supabase, str(current_user["id"]), event_id)
    publicado = {
        "id": str(evento["id"]),
        "titulo": evento.get("title"),
        "resumo": evento.get("summary"),
        "local": evento.get("venue"),
        "data_inicio": evento.get("event_start"),
        "data_fim": evento.get("event_end"),
        "url_ingresso": evento.get("ticket_url"),
    }
    return Response(
        content=noticias.gerar_ics(publicado),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{event_id}.ics"'},
    )
