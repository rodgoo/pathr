"""Códigos prontos com execução comentada, linha a linha.

## O problema que isto resolve

Ler código pronto ensina pouco. A pessoa passa os olhos, reconhece as palavras
e segue — a mesma ilusão de competência que o Feynman (routers/explanations.py)
existe para quebrar, só que com código. O que ensina é ver o programa RODAR: a
linha que está executando agora, o que cada variável vale nesse instante, e o
que já foi impresso.

É isso que um depurador dá a quem já sabe usar um. Quem está aprendendo não
tem ambiente montado, não sabe pôr breakpoint, e desiste antes. Aqui o passo a
passo vem junto com o código.

## O traço é conferido, não acreditado

Quem produz o traço é um modelo de linguagem, e modelo de linguagem erra
aritmética e erra ordem de execução. Exibir o que ele disser como se fosse a
execução de verdade seria ensinar errado com cara de autoridade — pior que não
ter o recurso.

Então o traço passa por `conferir()` antes de virar tela: passo que aponta
para linha que não existe, passo que aponta para linha em branco, traço vazio
ou grande demais são recusados. Isso não prova que o traço está certo — prova
que ele é COERENTE com o código exibido, que é o erro que aparece na prática
quando o modelo inventa.

O que resta de incerteza é dito na tela, não escondido: a execução é comentada,
não medida. Por isso o prompt exige programa curto, determinístico, sem
entrada, sem rede e sem aleatoriedade — as três coisas que tornariam o traço
impossível de conferir até rodando.
"""

from __future__ import annotations

import unicodedata
from typing import Any

# As linguagens oferecidas. `rotulo` é o que aparece na tela; `realce` é o
# identificador de sintaxe que o bloco de código usa.
LINGUAGENS: tuple[dict[str, str], ...] = (
    {"id": "python", "rotulo": "Python", "realce": "python"},
    {"id": "javascript", "rotulo": "JavaScript", "realce": "javascript"},
    {"id": "typescript", "rotulo": "TypeScript", "realce": "typescript"},
    {"id": "java", "rotulo": "Java", "realce": "java"},
    {"id": "csharp", "rotulo": "C#", "realce": "csharp"},
    {"id": "go", "rotulo": "Go", "realce": "go"},
    {"id": "rust", "rotulo": "Rust", "realce": "rust"},
    {"id": "c", "rotulo": "C", "realce": "c"},
    {"id": "cpp", "rotulo": "C++", "realce": "cpp"},
    {"id": "php", "rotulo": "PHP", "realce": "php"},
    {"id": "ruby", "rotulo": "Ruby", "realce": "ruby"},
    {"id": "kotlin", "rotulo": "Kotlin", "realce": "kotlin"},
    {"id": "swift", "rotulo": "Swift", "realce": "swift"},
    {"id": "dart", "rotulo": "Dart", "realce": "dart"},
    {"id": "sql", "rotulo": "SQL", "realce": "sql"},
    {"id": "bash", "rotulo": "Shell / Bash", "realce": "bash"},
    {"id": "powershell", "rotulo": "PowerShell", "realce": "powershell"},
    {"id": "html", "rotulo": "HTML", "realce": "html"},
    {"id": "css", "rotulo": "CSS", "realce": "css"},
    # Arquivos de configuração e de ferramenta. Não são "linguagens que se
    # estudam" no perfil, mas é neles que Git, CI, Docker e nuvem acontecem de
    # verdade — um workflow do GitHub é YAML, não Java.
    {"id": "yaml", "rotulo": "YAML (GitHub Actions, Compose, Kubernetes)", "realce": "yaml"},
    {"id": "dockerfile", "rotulo": "Dockerfile", "realce": "dockerfile"},
    {"id": "json", "rotulo": "JSON", "realce": "json"},
    {"id": "xml", "rotulo": "XML (pom.xml, configurações)", "realce": "xml"},
    {"id": "terraform", "rotulo": "Terraform (HCL)", "realce": "terraform"},
)

_POR_ID = {linguagem["id"]: linguagem for linguagem in LINGUAGENS}

# Oferecidos a todo mundo, com ou sem perfil: ninguém marca "YAML" como
# linguagem que estuda, e ainda assim quem estuda CI precisa dele.
FORMATOS: tuple[str, ...] = ("yaml", "dockerfile", "json", "xml", "terraform")

