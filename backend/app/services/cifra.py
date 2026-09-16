"""Cifra dos dados sensíveis, feita no app — a chave nunca vai para o banco.

## O que isto protege

Um vazamento do banco (dump, backup copiado, acesso indevido ao painel do
Supabase, SQL rodado por fora) ou do armazenamento de arquivos não entrega a
data de nascimento, o currículo, as fotos nem os relatos: lá só existe texto
cifrado. Para ler, é preciso também a chave, que mora nas secrets do servidor
(Fly), fora do banco e fora do repositório.

O que isto NÃO protege: quem controla o servidor em execução tem a chave. É o
limite de qualquer sistema que precisa LER o dado para funcionar (a IA lê o
currículo, a moderação lê o relato).

## Como

- **AES-256-GCM** (cifra autenticada): um byte alterado no banco faz a leitura
  falhar em vez de devolver lixo.
- **Nonce aleatório de 96 bits** por valor: o mesmo texto cifrado duas vezes dá
  resultados diferentes, e não dá para descobrir quem nasceu no mesmo dia.
- **Amarrado ao dono e ao lugar** (dado associado): o texto cifrado da data de
  nascimento de uma conta, copiado para a linha de outra, não abre.
- **Versionado e com o id da chave**: trocar a chave é pôr a nova em
  `DATA_ENCRYPTION_KEY` e a antiga em `DATA_ENCRYPTION_KEYS_OLD`. O que foi
  cifrado com a antiga continua abrindo; o que for gravado sai com a nova.

## Dado antigo

A leitura aceita o valor ainda sem cifra (sem o prefixo): o deploy não quebra
nada, e `scripts/cifrar_dados_existentes.py` cifra o que já estava gravado.
Em produção, gravar sem chave configurada é recusado — nunca se grava dado
sensível em claro por esquecimento de configuração.

A chave precisa de uma cópia guardada FORA do Fly (gerenciador de senhas):
sem ela, currículos, fotos e relatos cifrados ficam perdidos para sempre.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from functools import lru_cache
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

PREFIXO = "pathr1:"
MAGICO = b"PATHR1"
_TAMANHO_NONCE = 12
_TAMANHO_KID = 4


class CifraIndisponivel(RuntimeError):
    """Sem chave em produção, ou texto cifrado que nenhuma chave abre."""


def _decodificar_chave(bruta: str) -> bytes:
    limpa = bruta.strip()
    try:
        chave = base64.urlsafe_b64decode(limpa + "=" * (-len(limpa) % 4))
    except (binascii.Error, ValueError) as exc:
        raise CifraIndisponivel("DATA_ENCRYPTION_KEY não é base64 válido.") from exc
    if len(chave) != 32:
        raise CifraIndisponivel("DATA_ENCRYPTION_KEY precisa ter 32 bytes (AES-256).")
    return chave


def _kid(chave: bytes) -> bytes:
    return hashlib.sha256(chave).digest()[:_TAMANHO_KID]


@lru_cache(maxsize=4)
def _chaves(atual: str, antigas: str) -> tuple[Optional[tuple[bytes, bytes]], dict[bytes, bytes]]:
    principal = None
    todas: dict[bytes, bytes] = {}
    if atual.strip():
        chave = _decodificar_chave(atual)
        principal = (_kid(chave), chave)
        todas[principal[0]] = chave
    for bruta in antigas.split(","):
        if bruta.strip():
            chave = _decodificar_chave(bruta)
            todas.setdefault(_kid(chave), chave)
    return principal, todas


def _config() -> tuple[Optional[tuple[bytes, bytes]], dict[bytes, bytes]]:
    return _chaves(settings.data_encryption_key or "", settings.data_encryption_keys_old or "")


def ativa() -> bool:
    return _config()[0] is not None


def _chave_para_gravar() -> Optional[tuple[bytes, bytes]]:
    principal, _ = _config()
    if principal is None and settings.is_production:
        raise CifraIndisponivel("DATA_ENCRYPTION_KEY não configurada: dado sensível não é gravado em claro.")
    return principal


def _contexto(contexto: str) -> bytes:
    return contexto.encode("utf-8")


# -- texto -------------------------------------------------------------------


def cifrar(valor: Optional[str], contexto: str) -> Optional[str]:
    """Texto -> "pathr1:<kid>:<base64(nonce||ct||tag)>". None e "" passam como estão."""
    if valor is None or valor == "":
        return valor
    if valor.startswith(PREFIXO):
        return valor  # já cifrado: cifrar duas vezes esconderia o dado de si mesmo
    chave = _chave_para_gravar()
    if chave is None:
        return valor  # desenvolvimento e testes sem chave
    kid, segredo = chave
    nonce = os.urandom(_TAMANHO_NONCE)
    corpo = AESGCM(segredo).encrypt(nonce, valor.encode("utf-8"), _contexto(contexto))
    return f"{PREFIXO}{kid.hex()}:{base64.urlsafe_b64encode(nonce + corpo).decode()}"


def decifrar(valor: Optional[str], contexto: str) -> Optional[str]:
    """O inverso de `cifrar`. Valor sem o prefixo é dado antigo, em claro."""
    if not isinstance(valor, str) or not valor.startswith(PREFIXO):
        return valor
    try:
        kid_hex, corpo_b64 = valor[len(PREFIXO):].split(":", 1)
        bruto = base64.urlsafe_b64decode(corpo_b64)
        segredo = _config()[1][bytes.fromhex(kid_hex)]
        texto = AESGCM(segredo).decrypt(bruto[:_TAMANHO_NONCE], bruto[_TAMANHO_NONCE:], _contexto(contexto))
    except Exception as exc:  # noqa: BLE001
        # Chave errada, dado adulterado, ou cópia vinda de outra conta: nunca
        # devolver o texto cifrado como se fosse o dado.
        raise CifraIndisponivel("Não foi possível decifrar o dado.") from exc
    return texto.decode("utf-8")


# -- JSON (currículo lido pela IA) --------------------------------------------

_CHAVE_JSON = "_cifrado"


def cifrar_json(valor: Any, contexto: str) -> Any:
    """Um objeto vira {"_cifrado": "pathr1:…"} — cabe na mesma coluna jsonb."""
    if not valor:
        return valor
    if isinstance(valor, dict) and _CHAVE_JSON in valor:
        return valor
    texto = cifrar(json.dumps(valor, ensure_ascii=False), contexto)
    if texto is None or not texto.startswith(PREFIXO):
        return valor
    return {_CHAVE_JSON: texto}


def decifrar_json(valor: Any, contexto: str) -> Any:
    if isinstance(valor, dict) and isinstance(valor.get(_CHAVE_JSON), str):
        return json.loads(decifrar(valor[_CHAVE_JSON], contexto) or "null")
    return valor


# -- arquivos (currículo, fotos) ---------------------------------------------


def cifrar_bytes(dados: bytes, contexto: str) -> bytes:
    if not dados or dados.startswith(MAGICO):
        return dados
    chave = _chave_para_gravar()
    if chave is None:
        return dados
    kid, segredo = chave
    nonce = os.urandom(_TAMANHO_NONCE)
    return MAGICO + kid + nonce + AESGCM(segredo).encrypt(nonce, dados, _contexto(contexto))


def decifrar_bytes(dados: bytes, contexto: str) -> bytes:
    if not dados or not dados.startswith(MAGICO):
        return dados
    inicio = len(MAGICO)
    kid = dados[inicio:inicio + _TAMANHO_KID]
    nonce = dados[inicio + _TAMANHO_KID:inicio + _TAMANHO_KID + _TAMANHO_NONCE]
    corpo = dados[inicio + _TAMANHO_KID + _TAMANHO_NONCE:]
    try:
        return AESGCM(_config()[1][kid]).decrypt(nonce, corpo, _contexto(contexto))
    except Exception as exc:  # noqa: BLE001
        raise CifraIndisponivel("Não foi possível decifrar o arquivo.") from exc


# -- contextos: um por lugar, sempre com o dono ------------------------------


def ctx_nascimento(user_id: str) -> str:
    return f"pathr_profile.birth_date:{user_id}"


def ctx_curriculo_texto(user_id: str) -> str:
    return f"pathr_resume.raw_text:{user_id}"


def ctx_curriculo_dados(user_id: str) -> str:
    return f"pathr_resume.parsed:{user_id}"


def ctx_relato(user_id: str, coluna: str) -> str:
    return f"pathr_report.{coluna}:{user_id}"


def ctx_carta(user_id: str) -> str:
    """A carta de apresentação da candidatura: currículo e objetivo de
    carreira misturados, o mesmo tipo de dado de `ctx_curriculo_texto`."""
    return f"carta:{user_id}"


def ctx_arquivo(bucket: str, caminho: str) -> str:
    return f"storage:{bucket}/{caminho}"
