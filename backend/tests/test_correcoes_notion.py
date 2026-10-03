"""Correções de revisão: email_confiavel, guarda de SSRF, RTF e estado do evento."""

import ipaddress
import re
from pathlib import Path

import pytest
from sqlmodel import SQLModel

from app import models  # noqa: F401 — popula o metadata
from app.services import candidaturas, reader, text_extract
from app.services.evento_da_pagina import _lugar

_RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "email,ok",
    [
        ("rh@nubank-carreiras.io", False),
        ("rh@nubank.com.br", True),
        ("rh@carreiras.nubank.com.br", True),
        ("rh@outra.com", False),
        # O rótulo da empresa como SUBdomínio escolhido pelo atacante, não
        # como raiz do domínio registrável — o domínio registrável aqui é
        # "dominio-do-atacante.com", não "nubank".
        ("rh@nubank.dominio-do-atacante.com", False),
    ],
)
def test_email_confiavel_exige_rotulo_igual(email, ok):
    assert candidaturas.email_confiavel(email, "Nubank", None) is ok


@pytest.mark.parametrize(
    "ip",
    ["100.64.0.1", "100.127.255.254", "64:ff9b::a9fe:a9fe", "64:ff9b::8.8.8.8",
     "::ffff:127.0.0.1", "2002:7f00:1::", "2001:0:4136:e378:8000:63bf:3fff:fdd2"],
)
def test_ssrf_bloqueia_cgnat_nat64_e_ipv4_embutido(ip):
    assert reader._ip_interno(ipaddress.ip_address(ip))


def test_ssrf_deixa_passar_ip_publico():
    assert not reader._ip_interno(ipaddress.ip_address("8.8.8.8"))
    assert not reader._ip_interno(ipaddress.ip_address("2606:4700:4700::1111"))


def test_rtf_real_sai_sem_marcacao():
    rtf = (
        rb"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fswiss Arial;}}"
        rb"{\*\generator Word;}\pard\f0\fs24 Jo\'e3o Silva\par "
        rb"\pard\b Desenvolvedor Java\b0\par}"
    )
    texto = text_extract._from_rtf(rtf).text
    assert "João Silva" in texto and "Desenvolvedor Java" in texto
    for lixo in ("pard", "fs24", "rtf1", "fonttbl", "generator", "Arial"):
        assert lixo not in texto


@pytest.mark.parametrize(
    "regiao,uf",
    [("São Paulo", "SP"), ("Minas Gerais", "MG"), ("Rio de Janeiro", "RJ"), ("SP", "SP"),
     ("sao paulo", "SP"), ("Atlantis", None)],
)
def test_addressregion_vira_uf_certa(regiao, uf):
    no = {"location": {"name": "Local", "address": {"addressRegion": regiao, "addressLocality": "X"}}}
    assert _lugar(no)[2] == uf


def _cabecalhos_do_caddyfile() -> dict[str, str]:
    """Os cabeçalhos do bloco `header { ... }` de {$DOMAIN_APP}, em deploy/Caddyfile."""
    texto = (_RAIZ / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    bloco = re.search(r"\{\$DOMAIN_APP\}\s*\{.*?header\s*\{(.*?)\n\t\}", texto, re.DOTALL)
    assert bloco, "bloco header{} não encontrado em deploy/Caddyfile"
    return dict(re.findall(r'^\s*([\w-]+)\s+"(.*)"\s*$', bloco.group(1), re.MULTILINE))


def _cabecalhos_do_headers_cloudflare() -> dict[str, str]:
    """Os cabeçalhos do bloco `/*`, em frontend/public/_headers."""
    texto = (_RAIZ / "frontend" / "public" / "_headers").read_text(encoding="utf-8")
    bloco = re.search(r"^/\*\n((?:  .+\n)+)", texto, re.MULTILINE)
    assert bloco, "bloco /* não encontrado em frontend/public/_headers"
    return dict(re.findall(r"^\s*([\w-]+):\s*(.+)$", bloco.group(1), re.MULTILINE))


def test_caddy_do_self_host_espelha_os_cabecalhos_de_seguranca_do_site():
    """O self-host via VPS (deploy/Caddyfile) precisa enviar os MESMOS
    cabeçalhos de segurança que o Cloudflare Pages envia via
    frontend/public/_headers — o Caddy não lê aquele arquivo (é convenção
    específica do Pages), então sem este espelhamento o self-host perde CSP,
    X-Frame-Options, HSTS e nosniff."""
    do_caddy = _cabecalhos_do_caddyfile()
    do_cloudflare = _cabecalhos_do_headers_cloudflare()

    exigidos = {
        "X-Content-Type-Options",
        "Referrer-Policy",
        "X-Frame-Options",
        "Strict-Transport-Security",
        "Permissions-Policy",
        "Content-Security-Policy",
    }
    assert exigidos <= set(do_caddy), f"faltando no Caddyfile: {exigidos - set(do_caddy)}"
    assert exigidos <= set(do_cloudflare), f"faltando no _headers: {exigidos - set(do_cloudflare)}"
    for nome in exigidos:
        assert do_caddy[nome] == do_cloudflare[nome], f"{nome} diverge entre Caddyfile e _headers"


# --- PathrTag.parent_id e PathrRoadmapNode.parent_id têm FK de verdade ------
#
# Ao contrário de quase todo outro relacionamento do arquivo, estes dois eram
# só PGUUID com índice, sem ForeignKey — não é referência polimórfica (como
# PathrActivity.ref_id): o alvo é sempre a mesma tabela, e a ausência de FK
# deixava parent_id órfão (apontando para linha já apagada) sem nada impedir.


@pytest.mark.parametrize(
    "tabela,coluna,alvo",
    [
        ("pathr_tag", "parent_id", "pathr_tag.id"),
        ("pathr_roadmap_node", "parent_id", "pathr_roadmap_node.id"),
    ],
)
def test_parent_id_autorreferente_tem_chave_estrangeira(tabela, coluna, alvo):
    coluna_sa = SQLModel.metadata.tables[tabela].columns[coluna]
    fks = list(coluna_sa.foreign_keys)
    assert len(fks) == 1, f"{tabela}.{coluna} precisa de exatamente uma FK"
    assert fks[0].target_fullname == alvo
    # SET NULL, não CASCADE: apagar o pai não deveria apagar os filhos da
    # hierarquia, só soltá-los da árvore.
    assert fks[0].ondelete == "SET NULL"
    assert coluna_sa.nullable
