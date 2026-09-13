"""Cidades do Brasil: sugestão enquanto se digita, e distância entre duas.

## Por que uma base local e não uma API de geocodificação

As vagas precisam de uma pergunta respondida centenas de vezes por listagem:
"esta cidade fica a quantos km da pessoa?". Uma API externa (Nominatim, Google)
pediria uma chamada por cidade, com limite de uma por segundo no caso gratuito,
e pararia a tela quando saísse do ar. Os 5.570 municípios cabem em 250 KB, não
mudam de lugar, e a distância sai de conta — sem rede.

A base é a de Kelvin S. do Prado (github.com/kelvins/municipios-brasileiros,
licença MIT), com código do IBGE e coordenadas da sede de cada município.
"""

from __future__ import annotations

import csv
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

_ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "municipios.csv"

UFS: dict[str, str] = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}


@dataclass(frozen=True)
class Cidade:
    ibge: str
    nome: str
    uf: str
    lat: float
    lon: float
    capital: bool

    def para_tela(self) -> dict[str, object]:
        return {"ibge": self.ibge, "nome": self.nome, "uf": self.uf, "capital": self.capital}


def normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


_UF_POR_NOME = {normaliza(nome): uf for uf, nome in UFS.items()}


def uf_de(estado: Optional[str]) -> Optional[str]:
    """"ES", "es", "Espírito Santo" e "Espirito Santo" viram "ES"."""
    if not estado:
        return None
    limpo = estado.strip()
    if limpo.upper() in UFS:
        return limpo.upper()
    return _UF_POR_NOME.get(normaliza(limpo))


@lru_cache(maxsize=1)
def _cidades() -> tuple[Cidade, ...]:
    with _ARQUIVO.open(encoding="utf-8", newline="") as arquivo:
        return tuple(
            Cidade(
                ibge=linha["ibge"],
                nome=linha["nome"],
                uf=linha["uf"],
                lat=float(linha["lat"]),
                lon=float(linha["lon"]),
                capital=linha["capital"] == "1",
            )
            for linha in csv.DictReader(arquivo)
        )


@lru_cache(maxsize=1)
def _por_nome() -> dict[str, list[Cidade]]:
    indice: dict[str, list[Cidade]] = {}
    for cidade in _cidades():
        indice.setdefault(normaliza(cidade.nome), []).append(cidade)
    return indice


def achar(nome: Optional[str], estado: Optional[str] = None) -> Optional[Cidade]:
    """A cidade pelo nome, com ou sem acento. Sem UF, só quando o nome é de
    uma cidade só — ou a capital, no empate (é o que um anúncio quer dizer)."""
    candidatas = _por_nome().get(normaliza(nome or ""))
    if not candidatas:
        return None
    uf = uf_de(estado)
    if uf:
        return next((c for c in candidatas if c.uf == uf), None)
    if len(candidatas) == 1:
        return candidatas[0]
    return next((c for c in candidatas if c.capital), None)


def sugerir(texto: str, limite: int = 8) -> list[Cidade]:
    """As cidades cujo nome começa pelo que foi digitado ("vit" → Vitória).

    Começo do nome vem antes de começo de palavra, e capital vem antes dentro
    de cada grupo. Aceita "Vitória ES" e "Vitória - ES" para filtrar o estado.
    """
    uf = None
    # "são pa" é o começo de São Paulo, não São + Pará: a sigla só vale depois
    # de um separador ("Vitória - ES") ou digitada em maiúsculas ("Vitória ES").
    sigla = re.search(r"(?:\s*[-,/]\s*([A-Za-z]{2})|\s+([A-Z]{2}))\s*$", texto or "")
    if sigla and (sigla.group(1) or sigla.group(2)).upper() in UFS:
        uf = (sigla.group(1) or sigla.group(2)).upper()
        texto = texto[: sigla.start()]
    consulta = normaliza(texto)
    if len(consulta) < 2:
        return []

    comeca, palavra = [], []
    for cidade in _cidades():
        if uf and cidade.uf != uf:
            continue
        nome = normaliza(cidade.nome)
        if nome.startswith(consulta):
            comeca.append(cidade)
        elif f" {consulta}" in f" {nome}":
            palavra.append(cidade)
    ordem = lambda c: (not c.capital, len(c.nome), c.nome)  # noqa: E731
    return (sorted(comeca, key=ordem) + sorted(palavra, key=ordem))[:limite]


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Em linha reta (haversine). A estrada é mais longa, mas o raio que a
    pessoa escolhe já é uma estimativa — e em linha reta não depende de mapa."""
    raio_da_terra = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * raio_da_terra * math.asin(math.sqrt(a))


def no_raio(centro: Cidade, raio_km: float) -> list[tuple[Cidade, float]]:
    """As cidades até `raio_km` do centro, da mais perto para a mais longe."""
    perto = (
        (cidade, distancia_km(centro.lat, centro.lon, cidade.lat, cidade.lon))
        for cidade in _cidades()
    )
    return sorted(((c, d) for c, d in perto if d <= raio_km), key=lambda par: par[1])


def cidade_citada(texto: str, candidatas: Iterable[tuple[Cidade, float]]) -> Optional[tuple[Cidade, float]]:
    """A primeira das `candidatas` (já em ordem de distância) que o texto cita
    por nome inteiro. Nomes de três letras ou menos ("Ipê", "Una") ficam de
    fora: casariam em qualquer palavra."""
    alvo = f" {normaliza(texto)} "
    for cidade, distancia in candidatas:
        nome = normaliza(cidade.nome)
        if len(nome) > 3 and f" {nome} " in alvo:
            return cidade, distancia
    return None
