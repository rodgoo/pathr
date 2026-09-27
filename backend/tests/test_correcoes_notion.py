"""Correções de revisão: email_confiavel, guarda de SSRF, RTF e estado do evento."""

import ipaddress

import pytest

from app.services import candidaturas, reader, text_extract
from app.services.evento_da_pagina import _lugar


@pytest.mark.parametrize(
    "email,ok",
    [
        ("rh@nubank-carreiras.io", False),
        ("rh@nubank.com.br", True),
        ("rh@carreiras.nubank.com.br", True),
        ("rh@outra.com", False),
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
