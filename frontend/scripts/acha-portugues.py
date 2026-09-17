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

# Frase escrita dentro de uma expressão: {"Salvo"}, {ok ? "Salvo" : "Salvar"},
# label={pendente ? "Enviando…" : "Enviar"}. Sem acento nenhum, o primeiro
# varredor passava direto por tudo isso — e "Save"/"Salvo" fixos são o caso
# mais comum, porque rótulo curto raramente leva acento.
FRASE = re.compile(r'"([A-ZÀ-Úa-zà-ú][^"\n]{2,120})"')

# O que é código e não texto: nada disso vai para o dicionário. A primeira
# alternativa cobre lista de classe CSS e de `rel` ("btn btn-ghost", "noopener
# noreferrer"): palavras todas minúsculas, com hífen — rótulo escrito para gente
# começa com maiúscula ou leva acento, e cai fora desta regra.
TECNICO = re.compile(
    r"^(?:[a-z][a-z0-9-]*(?:[ /][a-z][a-z0-9-]*)*|#[0-9a-f]{3,8}|\d[\d.,%a-z ]*|"
    r"[\w.-]+\.(?:svg|png|json|ts|tsx)|https?://\S+|[a-z]+[A-Z]\w*|[\w.-]+@[\w.-]+|"
    r"rgba?\([^)]*\)|\S{1,3})$"
)

# Duas fontes de ruído que só apareceram rodando: o `d` de um <path> de ícone
# ("M15 6V21M15 6L21 3…") e o código de exemplo que a landing mostra na tela.
# Nenhum é frase, e os dois aparecem às dezenas por arquivo — deixados de fora,
# a lista de suspeitas volta a caber numa tela.
CAMINHO_SVG = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz][\d\s.,-]")
CODIGO = re.compile(r"[;{}<>]|=>|\(\)|\bconst\b|\bawait\b|\breturn\b")

achados = collections.Counter()
detalhe = collections.defaultdict(list)
suspeitas = collections.Counter()

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

    # Segunda passada, mais solta: frase entre aspas que NÃO está dentro de um
    # t(...). Aqui não se exige acento — por isso vai para uma lista separada,
    # de suspeitas: rótulo de verdade e nome de ícone se parecem muito.
    sem_t = re.sub(r"\bt\(\s*\"[^\"]+\"(?:\s*,\s*\{[^}]*\})?\s*\)", "", fonte)
    sem_t = re.sub(r"\bt\(\s*[^)]*\)", "", sem_t)  # t(cond ? "a" : "b")
    sem_t = re.sub(r"\bimport[^;]+;", "", sem_t)
    for achado in FRASE.finditer(sem_t):
        texto = achado.group(1).strip()
        if TECNICO.match(texto) or PT.search(texto):
            continue  # já contado acima, ou é código
        if CAMINHO_SVG.match(texto) or CODIGO.search(texto):
            continue
        if " " in texto or texto[0].isupper():
            suspeitas[caminho] += 1

print("TOTAL:", sum(achados.values()), "trechos em", len(achados), "arquivos\n")
for caminho, quantos in achados.most_common(25):
    print(f"{quantos:3}  {caminho}  (+{suspeitas.get(caminho, 0)} suspeitas)")

restantes = [(c, n) for c, n in suspeitas.most_common() if c not in achados]
if restantes:
    print("\nSó suspeitas (frase entre aspas, sem acento, fora de t()):")
    for caminho, quantos in restantes[:15]:
        print(f"{quantos:3}  {caminho}")
