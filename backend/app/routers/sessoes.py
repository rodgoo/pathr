"""Aparelhos conectados: ver onde a conta está aberta e encerrar um deles.

Uma "sessão" aqui é uma FAMÍLIA de refresh tokens (migração 0025): o login
num aparelho e todas as renovações que vieram dele. A lista mostra uma linha
por família viva; encerrar revoga a família inteira, e o token de acesso
daquele aparelho para de valer na próxima requisição (deps confere a sessão
a cada chamada).

Também mora aqui o aviso de novo acesso: o e-mail que sai quando a conta
entra de um navegador/sistema que ela não usava.
"""

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from app.database import get_supabase
from app.deps import client_ip, get_current_user_allow_unverified, user_agent
from app.services import aparelho
from app.services import email as emails

router = APIRouter(prefix="/auth/sessoes", tags=["autenticação"])
logger = logging.getLogger("pathr.sessoes")

# Quanto tempo um aparelho continua "conhecido" para o aviso. Voltar a entrar
# pelo mesmo Chrome depois de meses sem uso não é novidade que mereça e-mail.
_MEMORIA_DO_APARELHO = timedelta(days=180)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _momento(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _familia(linha: dict[str, Any]) -> str:
    return str(linha.get("family_id") or linha["id"])


def _grupo(linha: dict[str, Any]) -> str:
    """O que conta como "um aparelho" na lista: o id do dispositivo (o cookie
    que sobrevive a logout/login), ou a família do login para sessões antigas
    que ainda não têm dispositivo."""
    return str(linha.get("device_id") or linha.get("family_id") or linha["id"])


@router.get("")
def listar(
    current_user: dict = Depends(get_current_user_allow_unverified),
    supabase: Client = Depends(get_supabase),
):
    """Uma linha por aparelho com sessão viva: este aparelho primeiro, depois
    os usados mais recentemente."""
    user_id = str(current_user["id"])
    linhas = (
        supabase.table("pathr_refresh_token")
        .select("id,family_id,device_id,user_agent,ip,created_at,expires_at,revoked_at")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    agora = _agora()
    sessao_atual = str(current_user.get("session_id") or "")
    grupo_atual = next((_grupo(l) for l in linhas if str(l["id"]) == sessao_atual), None)

    familias: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        grupo = familias.setdefault(_grupo(linha), {"inicio": None, "viva": None, "viva_em": None})
        criado = _momento(linha.get("created_at"))
        if criado and (grupo["inicio"] is None or criado < grupo["inicio"]):
            grupo["inicio"] = criado
        expira = _momento(linha.get("expires_at"))
        if linha.get("revoked_at") or not expira or expira <= agora:
            continue
        if grupo["viva"] is None or (criado and grupo["viva_em"] and criado > grupo["viva_em"]):
            grupo["viva"], grupo["viva_em"] = linha, criado

    saida = []
    for chave, grupo in familias.items():
        viva = grupo["viva"]
        if not viva:
            continue
        ua = viva.get("user_agent")
        saida.append(
            {
                "id": chave,
                "aparelho": aparelho.descrever(ua),
                "navegador": aparelho.navegador(ua),
                "sistema": aparelho.sistema(ua),
                "celular": aparelho.celular(ua),
                "ip": aparelho.ip_mascarado(viva.get("ip")),
                # O token vivo nasce a cada renovação (a cada ~30 min de uso):
                # a data dele é o "último uso" que a pessoa entende.
                "ultimo_uso": viva.get("created_at"),
                "entrou_em": grupo["inicio"].isoformat() if grupo["inicio"] else viva.get("created_at"),
                "este_aparelho": chave == grupo_atual,
            }
        )
    atual = [s for s in saida if s["este_aparelho"]]
    outros = sorted(
        (s for s in saida if not s["este_aparelho"]), key=lambda s: str(s["ultimo_uso"] or ""), reverse=True
    )
    return atual + outros


@router.delete("/{familia}", status_code=status.HTTP_204_NO_CONTENT)
def encerrar(
    familia: str,
    current_user: dict = Depends(get_current_user_allow_unverified),
    supabase: Client = Depends(get_supabase),
):
    """Encerra um aparelho. 404 para família que não é da pessoa — nem diz que existe."""
    try:
        uuid.UUID(familia)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada.")
    user_id = str(current_user["id"])
    linhas = (
        supabase.table("pathr_refresh_token")
        .select("id,family_id,device_id")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    ids = [str(l["id"]) for l in linhas if _grupo(l) == familia]
    if not ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada.")
    agora = _agora().isoformat()
    for token_id in ids:
        supabase.table("pathr_refresh_token").update({"revoked_at": agora}).eq("id", token_id).eq(
            "user_id", user_id
        ).is_("revoked_at", "null").execute()
    return None


# ---------------------------------------------------------------------------
# Aviso de novo acesso
# ---------------------------------------------------------------------------


def aparelho_novo(supabase: Client, user_id: str, ua: Optional[str]) -> bool:
    """A conta nunca entrou por este navegador+sistema nos últimos 180 dias?

    Chamado ANTES de criar a sessão nova. Conta sem nenhuma sessão anterior
    (o primeiro login depois do cadastro) não é "novo acesso": não há com o
    que comparar, e o e-mail só assustaria quem acabou de criar a conta.
    """
    try:
        linhas = (
            supabase.table("pathr_refresh_token")
            .select("user_agent,created_at")
            .eq("user_id", user_id)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        return False
    if not linhas:
        return False
    limite = _agora() - _MEMORIA_DO_APARELHO
    alvo = aparelho.assinatura(ua)
    for linha in linhas:
        criado = _momento(linha.get("created_at"))
        if criado and criado < limite:
            continue
        if aparelho.assinatura(linha.get("user_agent")) == alvo:
            return False
    return True


def avisar_se_novo(supabase: Client, user: dict, request: Optional[Request], metodo: str) -> None:
    """Manda o e-mail de novo acesso em segundo plano, se o aparelho for novo.

    Em thread, e não na requisição: o Brevo pode levar segundos, e o login não
    pode esperar por um e-mail. Falha no envio fica no log — nunca impede entrar.
    """
    destino = user.get("email")
    if not destino:
        return
    ua = user_agent(request)
    if not aparelho_novo(supabase, str(user["id"]), ua):
        return
    dados = {
        "aparelho": aparelho.descrever(ua),
        "ip": aparelho.ip_mascarado(client_ip(request)),
        "quando": _agora(),
        "metodo": metodo,
    }

    def enviar() -> None:
        try:
            emails.send_new_login(destino, user.get("name") or "", **dados)
        except Exception:  # noqa: BLE001
            logger.warning("aviso de novo acesso não saiu", exc_info=True)

    threading.Thread(target=enviar, daemon=True).start()
