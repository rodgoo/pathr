"""Quanto cada pessoa (ou cada IP) pode pedir, e em quanto tempo.

O PathR nasceu com um usuário. Com vários, três recursos passam a ser de TODOS
ao mesmo tempo, e qualquer um deles pode ser esgotado por uma pessoa só:

1. **A cota de e-mail do Brevo** (~300/dia no plano gratuito). Quem martela
   "esqueci a senha" ou o cadastro com endereços aleatórios gasta os e-mails
   do dia, e a partir daí ninguém recebe o link de confirmação — ninguém mais
   consegue criar conta.
2. **A cota dos provedores de IA**, também gratuita e também do app inteiro.
   Um usuário gerando quiz em laço derruba a IA de todos os outros.
3. **A lista de usuários.** Busca por nome de usuário sem freio é como alguém
   baixa a base inteira de perfis.

## Por que no banco

O backend roda em mais de uma máquina na Fly, e elas dormem quando ociosas.
Um contador em memória valeria por máquina e zeraria a cada vez que uma
acorda: o limite de 5 por hora viraria 5 por hora por máquina, por acordada.
Uma linha por evento em `pathr_rate_event`, contada numa janela, vale para
todas.

## Falha aberta

Se o banco não responder, o pedido PASSA. Um limite que derruba o login
porque o Supabase piscou transforma proteção em indisponibilidade — e o
bloqueio por conta (`security.is_locked`) continua valendo por fora daqui.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from supabase import Client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Regra:
    acao: str
    limite: int
    janela: timedelta
    mensagem: str


# Os números. Folgados para uso real, apertados para abuso: ninguém pede a
# recuperação de senha cinco vezes numa hora por engano.
CADASTRO_POR_IP = Regra("cadastro", 5, timedelta(hours=1), "Muitos cadastros deste endereço. Tente de novo em uma hora.")
LOGIN_POR_IP = Regra("login", 30, timedelta(minutes=15), "Muitas tentativas de entrada. Aguarde alguns minutos.")
EMAIL_POR_IP = Regra("email-publico", 6, timedelta(hours=1), "Muitos pedidos de e-mail deste endereço. Tente de novo em uma hora.")
EMAIL_POR_DESTINO = Regra("email-destino", 3, timedelta(hours=1), "Já enviamos alguns e-mails para este endereço há pouco. Confira a caixa de entrada e o spam.")
USERNAME_POR_IP = Regra("username-checa", 60, timedelta(minutes=10), "Muitas consultas. Aguarde um instante.")
BUSCA_POR_USUARIO = Regra("busca-pessoas", 60, timedelta(minutes=10), "Muitas buscas seguidas. Aguarde um instante.")
CONVITE_POR_USUARIO = Regra("convite-amizade", 40, timedelta(days=1), "Limite de convites de amizade de hoje atingido.")
# Chamadas ao modelo, não requisições: gerar um quiz pode custar duas. 150 por
# dia cobre um dia inteiro de estudo pesado com folga.
RELATO_POR_USUARIO = Regra("relato", 10, timedelta(days=1), "Limite de relatos de hoje atingido. Obrigado por insistir — tente amanhã.")
IA_POR_USUARIO = Regra("ia", 150, timedelta(days=1), "Você atingiu o limite diário de uso da IA. Ele volta amanhã.")


# Quem está fazendo a requisição corrente, para a IA contar a cota sem que
# cada rota precise repassar o usuário. Preenchido pelo middleware em
# `app.middleware_usuario` — só para CONTAGEM: autorização continua sendo do
# `get_current_user`, que confere a sessão no banco.
usuario_da_requisicao: ContextVar[Optional[str]] = ContextVar("usuario_da_requisicao", default=None)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def consumir(supabase: Client, regra: Regra, chave: Optional[str]) -> None:
    """Conta um uso de `regra` para `chave`, ou recusa com 429 se passou.

    Chave vazia (IP desconhecido) não é limitada: agrupar todo mundo sem IP
    sob a mesma chave bloquearia pessoas que não têm nada a ver umas com as
    outras.
    """
    if not chave:
        return
    chave = chave.strip().lower()[:200]
    desde = (_agora() - regra.janela).isoformat()
    try:
        usados = (
            supabase.table("pathr_rate_event")
            .select("id", count="exact")
            .eq("action", regra.acao)
            .eq("key", chave)
            .gte("created_at", desde)
            .limit(1)
            .execute()
            .count
            or 0
        )
    except Exception:  # noqa: BLE001
        logger.warning("limite %s: contagem indisponivel, deixando passar", regra.acao)
        return

    if usados >= regra.limite:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=regra.mensagem,
            headers={"Retry-After": str(int(regra.janela.total_seconds()))},
        )

    try:
        # A linha velha sai no disparo de hora em hora (services/faxina.py).
        supabase.table("pathr_rate_event").insert({"action": regra.acao, "key": chave}).execute()
    except Exception:  # noqa: BLE001
        logger.warning("limite %s: registro indisponivel", regra.acao)


def consumir_ia(supabase_factory) -> None:
    """Conta uma chamada ao modelo para quem está logado na requisição.

    Sem usuário (tarefa agendada, e-mail de aviso), não conta: a cota é por
    pessoa, e o trabalho do próprio app não é de ninguém.
    """
    usuario = usuario_da_requisicao.get()
    if not usuario:
        return
    consumir(supabase_factory(), IA_POR_USUARIO, usuario)