# "Automático": o gerador escolhe os arquivos e as linguagens que o assunto usa
# na vida real (routers/walkthroughs.py). É o padrão, porque quem pede "GitHub e
# testes automatizados" não precisa saber que isso é um YAML chamando um teste.
AUTO = "auto"
AUTOMATICO = {"id": AUTO, "rotulo": "Automático (pelo assunto)", "realce": "text"}

NIVEIS: tuple[str, ...] = ("iniciante", "intermediario", "avancado")

# Um traço mais curto que isto não mostra execução nenhuma; mais longo que isto
# ninguém percorre até o fim, e é sinal de que o modelo gerou um programa
# grande demais para o formato.
MINIMO_DE_PASSOS = 2
MAXIMO_DE_PASSOS = 60
_MAXIMO_DE_LINHAS = 80


def existe(linguagem: str) -> bool:
    return linguagem in _POR_ID


def pode_pedir(linguagem: str) -> bool:
    """O que o pedido de exemplo aceita: uma linguagem da lista ou "auto"."""
    return linguagem == AUTO or existe(linguagem)


def realce(linguagem: str) -> str:
    return _POR_ID.get(linguagem, {}).get("realce", "text")


def rotulo(linguagem: str) -> str:
    if linguagem == AUTO:
        return AUTOMATICO["rotulo"]
    if linguagem == "texto":
        return "Texto"
    return _POR_ID.get(linguagem, {}).get("rotulo", linguagem)


def catalogo() -> list[dict[str, str]]:
    return [dict(linguagem) for linguagem in LINGUAGENS]


def linhas_de(codigo: str) -> list[str]:
    """As linhas como a tela vai numerá-las: 1-based, sem o \n final solto."""
    return codigo.replace("\r\n", "\n").rstrip("\n").split("\n")


