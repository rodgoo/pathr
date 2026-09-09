"""O grafo de pre-requisitos: a ordem em que se aprende.

Este arquivo testa CONHECIMENTO CURADO, e nao codigo. A funcao que calcula
camada tem cinco linhas; o que pode estar errado e a tabela -- e um erro nela
nao quebra nada, so produz uma trilha que pede Docker antes de Linux e ninguem
percebe ate alguem estudar por ela.

Por isso os testes sao afirmacoes sobre a AREA, escritas como alguem da area
as diria: "Kubernetes depois de Docker", "framework depois da linguagem dele".
Se uma delas cair, ou a tabela regrediu ou a afirmacao envelheceu -- e as duas
merecem uma conversa, nao um ajuste automatico.
"""

import pytest

from app.services import escada


def _antes(anterior: str, posterior: str) -> bool:
    return escada.camada(anterior) < escada.camada(posterior)


# ---------------------------------------------------------------------------
# As perguntas que o produto precisa saber responder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "anterior,posterior",
    [
        # Versionar antes de colaborar e de automatizar.
        ("Git", "Code review"),
        ("Git", "CI/CD"),
        ("CI/CD", "GitHub Actions"),
        # Mexer no sistema antes de empacotar; empacotar antes de orquestrar.
        ("Linux", "Docker"),
        ("Docker", "Kubernetes"),
        ("Docker", "Microsserviços"),
        # A linguagem antes do framework dela.
        ("Java", "Spring Boot"),
        ("Python", "Django"),
        ("Ruby", "Rails"),
        ("PHP", "Laravel"),
        ("C#", ".NET"),
        ("JavaScript", "Node.js"),
        ("Node.js", "Express"),
        # A base da web antes das camadas.
        ("HTML", "CSS"),
        ("CSS", "Sass"),
        ("JavaScript", "TypeScript"),
        ("JavaScript", "React"),
        ("React", "Next.js"),
        ("React", "Redux"),
        ("React", "React Native"),
        # SQL antes de qualquer banco.
        ("SQL", "PostgreSQL"),
        ("SQL", "Modelagem de dados"),
        ("Modelagem de dados", "MongoDB"),
        # Escrever antes de testar; testar com a ferramenta da linguagem.
        ("Clean Code", "Testes automatizados"),
        ("Testes automatizados", "Pytest"),
        ("Java", "JUnit"),
        # Ter o que arquitetar antes de arquitetar.
        ("Clean Code", "Arquitetura de software"),
        ("Arquitetura de software", "REST"),
        ("REST", "GraphQL"),
    ],
)
def test_o_que_vem_antes_vem_antes(anterior, posterior):
    assert _antes(anterior, posterior), (
        f"{anterior} deveria vir antes de {posterior}, "
        f"mas as camadas sao {escada.camada(anterior)} e {escada.camada(posterior)}"
    )


# ---------------------------------------------------------------------------
# Propriedades do grafo
# ---------------------------------------------------------------------------


def test_toda_tecnologia_vem_depois_de_todos_os_seus_pre_requisitos():
    """A invariante que sustenta a ordenacao inteira. Se ela cai, a trilha
    pode pedir algo antes do que ele exige -- e o resto dos testes aqui viram
    casos isolados de um problema geral."""
    quebradas = [
        (nome, pre)
        for nome, pres in escada.PRE_REQUISITOS.items()
        for pre in pres
        if escada.camada(pre) >= escada.camada(nome)
    ]
    assert not quebradas, f"pre-requisito na mesma camada ou depois: {quebradas}"


def test_o_fundamento_esta_na_camada_zero():
    """Linguagem, Git, Linux, HTML, SQL e Algoritmos nao dependem de nada
    dentro do produto: sao por onde alguem comeca."""
    for base in ("Git", "Linux", "HTML", "SQL", "Java", "Python", "JavaScript", "Algoritmos"):
        assert escada.camada(base) == 0, f"{base} deveria ser fundamento"


def test_tecnologia_desconhecida_nao_trava_a_trilha():
    """Tag fora do grafo vale 0. Empurrar o desconhecido para o fim mandaria
    para o fim da trilha justamente o que pode ser fundamento."""
    assert escada.camada("Tecnologia Que Nao Existe") == 0


def test_o_modulo_herda_a_camada_da_tecnologia_mais_funda():
    """Um modulo que junta Git e Kubernetes so e estudavel por quem alcancou
    Kubernetes. A media o poria no meio da trilha, onde nao seria estudavel."""
    assert escada.camada_do_conjunto(["Git", "Kubernetes"]) == escada.camada("Kubernetes")


def test_modulo_sem_tecnologia_nao_e_empurrado_para_o_fim():
    assert escada.camada_do_conjunto([]) == 0


# ---------------------------------------------------------------------------
# O que a tela e o prompt consomem
# ---------------------------------------------------------------------------


def test_diz_o_que_falta_para_encarar_uma_tecnologia():
    """A tela precisa disto: "Kubernetes travado" ajuda pouco; "falta Docker"
    diz o que fazer a respeito."""
    assert escada.faltando("Kubernetes", ["Linux"]) == ["Docker"]
    assert escada.faltando("Kubernetes", ["Docker"]) == []


def test_o_prompt_recebe_so_as_dependencias_do_plano():
    """Mandar o grafo inteiro gastaria contexto com tecnologia que nao esta no
    plano, e o prompt e cobrado por token."""
    texto = escada.ordem_para_o_prompt(["Java", "Spring Boot", "Kubernetes"])
    assert "Spring Boot só depois de Java" in texto
    # Docker nao esta na lista, entao a dependencia de Kubernetes nao aparece.
    assert "Kubernetes" not in texto


def test_o_prompt_fica_vazio_sem_dependencia_entre_as_tecnologias():
    """Tres fundamentos nao tem ordem entre si, e inventar uma seria pior que
    calar: o objetivo da pessoa decide, nao o grafo."""
    assert escada.ordem_para_o_prompt(["Java", "Python", "Git"]) == ""
