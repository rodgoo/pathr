"""Avisos de "algo mudou", para as telas abertas em outros aparelhos.

O PathR guarda tudo no servidor, então quem ABRE uma tela já vê o estado
certo. O buraco é a tela que já estava aberta: marcar um módulo no celular
não mexia no notebook que ficou no ar a manhã inteira. Este módulo fecha esse
buraco.

## O que trafega

Nada de conteúdo. O aviso é só ``{"rota": "/roadmap/nodes/x", "origem": …}``
— um empurrão para o cliente reconsultar o que ele já sabe pedir. Mandar o
dado pelo canal criaria uma segunda forma de o cliente aprender a verdade, e
duas formas divergem: a primeira vez que um endpoint mudasse de formato,
metade das telas veria um formato e metade o outro. O canal diz *quando*
perguntar; *o que* continua vindo pelas rotas de sempre.

## Três camadas, e cada uma cai sozinha

1. **Fila em memória por conexão.** É o que entrega o aviso a quem está
   ouvindo NESTE processo.
2. **`LISTEN/NOTIFY` do Postgres.** É o que leva o aviso deste processo aos
   outros. A Fly pode ter mais de uma máquina no ar (``auto_start_machines``),
   e sem esta camada dois aparelhos em máquinas diferentes não se falariam.
3. **Reconferência ao voltar ao primeiro plano**, no cliente. Não está aqui,
   mas é o chão de tudo: se as duas camadas acima falharem, as telas ainda se
   corrigem sozinhas ao ganhar foco. Por isso nada aqui precisa de garantia de
   entrega — um aviso perdido custa alguns segundos de defasagem, não um dado
   errado.

A camada 2 exige uma conexão DIRETA com o Postgres. O pooler em modo
transação do Supabase (porta 6543) não suporta ``LISTEN``, e nesse caso o
listener nem sobe: registra o motivo uma vez e o app segue com as camadas 1 e
3. É degradação, não falha — e o log diz exatamente qual.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger("pathr.eventos")

CANAL = "pathr_eventos"

# Quantos avisos uma conexão lenta pode acumular antes de o mais velho ser
# descartado. Um aviso é um empurrão para reconsultar: dez empurrões
# empilhados valem exatamente o mesmo que um, então segurar mais é guardar
# trabalho que já não serve.
LIMITE_DA_FILA = 8

# user_id -> filas das conexões abertas daquele usuário NESTE processo.
_ouvintes: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
_listener: asyncio.Task[None] | None = None


def inscrever(user_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Abre uma fila para uma conexão. Quem chama precisa `cancelar` depois."""
    fila: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=LIMITE_DA_FILA)
    _ouvintes.setdefault(user_id, set()).add(fila)
    return fila


def cancelar(user_id: str, fila: asyncio.Queue[dict[str, Any]]) -> None:
    """Fecha a fila de uma conexão que terminou."""
    filas = _ouvintes.get(user_id)
    if not filas:
        return
    filas.discard(fila)
    if not filas:
        _ouvintes.pop(user_id, None)


def conexoes_abertas(user_id: str | None = None) -> int:
    """Quantas conexões este processo mantém. Só para diagnóstico e testes."""
    if user_id is not None:
        return len(_ouvintes.get(user_id, ()))
    return sum(len(filas) for filas in _ouvintes.values())


def _entregar_local(user_id: str, evento: dict[str, Any]) -> None:
    for fila in list(_ouvintes.get(user_id, ())):
        try:
            fila.put_nowait(evento)
        except asyncio.QueueFull:
            # Descarta o mais VELHO, não o novo: o aviso recente é o que
            # descreve o estado atual.
            with contextlib.suppress(asyncio.QueueEmpty):
                fila.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                fila.put_nowait(evento)


async def publicar(user_id: str, rota: str, origem: str = "") -> None:
    """Avisa as telas daquele usuário que algo mudou.

    `origem` é o identificador do cliente que fez a escrita. Ele volta no
    aviso para o próprio autor se reconhecer e ignorar: quem acabou de gravar
    já atualizou a tela, e reconsultar por causa do próprio POST seria uma
    requisição a mais por escrita, em todo aparelho.
    """
    evento = {"rota": rota, "origem": origem}
    _entregar_local(user_id, evento)
    await _notificar_outras_maquinas(user_id, evento)


async def _notificar_outras_maquinas(user_id: str, evento: dict[str, Any]) -> None:
    if not settings.database_url:
        return
    carga = json.dumps({"user_id": user_id, **evento})
    try:
        await asyncio.to_thread(_notify_bloqueante, carga)
    except Exception as erro:  # noqa: BLE001 — um aviso perdido não pode derrubar a escrita
        logger.debug("NOTIFY falhou (as telas ainda se corrigem no foco): %s", erro)


def _dsn() -> str:
    """A URL no formato que o psycopg entende.

    `settings.database_url` sai normalizada para SQLAlchemy
    (`postgresql+psycopg://`); o driver quer `postgresql://`.
    """
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _notify_bloqueante(carga: str) -> None:
    import psycopg

    with psycopg.connect(_dsn(), connect_timeout=5, autocommit=True) as conn:
        conn.execute("SELECT pg_notify(%s, %s)", (CANAL, carga))


async def _escutar() -> None:
    """Segura uma conexão em LISTEN e repassa o que chegar às filas locais.

    Reconecta com espera crescente: o banco pode reiniciar, e um laço apertado
    de reconexão transformaria uma indisponibilidade curta numa tempestade de
    conexões contra o Supabase.
    """
    import psycopg

    espera = 1.0
    while True:
        try:
            conn = await asyncio.to_thread(
                psycopg.connect, _dsn(), connect_timeout=5, autocommit=True
            )
        except Exception as erro:  # noqa: BLE001
            logger.warning(
                "sem LISTEN (avisos ficam restritos a esta máquina; as telas "
                "ainda se corrigem ao voltar ao foco): %s",
                erro,
            )
            await asyncio.sleep(espera)
            espera = min(espera * 2, 60)
            continue

        espera = 1.0
        try:
            await asyncio.to_thread(conn.execute, f"LISTEN {CANAL}")
            logger.info("ouvindo %s para avisos entre máquinas", CANAL)
            while True:
                aviso = await asyncio.to_thread(_proxima_notificacao, conn)
                if aviso is None:
                    continue
                try:
                    corpo = json.loads(aviso)
                except json.JSONDecodeError:
                    continue
                user_id = corpo.pop("user_id", "")
                if user_id:
                    _entregar_local(user_id, corpo)
        except asyncio.CancelledError:
            raise
        except Exception as erro:  # noqa: BLE001
            logger.warning("LISTEN caiu, reconectando: %s", erro)
        finally:
            with contextlib.suppress(Exception):
                conn.close()
        await asyncio.sleep(espera)


def _proxima_notificacao(conn: Any) -> str | None:
    """Bloqueia até chegar um aviso, ou devolve `None` no tempo limite.

    O tempo limite existe para o laço poder ser cancelado no desligamento: uma
    thread presa para sempre num `notifies()` seguraria o processo.
    """
    for aviso in conn.notifies(timeout=20):
        return str(aviso.payload)
    return None


def iniciar_listener() -> None:
    """Sobe o ouvinte entre máquinas. Chamado no start-up do app."""
    global _listener
    if _listener is not None or not settings.database_url:
        return
    _listener = asyncio.create_task(_escutar())


async def parar_listener() -> None:
    global _listener
    if _listener is None:
        return
    _listener.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _listener
    _listener = None