def conferir(codigo: str, passos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deixa passar só o traço coerente com o código. Devolve [] se não houver.

    Recusar é melhor que consertar: um passo que aponta para a linha errada,
    silenciosamente movido para a linha mais próxima, ensinaria uma ordem de
    execução falsa com a mesma cara de certeza. Sem traço coerente, a tela
    mostra o código e a explicação e diz que o passo a passo não saiu.
    """
    linhas = linhas_de(codigo)
    if not linhas or len(linhas) > _MAXIMO_DE_LINHAS:
        return []

    limpos: list[dict[str, Any]] = []
    for passo in passos[:MAXIMO_DE_PASSOS]:
        try:
            numero = int(passo.get("linha"))
        except (TypeError, ValueError):
            return []
        if not 1 <= numero <= len(linhas):
            return []
        # Linha em branco não executa. Um traço que para numa delas não está
        # descrevendo este programa.
        if not linhas[numero - 1].strip():
            return []
        acao = str(passo.get("acao") or "").strip()
        if not acao:
            return []

        estado = passo.get("estado")
        limpos.append(
            {
                "linha": numero,
                "acao": acao,
                "estado": estado_limpo(estado),
                "saida": str(passo.get("saida") or ""),
            }
        )

    if len(limpos) < MINIMO_DE_PASSOS:
        return []

    # O traço precisa CHEGAR AO FIM, e não só ser coerente onde existe.
    #
    # O modelo às vezes descreve os três primeiros passos e para — a recursão
    # nunca desenrola, o laço nunca fecha, e nada é impresso. Isso passa em
    # todas as checagens acima (as linhas existem, não estão em branco, têm
    # descrição) e ainda assim é pior que traço nenhum: a pessoa acompanha até
    # a metade e conclui que o programa termina ali.
    #
    # O prompt obriga o programa a imprimir. Então um traço que não contém
    # NENHUMA saída não chegou ao primeiro print — é truncado, por definição.
    if not any(passo["saida"] for passo in limpos):
        return []

    return limpos


def estado_limpo(bruto: Any) -> list[dict[str, str]]:
    """As variáveis vivas no fim do passo, como pares nome/valor em texto.

    Texto e não número: o painel mostra o valor, não faz conta com ele, e um
    modelo que devolve `3` numa hora e `"3"` na outra não pode quebrar a tela.
    """
    if not isinstance(bruto, list):
        return []
    saida: list[dict[str, str]] = []
    for item in bruto[:12]:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("nome") or "").strip()
        if not nome:
            continue
        saida.append({"nome": nome[:40], "valor": str(item.get("valor", ""))[:120]})
    return saida


def saida_acumulada(passos: list[dict[str, Any]], ate: int) -> str:
    """Tudo que o programa imprimiu até o passo `ate` (inclusive, 0-based).

    Acumulada e não por passo: o painel de saída de um depurador cresce, e
    mostrar só a linha do passo atual faria a impressão anterior sumir ao
    avançar — o oposto do que a pessoa precisa ver para seguir o programa.
    """
    pedacos = [p["saida"] for p in passos[: ate + 1] if p.get("saida")]
    return "\n".join(pedacos)


# ---------------------------------------------------------------------------
# O laboratório de cada pessoa: as linguagens dela e o que abrir a seguir
# ---------------------------------------------------------------------------

# A tag do catálogo (slug) que corresponde a cada linguagem do laboratório.
_LINGUAGEM_DA_TAG: dict[str, str] = {
    "python": "python", "javascript": "javascript", "typescript": "typescript",
    "java": "java", "c-sharp": "csharp", "go": "go", "rust": "rust", "c": "c",
    "c-plus-plus": "cpp", "php": "php", "ruby": "ruby", "kotlin": "kotlin",
    "swift": "swift", "dart": "dart", "sql": "sql", "shell-script": "bash",
    "powershell": "powershell", "html": "html", "css": "css",
}

# Tecnologia de um módulo do roadmap que se estuda em código de uma linguagem.
# Mais de uma candidata: vale a primeira que a pessoa tem no perfil.
_LINGUAGEM_DO_ASSUNTO: dict[str, tuple[str, ...]] = {
    **{slug: ("java",) for slug in (
        "spring-boot", "spring-security", "jpa", "hibernate", "junit", "mockito",
        "maven", "gradle", "quarkus", "jakarta-ee",
    )},
    **{slug: ("typescript", "javascript") for slug in (
        "node-js", "express", "nestjs", "jest", "react", "angular", "vue-js", "next-js",
    )},
    **{slug: ("python",) for slug in ("django", "flask", "fastapi", "pandas")},
    **{slug: ("sql",) for slug in ("postgresql", "mysql", "oracle", "sql-server")},
    "net": ("csharp",),
    "laravel": ("php",),
    "flutter": ("dart",),
    "android": ("kotlin",),
    # Ferramentas: estudam-se nos arquivos de configuração delas, que servem a
    # qualquer pessoa (FORMATOS), com ou sem a linguagem no perfil.
    **{slug: ("yaml",) for slug in (
        "github", "github-actions", "gitlab", "gitlab-ci", "ci-cd", "docker-compose", "kubernetes", "ansible",
    )},
    "docker": ("dockerfile",),
    "terraform": ("terraform",),
    "git": ("bash",),
}

# Uma trilha por linguagem, do básico ao avançado. Assuntos que cabem num
# programa curto e determinístico — o formato do laboratório (ver o prompt em
# routers/walkthroughs.py).
_TRILHAS: dict[str, dict[str, tuple[str, ...]]] = {
    "java": {
        "iniciante": ("variáveis, tipos e operadores", "if/else e switch", "laços for e while", "arrays e percorrer com for-each", "métodos com parâmetros e retorno"),
        "intermediario": ("classes, objetos e construtores", "herança e polimorfismo", "interfaces e classes abstratas", "List, Set e Map", "Streams: filter, map e collect", "tratamento de exceções com try/catch", "Optional sem NullPointerException"),
        "avancado": ("generics com wildcards", "records e sealed interfaces", "equals, hashCode e coleções", "CompletableFuture encadeado", "padrão Strategy com lambdas"),
    },
    "javascript": {
        "iniciante": ("let, const e tipos", "funções e arrow functions", "arrays: push, map e filter", "objetos e desestruturação", "laços for...of e for...in"),
        "intermediario": ("closures", "this em funções e arrow functions", "Promises e async/await", "reduce na prática", "spread e rest", "classes e herança"),
        "avancado": ("event loop: microtasks e macrotasks", "generators e iterators", "prototypes por baixo das classes", "memoização com Map", "debounce implementado do zero"),
    },
    "typescript": {
        "iniciante": ("tipos básicos e inferência", "interfaces e type aliases", "funções tipadas", "union types e narrowing", "arrays e tuplas tipadas"),
        "intermediario": ("generics em funções", "tipos utilitários: Partial, Pick e Record", "discriminated unions com switch", "classes com modificadores de acesso", "enums versus union de literais"),
        "avancado": ("conditional types", "mapped types", "type guards personalizados", "infer em tipos condicionais", "generics com restrições (extends keyof)"),
    },
    "python": {
        "iniciante": ("variáveis e tipos", "if/elif/else", "laços for e range", "listas e fatiamento", "funções com parâmetros padrão"),
        "intermediario": ("list comprehension", "dicionários e sets", "classes e métodos especiais", "tratamento de exceções", "decorators simples"),
        "avancado": ("generators e yield", "context managers", "dataclasses e ordenação", "recursão com memoização", "closures e nonlocal"),
    },
    "sql": {
        "iniciante": ("SELECT com WHERE e ORDER BY", "INSERT, UPDATE e DELETE", "funções de agregação com GROUP BY"),
        "intermediario": ("INNER JOIN e LEFT JOIN", "HAVING depois do GROUP BY", "subconsultas", "CASE WHEN"),
        "avancado": ("window functions: ROW_NUMBER e SUM OVER", "CTE recursiva", "transações e níveis de isolamento"),
    },
    "csharp": {
        "iniciante": ("variáveis e tipos", "laços e condicionais", "métodos"),
        "intermediario": ("classes e propriedades", "LINQ: Where, Select e GroupBy", "interfaces", "exceções"),
        "avancado": ("async/await com Task", "generics", "records e pattern matching"),
    },
    "yaml": {
        "iniciante": ("GitHub Actions: rodar os testes a cada push", "Docker Compose: API e banco de dados juntos"),
        "intermediario": ("GitHub Actions: matriz de versões e cache de dependências", "Kubernetes: Deployment e Service"),
        "avancado": ("GitHub Actions: build, testes e deploy com environments", "Kubernetes: ConfigMap, Secret e probes"),
    },
    "dockerfile": {
        "iniciante": ("Dockerfile de uma API: FROM, COPY, RUN e CMD",),
        "intermediario": ("build em múltiplos estágios",),
        "avancado": ("imagem enxuta com usuário sem root e HEALTHCHECK",),
    },
}
_TRILHA_GENERICA: dict[str, tuple[str, ...]] = {
    "iniciante": ("variáveis e tipos", "condicionais", "laços", "funções"),
    "intermediario": ("estruturas de dados da linguagem", "tratamento de erros", "recursão"),
    "avancado": ("concorrência sem aleatoriedade", "tipos genéricos", "padrões de projeto"),
}

_NIVEL_PELA_PROFICIENCIA = {0: "iniciante", 1: "iniciante", 2: "intermediario", 3: "intermediario", 4: "avancado", 5: "avancado"}


def _normaliza_assunto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return " ".join(sem_acento.split())


def linguagens_do_perfil(minhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """As linguagens do laboratório que a pessoa marcou no perfil, com o nível
    que ela tem em cada uma. A que é meta vem primeiro, depois a mais forte."""
    achadas = []
    for tag in minhas:
        linguagem = _LINGUAGEM_DA_TAG.get(str(tag.get("slug") or ""))
        if linguagem:
            achadas.append({
                **_POR_ID[linguagem],
                "proficiencia": int(tag.get("proficiency") or 0),
                "meta": bool(tag.get("is_target")),
            })
    achadas.sort(key=lambda l: (not l["meta"], -l["proficiencia"], l["rotulo"]))
    return achadas


def sugerir(
    minhas: list[dict[str, Any]],
    modulos: list[dict[str, Any]],
    ja_gerados: set[str],
    limite: int = 12,
) -> dict[str, Any]:
    """O que o laboratório oferece a esta pessoa, sem IA.

    - `linguagens`: só as do perfil. Sem nenhuma, todas — e a tela avisa.
    - `sugestoes`: primeiro o que o roadmap está pedindo agora (o módulo em
      andamento, depois os próximos), no nível da pessoa naquela linguagem;
      depois a trilha de cada linguagem, no nível dela; e um "próximo passo",
      um nível acima. O que ela já gerou não volta.

    `modulos` são os do plano principal, em ordem, com `titulo`, `status`,
    `objetivos` e `tags` (slugs).
    """
    do_perfil = linguagens_do_perfil(minhas)
    ids = [l["id"] for l in do_perfil]
    nivel_de = {l["id"]: _NIVEL_PELA_PROFICIENCIA[min(max(l["proficiencia"], 0), 5)] for l in do_perfil}
    vistos = {_normaliza_assunto(t) for t in ja_gerados}
    sugestoes: list[dict[str, Any]] = []

    def acrescenta(linguagem: str, assunto: str, nivel: str, motivo: str, origem: str) -> bool:
        chave = _normaliza_assunto(assunto)
        if chave in vistos or len(sugestoes) >= limite:
            return False
        vistos.add(chave)
        sugestoes.append({
            "language": linguagem,
            "language_label": rotulo(linguagem),
            "topic": assunto[:120],
            "level": nivel,
            "motivo": motivo,
            "origem": origem,
        })
        return True

    # 1. O roadmap: o módulo em andamento antes dos que estão por fazer.
    pendentes = [m for m in modulos if m.get("status") not in ("done", "skipped")]
    pendentes.sort(key=lambda m: m.get("status") != "doing")
    do_roadmap = 0
    for modulo in pendentes:
        if do_roadmap >= 3:
            break
        candidatas: list[str] = []
        for slug in modulo.get("tags") or []:
            if slug in _LINGUAGEM_DA_TAG:
                candidatas.append(_LINGUAGEM_DA_TAG[slug])
            candidatas.extend(_LINGUAGEM_DO_ASSUNTO.get(slug, ()))
        # Linguagem do perfil primeiro; senão, o arquivo da ferramenta (o
        # workflow YAML, o Dockerfile). Sem nenhum dos dois — AWS pelo console,
        # soft skills — o laboratório não é o lugar.
        linguagem = next((c for c in candidatas if c in ids), None) or next(
            (c for c in candidatas if c in FORMATOS or (c == "bash" and ids)), None
        )
        if not linguagem:
            continue
        objetivo = next(iter(modulo.get("objetivos") or []), "")
        titulo = str(modulo.get("titulo") or "").strip()
        assunto = f"{titulo}: {objetivo.rstrip('.')}" if objetivo else titulo
        situacao = "Em andamento" if modulo.get("status") == "doing" else "Próximo"
        nivel = nivel_de.get(linguagem, "iniciante")
        if acrescenta(linguagem, assunto, nivel, f"{situacao} no seu roadmap: {titulo}", "roadmap"):
            do_roadmap += 1

    # 2. A trilha de cada linguagem, alternando entre elas. Sobra lugar para
    # o próximo passo de cada uma.
    trilhas = {l: list((_TRILHAS.get(l) or _TRILHA_GENERICA)[nivel_de[l]]) for l in ids}
    while len(sugestoes) < limite - len(ids) and any(trilhas.values()):
        for linguagem in ids:
            if trilhas[linguagem] and len(sugestoes) < limite - len(ids):
                assunto = trilhas[linguagem].pop(0)
                acrescenta(linguagem, assunto, nivel_de[linguagem], f"Para o seu nível em {rotulo(linguagem)}", "trilha")

    # 3. Um passo acima em cada linguagem: onde a pessoa chega a seguir.
    for linguagem in ids:
        atual = nivel_de[linguagem]
        if atual == "avancado":
            continue
        proximo = NIVEIS[NIVEIS.index(atual) + 1]
        for assunto in (_TRILHAS.get(linguagem) or _TRILHA_GENERICA)[proximo]:
            if acrescenta(linguagem, assunto, proximo, f"Próximo passo em {rotulo(linguagem)}", "proximo_nivel"):
                break

    so_do_perfil = [
        {chave: valor for chave, valor in l.items() if chave in ("id", "rotulo", "realce")} for l in do_perfil
    ]
    return {
        # O automático primeiro (é o padrão da tela); depois as do perfil e os
        # formatos de ferramenta, que valem para todo mundo.
        "linguagens": [dict(AUTOMATICO)]
        + (
            so_do_perfil + [dict(_POR_ID[f]) for f in FORMATOS if f not in ids]
            if so_do_perfil
            else catalogo()
        ),
        "do_perfil": bool(do_perfil),
        "sugestoes": sugestoes,
    }
