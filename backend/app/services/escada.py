"""A ordem em que se aprende: o grafo de pré-requisitos entre tecnologias.

## Por que isto existe

A trilha precisa ir do mais fácil para o mais difícil, e "mais fácil" não é
uma propriedade do assunto — é uma propriedade da POSIÇÃO dele no que já se
sabe. Docker não é difícil em si; é difícil para quem ainda não consegue rodar
a aplicação que vai empacotar. Kubernetes não é difícil em si; é impossível
para quem não sabe o que é um contêiner.

Antes, essa ordem era pedida ao modelo em uma linha do prompt ("em ordem de
dependência") e conferida por ninguém. Ordenar é justamente o que o modelo
mais erra, e aqui o custo do erro é a trilha inteira começar no lugar errado —
a pessoa abre o plano, vê Docker na primeira semana e não tem como saber que
aquilo está fora de ordem.

Agora a ordem é DADO, não palpite. É a mesma ideia do roadmap.sh: um grafo
curado, revisável, que diz o que vem antes do quê.

## Como se lê

`PRE_REQUISITOS` lista, para cada tecnologia, o que precisa vir antes dela.
Só a aresta DIRETA é declarada — que Kubernetes depende de Linux é derivado,
porque Docker já depende. Declarar o transitivo encheria a tabela de ruído e
a faria mentir na primeira vez que alguém corrigisse só um dos caminhos.

A `camada` de cada tecnologia é o comprimento do caminho mais longo até uma
raiz, calculado uma vez no import. É esse número que ordena a trilha: camada 0
é o que se aprende sem depender de nada, e cada camada acima só faz sentido
depois da anterior.

## O que NÃO está aqui

Preferência. O grafo não diz se alguém deve aprender Java ou Python — os dois
são camada 0 e a escolha é do objetivo da pessoa. Ele só diz que qualquer um
dos dois vem antes de Spring Boot ou Django.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

# O que precisa vir ANTES de cada tecnologia. Só arestas diretas.
#
# A regra que guiou cada linha: "é possível estudar X com proveito sem saber
# Y?" Se não for, Y é pré-requisito. Onde a resposta é "dá, mas é pior",
# NÃO virou aresta — o grafo trava a trilha, e travar por preferência
# transformaria conselho em obstáculo.
PRE_REQUISITOS: dict[str, tuple[str, ...]] = {
    # --- Fundamento de tudo que roda em servidor ---
    # Git antes de qualquer colaboração: não dá para revisar código, abrir PR
    # ou automatizar entrega sem versionar primeiro.
    "Code review": ("Git",),
    "CI/CD": ("Git",),
    "GitHub Actions": ("CI/CD",),
    "Jenkins": ("CI/CD",),
    # Empacotar pressupõe ter o que empacotar, e mexer no sistema onde roda.
    "Docker": ("Linux",),
    "Kubernetes": ("Docker",),
    "Terraform": ("Docker",),
    "Nginx": ("Linux",),
    "Observabilidade": ("Docker",),
    # --- Web: a base antes do framework ---
    "CSS": ("HTML",),
    "Sass": ("CSS",),
    "Tailwind CSS": ("CSS",),
    "Acessibilidade": ("HTML",),
    "TypeScript": ("JavaScript",),
    "React": ("JavaScript", "CSS"),
    "Vue.js": ("JavaScript", "CSS"),
    "Angular": ("TypeScript", "CSS"),
    "Svelte": ("JavaScript", "CSS"),
    "Next.js": ("React",),
    "Redux": ("React",),
    "Webpack": ("JavaScript",),
    "Vite": ("JavaScript",),
    # --- Backend: a linguagem antes do framework dela ---
    "Node.js": ("JavaScript",),
    "Express": ("Node.js",),
    "NestJS": ("TypeScript", "Node.js"),
    "Spring Boot": ("Java",),
    "Spring Security": ("Spring Boot", "Segurança"),
    "JPA": ("Java", "SQL"),
    "JPA/Hibernate": ("Java", "SQL"),
    "Django": ("Python",),
    "Flask": ("Python",),
    "FastAPI": ("Python",),
    "Rails": ("Ruby",),
    "Laravel": ("PHP",),
    ".NET": ("C#",),
    # --- Dados: SQL antes de tudo que fala com banco ---
    "PostgreSQL": ("SQL",),
    "MySQL": ("SQL",),
    "Oracle": ("SQL",),
    "SQL Server": ("SQL",),
    "Modelagem de dados": ("SQL",),
    "MongoDB": ("Modelagem de dados",),
    "Redis": ("Modelagem de dados",),
    "Elasticsearch": ("Modelagem de dados",),
    "ETL": ("SQL",),
    "Spark": ("ETL",),
    "Pandas": ("Python",),
    "Power BI": ("SQL",),
    "Kafka": ("Arquitetura de software",),
    "RabbitMQ": ("Arquitetura de software",),
    # --- Arquitetura: só depois de ter o que arquitetar ---
    "REST": ("Arquitetura de software",),
    "GraphQL": ("REST",),
    "gRPC": ("REST",),
    "WebSocket": ("REST",),
    "Microsserviços": ("REST", "Docker"),
    # --- Testes: escrever antes de testar ---
    "Testes automatizados": ("Clean Code",),
    "JUnit": ("Java", "Testes automatizados"),
    "Jest": ("JavaScript", "Testes automatizados"),
    "Pytest": ("Python", "Testes automatizados"),
    "Cypress": ("Testes automatizados", "HTML"),
    # --- Mobile ---
    "Android": ("Kotlin",),
    "iOS": ("Swift",),
    "React Native": ("React",),
    "Flutter": ("Algoritmos",),
    # --- Nuvem: entender contêiner antes de orquestrar na nuvem ---
    "AWS": ("Linux",),
    "Azure": ("Linux",),
    "Google Cloud": ("Linux",),
    # --- IA ---
    "Machine Learning": ("Python", "Algoritmos"),
    "LLM": ("Machine Learning",),
    # --- Qualidade ---
    "Clean Code": ("Algoritmos",),
    "Arquitetura de software": ("Clean Code",),
    "Segurança": ("REST",),
}


@lru_cache(maxsize=1)
def _camadas() -> dict[str, int]:
    """Quantos passos, no MAIOR caminho, separam cada tecnologia de uma raiz.

    O caminho mais longo, e não o mais curto: se React precisa de JavaScript
    (camada 0) e de CSS (que precisa de HTML, camada 1), então React só é
    alcançável na camada 2 — a mais funda das duas. Usar o mais curto colocaria
    React ao lado de CSS e a trilha pediria os dois na mesma semana.

    Ciclo (que seria erro de curadoria) não trava nada: a recursão para no
    caminho já visitado, e a tecnologia fica na profundidade que deu.
    """
    profundidade: dict[str, int] = {}

    def medir(nome: str, visitados: frozenset[str]) -> int:
        if nome in profundidade:
            return profundidade[nome]
        if nome in visitados:
            return 0
        anteriores = PRE_REQUISITOS.get(nome, ())
        valor = (
            0
            if not anteriores
            else 1 + max(medir(a, visitados | {nome}) for a in anteriores)
        )
        profundidade[nome] = valor
        return valor

    for nome in PRE_REQUISITOS:
        medir(nome, frozenset())
    return profundidade


def camada(tecnologia: str) -> int:
    """A camada de uma tecnologia. Desconhecida vale 0 — não travar o que não
    se conhece é melhor que empurrar para o fim algo que pode ser fundamento.
    """
    return _camadas().get(tecnologia.strip(), 0)


def camada_do_conjunto(tecnologias: Iterable[str]) -> int:
    """A camada de um MÓDULO, que é a da tecnologia mais funda que ele exige.

    A mais funda, e não a média: um módulo que junta Git e Kubernetes só pode
    ser estudado por quem já alcançou Kubernetes. A média o colocaria no meio
    da trilha, onde ele não seria estudável.
    """
    valores = [camada(t) for t in tecnologias if t and t.strip()]
    return max(valores) if valores else 0


def pre_requisitos_de(tecnologia: str) -> tuple[str, ...]:
    return PRE_REQUISITOS.get(tecnologia.strip(), ())


def faltando(tecnologia: str, ja_sabe: Iterable[str]) -> list[str]:
    """O que falta, entre os pré-requisitos DIRETOS, para alguém encarar isto.

    Serve à tela: dizer "Kubernetes está travado" ajuda pouco; dizer "falta
    Docker" diz o que fazer a respeito.
    """
    conhecidas = {t.strip().lower() for t in ja_sabe if t}
    return [p for p in pre_requisitos_de(tecnologia) if p.lower() not in conhecidas]


def ordem_para_o_prompt(tecnologias: Iterable[str]) -> str:
    """As dependências entre as tecnologias DESTE plano, em texto.

    Vai para o prompt do gerador para ele já escrever o plano na ordem certa,
    em vez de a ordem ser só consertada depois. Corrigir depois reordena os
    módulos; escrever certo desde o começo faz o CONTEÚDO de cada módulo
    supor o que veio antes, que é o que uma trilha de verdade faz.
    """
    nomes = {t.strip() for t in tecnologias if t and t.strip()}
    linhas = []
    for nome in sorted(nomes):
        antes = [p for p in pre_requisitos_de(nome) if p in nomes]
        if antes:
            linhas.append(f"- {nome} só depois de {', '.join(antes)}")
    return "\n".join(linhas)
