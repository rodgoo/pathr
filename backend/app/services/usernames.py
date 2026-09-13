"""O nome de usuário: `@rodrigocarvalho`, e o que fazer quando ele já existe.

É por ele que uma pessoa encontra outra, e é ele que aparece no lugar do
e-mail em tudo que outra conta vê. Por isso as regras são estreitas: letras
minúsculas, números e underline, começando por letra. Um `@Rodrigo.Carvalho`
e um `@rodrigocarvalho` seriam duas contas que ninguém distingue lendo.

## Quem não escolhe, ganha um

O cadastro pede o nome de usuário, mas não trava quem pula: a conta nasce com
um derivado do nome completo. A ordem das tentativas é a que o usuário pediu,
e é também a que produz o nome mais parecido com o que a pessoa teria
escolhido:

1. os nomes concatenados            rodrigocarvalho
2. underline entre os nomes         rodrigo_carvalho
3. underline no fim                 rodrigocarvalho_
4. um número                        rodrigocarvalho2, rodrigo_carvalho2, ...

Conectivos saem ("Maria da Silva" vira `mariasilva`, não `mariadasilva`):
ninguém digita o "da" quando procura alguém.

## Unicidade é do banco

A checagem aqui escolhe um candidato livre, mas quem GARANTE a unicidade é o
índice único em `lower(username)` (migração 0020). Duas pessoas cadastrando
"Ana Souza" no mesmo segundo passariam as duas pela checagem; o índice recusa
a segunda, e quem chama tenta o próximo candidato.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable, Optional

MINIMO = 3
MAXIMO = 24

_VALIDO = re.compile(r"^[a-z][a-z0-9_]{2,23}$")

# Palavras que não podem ser de ninguém: pareceriam o próprio app falando, e
# são a primeira coisa que alguém tenta para se passar por suporte.
RESERVADOS = frozenset(
    {
        "admin", "administrador", "api", "app", "ajuda", "conta", "contato",
        "equipe", "help", "moderador", "notter", "oficial", "pathr", "root",
        "seguranca", "sistema", "staff", "suporte", "support", "system",
    }
)

# Conectivos de nome em português. Saem da concatenação, não da pessoa.
_CONECTIVOS = frozenset({"da", "das", "de", "di", "do", "dos", "du", "e", "y"})

# Agnomes: marcam geração, não família. Com nome longo, o sobrenome escolhido é
# o último ANTES deles — "Rodrigo Carvalho Neto" é o Rodrigo Carvalho, e
# `rodrigoneto` não seria encontrado por ninguém que o conhece.
_AGNOMES = frozenset({"filho", "neto", "junior", "jr", "sobrinho", "segundo", "terceiro"})


def normalizar(bruto: str) -> str:
    """O que a pessoa digitou, no formato guardado: sem @, minúsculo, sem espaço."""
    return (bruto or "").strip().lstrip("@").strip().lower()


def problema(username: str) -> Optional[str]:
    """Por que este nome não serve, em português — ou `None` se serve.

    Não confere se está livre: isso é do banco. Aqui só a forma.
    """
    nome = normalizar(username)
    if len(nome) < MINIMO:
        return f"Use ao menos {MINIMO} caracteres."
    if len(nome) > MAXIMO:
        return f"Use no máximo {MAXIMO} caracteres."
    if not nome[0].isalpha() or not nome[0].isascii():
        return "Comece com uma letra."
    if not _VALIDO.match(nome):
        return "Use só letras minúsculas sem acento, números e _."
    if "__" in nome:
        return "Não use dois _ seguidos."
    if nome.strip("_") in RESERVADOS:
        return "Este nome é reservado."
    return None


def _partes(nome_completo: str) -> list[str]:
    """As palavras do nome, sem acento, sem símbolo e sem conectivo."""
    sem_acento = (
        unicodedata.normalize("NFKD", nome_completo or "").encode("ascii", "ignore").decode()
    )
    palavras = re.findall(r"[a-z0-9]+", sem_acento.lower())
    uteis = [p for p in palavras if p not in _CONECTIVOS]
    return uteis or palavras


def _cabe(texto: str) -> str:
    """Corta no máximo sem deixar underline pendurado no corte."""
    return texto[:MAXIMO].rstrip("_") if len(texto) > MAXIMO else texto


def candidatos(nome_completo: str, quantos_numeros: int = 50) -> list[str]:
    """Os nomes a tentar, na ordem de preferência. Todos com forma válida.

    Com nome longo, só primeiro e último entram: "Rodrigo Augusto Pereira
    Carvalho" como `rodrigoaugustopereiracar` é pior que `rodrigocarvalho`.
    """
    partes = _partes(nome_completo)
    if not partes:
        partes = ["estudante"]
    if len(partes) > 2 and len("".join(partes)) > MAXIMO:
        familia = [p for p in partes[1:] if p not in _AGNOMES] or partes[1:]
        partes = [partes[0], familia[-1]]
    # Nome começando por número ("2Pac") ganha um prefixo para ser válido.
    if not partes[0][0].isalpha():
        partes[0] = "u" + partes[0]

    junto = _cabe("".join(partes))
    separado = _cabe("_".join(partes))
    base = [junto]
    if len(partes) > 1:
        base.append(separado)
    base.append(_cabe(junto[: MAXIMO - 1]) + "_")

    numerados: list[str] = []
    for numero in range(2, 2 + quantos_numeros):
        sufixo = str(numero)
        numerados.append(junto[: MAXIMO - len(sufixo)] + sufixo)
        if len(partes) > 1:
            numerados.append(separado[: MAXIMO - len(sufixo)].rstrip("_") + sufixo)

    vistos: set[str] = set()
    saida: list[str] = []
    for item in base + numerados:
        if item not in vistos and problema(item) is None:
            vistos.add(item)
            saida.append(item)
    return saida


def sugestoes_para(desejado: str, nome_completo: str = "") -> list[str]:
    """O que oferecer quando o nome digitado já tem dono.

    Primeiro variações do próprio nome digitado — a pessoa escolheu aquele por
    algum motivo —, depois os derivados do nome completo.
    """
    alvo = normalizar(desejado)
    variacoes: list[str] = []
    if problema(alvo) is None:
        variacoes.append(_cabe(alvo[: MAXIMO - 1]) + "_")
        for numero in range(1, 30):
            sufixo = str(numero)
            variacoes.append(alvo[: MAXIMO - len(sufixo)] + sufixo)
    vistos: set[str] = {alvo}
    saida: list[str] = []
    for item in variacoes + (candidatos(nome_completo) if nome_completo else []):
        if item not in vistos and problema(item) is None:
            vistos.add(item)
            saida.append(item)
    return saida


def primeiro_livre(
    opcoes: Iterable[str], ocupados: Callable[[list[str]], set[str]]
) -> Optional[str]:
    """O primeiro nome da lista que ninguém usa.

    `ocupados` recebe um lote e devolve os que já têm dono — uma consulta por
    lote, e não uma por nome, porque "Ana Souza" pode precisar de dezenas de
    tentativas antes de achar um número livre.
    """
    lista = list(opcoes)
    for inicio in range(0, len(lista), 20):
        lote = lista[inicio : inicio + 20]
        tomados = ocupados(lote)
        for nome in lote:
            if nome not in tomados:
                return nome
    return None
