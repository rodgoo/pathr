"""Acha texto em português que não passa pelo dicionário.

    cd frontend && python scripts/acha-portugues.py

Existe porque a tradução de um app não termina: toda tela nova nasce com string
fixa, e ninguém percebe até alguém abrir o app em espanhol. O `traduzir.mjs`
cuida do que JÁ está no dicionário; este aqui encontra o que nunca entrou.

Como decide: procura texto de JSX (inclusive o que quebra em várias linhas) e
props de rótulo (`title`, `label`, `placeholder`, `description`, `aria-label`,
`alt`) que tenham acento ou palavra funcional do português. Comentário é
ignorado — a documentação do código é em português de propósito.

É uma heurística e erra para os dois lados: nome próprio com acento aparece à
toa, e "Save" fixo em inglês passa batido. Serve para dar a LISTA por onde
começar, não para bater o martelo — por isso imprime contagem por arquivo, e a
conferência é de quem lê.
"""

import re, pathlib, collections

RAIZ = pathlib.Path("src")
PT = re.compile(r"[ãõáéíóúâêôàç]|\b(você|voce|seu|sua|não|nao|uma|ainda|aqui|hoje|para)\b", re.I)
# Texto de JSX que pode atravessar linhas, sem tag nem expressão dentro.
TEXTO = re.compile(r">\s*([^<>{}]{8,400}?)\s*<", re.S)
PROP = re.compile(r'\b(title|label|placeholder|description|aria-label|alt)=\{?"([^"\n]{8,300})"')

achados = collections.Counter()
detalhe = collections.defaultdict(list)

for arquivo in RAIZ.rglob("*.tsx"):
    caminho = arquivo.as_posix()
    if "/test/" in caminho or arquivo.name.endswith(".test.tsx"):
        continue
    fonte = arquivo.read_text(encoding="utf-8")
    # Fora comentários de bloco: a documentação do arquivo é em PT de propósito.
    fonte = re.sub(r"/\*.*?\*/", "", fonte, flags=re.S)
    fonte = re.sub(r"^\s*//.*$", "", fonte, flags=re.M)
    for achado in TEXTO.finditer(fonte):
        texto = " ".join(achado.group(1).split())
        if len(texto) >= 8 and PT.search(texto):
            achados[caminho] += 1
            detalhe[caminho].append(texto)
    for achado in PROP.finditer(fonte):
        texto = achado.group(2)
        if PT.search(texto):
            achados[caminho] += 1
            detalhe[caminho].append(f"[{achado.group(1)}] {texto}")

print("TOTAL:", sum(achados.values()), "trechos em", len(achados), "arquivos\n")
for caminho, quantos in achados.most_common(25):
    print(f"{quantos:3}  {caminho}")
