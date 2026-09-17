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
# Contas falsas em série (services/antirrobo.py). O dia segura quem espera a hora
# virar; a faixa segura quem troca de IP dentro da mesma rede; o global é o teto
# do app inteiro, contado só quando a conta vai mesmo ser criada.
CADASTRO_POR_IP_DIA = Regra("cadastro-dia", 10, timedelta(days=1), "Muitos cadastros deste endereço hoje. Tente amanhã.")
CADASTRO_POR_REDE = Regra("cadastro-rede", 30, timedelta(days=1), "Muitos cadastros desta rede hoje. Tente mais tarde.")
CADASTRO_GLOBAL = Regra("cadastro-global", 300, timedelta(hours=1), "Muitos cadastros agora. Tente de novo em alguns minutos.")
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
# A curadoria busca na web e valida cada link: cara por pedido, e cada tag nova
# abria uma rodada. Por conta, para criar tags em série não virar busca infinita.
CURADORIA_POR_USUARIO = Regra("curadoria", 12, timedelta(days=1), "Já buscamos materiais várias vezes hoje. Tente amanhã.")
# Candidaturas (services/candidaturas.py). Montar a fila à mão busca em todas
# as fontes; a carta é uma chamada de IA; e o envio sai pelo domínio do PathR —
# sem teto, seria um relay de spam de graça, e a reputação de envio perdida
# derrubaria junto os e-mails de confirmação de conta.
FILA_DE_VAGAS = Regra("fila-vagas", 6, timedelta(days=1), "Você já montou a fila de vagas várias vezes hoje. Tente amanhã.")
CARTA_POR_USUARIO = Regra("carta", 30, timedelta(days=1), "Limite de cartas de apresentação de hoje atingido.")
ENVIO_DE_CANDIDATURA = Regra("envio-candidatura", 25, timedelta(days=1), "Você já enviou muitas candidaturas hoje. O limite volta amanhã.")
TAG_NOVA_POR_USUARIO = Regra("tag-por-nome", 60, timedelta(days=1), "Limite de tecnologias adicionadas hoje atingido.")


# Quem está fazendo a requisição corrente, para a IA contar a cota sem que
# cada rota precise repassar o usuário. Preenchido pelo middleware em
# `app.middleware_usuario` — só para CONTAGEM: autorização continua sendo do
# `get_current_user`, que confere a sessão no banco.
usuario_da_requisicao: ContextVar[Optional[str]] = ContextVar("usuario_da_requisicao", default=None)


def rede_do_ip(ip: Optional[str]) -> Optional[str]:
    """A faixa do IP: /24 no IPv4, /48 no IPv6. Um IPv6 inteiro é trivial de
    trocar (cada aparelho tem milhões), e um script com várias máquinas numa
    mesma rede ainda cai na mesma chave."""
    if not ip:
        return None
    import ipaddress

    try:
        endereco = ipaddress.ip_address(ip.strip())
    except ValueError:
        return ip
    prefixo = 24 if endereco.version == 4 else 48
    return str(ipaddress.ip_network(f"{endereco}/{prefixo}", strict=False))


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

    # REGISTRA PRIMEIRO, conta depois.
    #
    # Na ordem inversa (contar, decidir, registrar) havia uma janela entre a
    # contagem e a escrita: dez pedidos simultâneos liam "0 usados", os dez
    # passavam e os dez gravavam — o teto diário virava dez vezes o teto, que é
    # exatamente o que um ataque faz (pedidos em paralelo, não em fila).
    #
    # Gravando antes, cada pedido já entra na conta que ele mesmo vai ler: quem
    # chegou junto vê a si e aos outros, e todos além do teto são recusados. O
    # preço é que o pedido recusado também deixa a sua linha — tentativa
    # recusada consome cota, que para um limite de abuso é o comportamento
    # certo, não um defeito.
    try:
        # A linha velha sai no disparo de hora em hora (services/faxina.py).
        supabase.table("pathr_rate_event").insert({"action": regra.acao, "key": chave}).execute()
    except Exception:  # noqa: BLE001
        logger.warning("limite %s: registro indisponivel", regra.acao)
        return

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

    # `>` e não `>=`: a linha deste pedido já está contada, então o pedido de
    # número `limite` ainda passa e o seguinte é recusado.
    if usados > regra.limite:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=regra.mensagem,
            headers={"Retry-After": str(int(regra.janela.total_seconds()))},
        )


def consumir_ia(supabase_factory) -> None:
    """Conta uma chamada ao modelo para quem está logado na requisição.

    Sem usuário (tarefa agendada, e-mail de aviso), não conta: a cota é por
    pessoa, e o trabalho do próprio app não é de ninguém.
    """
    usuario = usuario_da_requisicao.get()
    if not usuario:
        return
    consumir(supabase_factory(), IA_POR_USUARIO, usuario)
