"""Exemplos com vários arquivos, e a conferência de que são de verdade.

O que se segura: o workflow do GitHub é YAML válido, com `on`, `jobs`, `steps`
e actions na versão atual; Java compila no básico (classe pública = arquivo,
pacote = pasta, jakarta no lugar de javax); o traço entre arquivos aponta para
arquivo e linha que existem; e o gerador devolve o motivo da recusa ao modelo,
nunca grava conteúdo recusado, e aceita "auto".
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import walkthroughs
from app.services import code_lab_projeto as P
from tests.fake_supabase import FakeSupabase

WORKFLOW = """name: CI
on:
  push:
    branches: [main]
jobs:
  testes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
      - run: mvn -B test
"""

TESTE_JAVA = """package com.exemplo.produto;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class CalculadoraTest {
    @Test
    void soma() {
        assertEquals(4, 2 + 2);
    }
}
"""

ENTIDADE = """package com.exemplo.produto;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class Produto {
    @Id
    private Long id;
    private String nome;
}
"""


def arq(caminho, conteudo):
    return {"caminho": caminho, "conteudo": conteudo}


def normalizados(*arquivos):
    limpos, motivo = P.normalizar(list(arquivos))
    assert motivo is None, motivo
    return limpos


# --- a linguagem sai do nome do arquivo ------------------------------------------


@pytest.mark.parametrize(
    "caminho,linguagem",
    [
        (".github/workflows/ci.yml", "yaml"),
        ("compose.yaml", "yaml"),
        ("Dockerfile", "dockerfile"),
        ("src/main/java/com/exemplo/App.java", "java"),
        ("infra/main.tf", "terraform"),
        ("package.json", "json"),
        (".gitignore", "texto"),
    ],
)
def test_linguagem_pelo_nome(caminho, linguagem):
    assert P.linguagem_do_arquivo(caminho) == linguagem


@pytest.mark.parametrize(
    "arquivos,trecho",
    [
        ([], "nenhum"),
        ([arq("/etc/passwd", "x")], "caminho"),
        ([arq("../fora.yml", "x")], "caminho"),
        ([arq("a.yml", "x: 1"), arq("a.yml", "y: 2")], "repetido"),
        ([arq("a.yml", "   ")], "vazio"),
        ([arq(f"f{i}.yml", "x: 1") for i in range(7)], "mais de 6"),
    ],
)
def test_arquivos_invalidos_sao_recusados(arquivos, trecho):
    limpos, motivo = P.normalizar(arquivos)
    assert limpos == [] and trecho in motivo


# --- conteúdo real ---------------------------------------------------------------


def test_workflow_real_passa():
    assert P.problemas(normalizados(arq(".github/workflows/ci.yml", WORKFLOW))) == []


def test_yaml_quebrado_e_recusado():
    quebrado = "jobs:\n  testes:\n    runs-on: ubuntu-latest\n   steps: [\n"
    achados = P.problemas(normalizados(arq("config.yml", quebrado)))
    assert achados and "YAML inválido" in achados[0]


def test_workflow_sem_on_sem_steps_e_com_action_velha():
    velho = "name: CI\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2\n  vazio:\n    runs-on: ubuntu-latest\n"
    achados = " | ".join(P.problemas(normalizados(arq(".github/workflows/ci.yml", velho))))
    assert "sem `on`" in achados
    assert "actions/checkout@v2 está desatualizada" in achados
    assert "job vazio sem `steps`" in achados


def test_uses_inventado_e_recusado():
    ruim = WORKFLOW.replace("actions/setup-java@v4", "configurar java agora")
    achados = P.problemas(normalizados(arq(".github/workflows/ci.yml", ruim)))
    assert any("não é uma referência de action válida" in a for a in achados)


def test_java_classe_pacote_e_jakarta():
    assert P.problemas(normalizados(arq("src/main/java/com/exemplo/produto/Produto.java", ENTIDADE))) == []
    errado = ENTIDADE.replace("jakarta.persistence", "javax.persistence").replace("public class Produto", "public class Item")
    achados = " | ".join(P.problemas(normalizados(arq("src/main/java/com/exemplo/loja/Produto.java", errado))))
    assert "Item precisa estar em Item.java" in achados
    assert "package com.exemplo.loja;" in achados
    assert "jakarta" in achados


def test_chaves_que_nao_fecham():
    achados = P.problemas(normalizados(arq("Main.java", "public class Main {\n  void x() {\n}\n")))
    assert any("não fecham" in a for a in achados)
    # Chave dentro de texto e de comentário não conta; URL com // também não.
    ok = 'class A {\n  String s = "}";\n  // }\n  String u = "https://x";\n}\n'
    assert P.problemas(normalizados(arq("A.java", ok))) == []


def test_dockerfile_json_e_compose():
    assert P.problemas(normalizados(arq("Dockerfile", "FROM eclipse-temurin:21-jre\nCOPY app.jar /app.jar\nCMD [\"java\", \"-jar\", \"/app.jar\"]\n"))) == []
    assert P.problemas(normalizados(arq("Dockerfile", "COPY . .\nrodar tudo\n")))
    assert P.problemas(normalizados(arq("package.json", '{"name": "x",}')))
    assert P.problemas(normalizados(arq("compose.yaml", "version: '3'\n")))


# --- o traço entre arquivos --------------------------------------------------------


def test_traco_passa_de_um_arquivo_para_outro():
    arquivos = normalizados(arq(".github/workflows/ci.yml", WORKFLOW), arq("src/test/java/com/exemplo/produto/CalculadoraTest.java", TESTE_JAVA))
    passos = [
        {"arquivo": ".github/workflows/ci.yml", "linha": 2, "acao": "o push na main dispara o workflow"},
        {"arquivo": ".github/workflows/ci.yml", "linha": 14, "acao": "roda mvn -B test", "saida": "[INFO] Running com.exemplo.produto.CalculadoraTest"},
        {"arquivo": "src/test/java/com/exemplo/produto/CalculadoraTest.java", "linha": 9, "acao": "assertEquals(4, 4) passa", "saida": "Tests run: 1, Failures: 0"},
    ]
    conferido = P.conferir_traco(arquivos, passos)
    assert [p["arquivo"] for p in conferido] == [p["arquivo"] for p in passos]


def test_traco_com_arquivo_que_nao_existe_ou_sem_arquivo_e_recusado():
    arquivos = normalizados(arq("a.yml", "x: 1\ny: 2"), arq("b.yml", "z: 3"))
    assert P.conferir_traco(arquivos, [{"arquivo": "c.yml", "linha": 1, "acao": "x", "saida": "s"}, {"arquivo": "a.yml", "linha": 2, "acao": "y"}]) == []
    assert P.conferir_traco(arquivos, [{"linha": 1, "acao": "x", "saida": "s"}, {"linha": 1, "acao": "y"}]) == []
    # Um arquivo só: o passo sem `arquivo` vale para ele.
    unico = normalizados(arq("a.yml", "x: 1\ny: 2"))
    assert len(P.conferir_traco(unico, [{"linha": 1, "acao": "x"}, {"linha": 2, "acao": "y", "saida": "ok"}])) == 2


# --- o gerador -------------------------------------------------------------------------

EU = {"id": "11111111-1111-1111-1111-111111111111", "email": "eu@exemplo.com"}


@pytest.fixture
def gerador(monkeypatch):
    estado = SimpleNamespace(respostas=[], pedidos=[])

    async def falso(sistema, pedido, schema, **_):
        estado.pedidos.append(pedido)
        return SimpleNamespace(content=estado.respostas.pop(0), model="falso")

    monkeypatch.setattr(walkthroughs, "generate_json", falso)
    monkeypatch.setattr(walkthroughs, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(walkthroughs, "list_mine", lambda *_: [{"slug": "java", "proficiency": 2, "is_target": True}])
    return estado


def _bom():
    return {
        "titulo": "Testes no GitHub Actions",
        "resumo": "O workflow roda os testes a cada push.",
        "cenario": "um push na main com um teste que passa",
        "linguagem": "yaml",
        "arquivos": [arq(".github/workflows/ci.yml", WORKFLOW), arq("src/test/java/com/exemplo/produto/CalculadoraTest.java", TESTE_JAVA)],
        "conceitos": ["CI", "JUnit"],
        "passos": [
            {"arquivo": ".github/workflows/ci.yml", "linha": 2, "acao": "o push dispara"},
            {"arquivo": "src/test/java/com/exemplo/produto/CalculadoraTest.java", "linha": 9, "acao": "o teste passa", "saida": "Tests run: 1"},
        ],
    }


def test_gerador_recusa_conteudo_inventado_e_manda_o_motivo(gerador):
    ruim = _bom()
    ruim["arquivos"][0] = arq(".github/workflows/ci.yml", WORKFLOW.replace("checkout@v4", "checkout@v2"))
    gerador.respostas = [ruim, _bom()]
    banco = FakeSupabase(pathr_walkthrough=[])

    linha = asyncio.run(walkthroughs.gerar_exemplo(banco, EU, "auto", "GitHub e testes automatizados"))

    assert "checkout@v2 está desatualizada" in gerador.pedidos[1]
    assert "Java" in gerador.pedidos[0]  # a linguagem do perfil vai junto
    assert linha["language"] == "yaml"
    assert [a["caminho"] for a in linha["files"]] == [".github/workflows/ci.yml", "src/test/java/com/exemplo/produto/CalculadoraTest.java"]
    assert "checkout@v4" in linha["code"]
    assert "Cenário: um push na main" in linha["summary"]
    api = walkthroughs._para_api(linha)
    assert api["files"][1]["linhas"][0] == "package com.exemplo.produto;"
    assert api["steps"][1]["arquivo"].endswith("CalculadoraTest.java")


def test_gerador_nao_grava_quando_todas_as_tentativas_sao_inventadas(gerador):
    ruim = _bom()
    ruim["arquivos"] = [arq(".github/workflows/ci.yml", "jobs: [")]
    gerador.respostas = [ruim, ruim, ruim]
    banco = FakeSupabase(pathr_walkthrough=[])
    with pytest.raises(HTTPException) as erro:
        asyncio.run(walkthroughs.gerar_exemplo(banco, EU, "yaml", "workflow"))
    assert erro.value.status_code == 502
    assert banco.linhas("pathr_walkthrough") == []


def test_exemplo_antigo_de_um_arquivo_continua_abrindo():
    antigo = {"id": "w1", "language": "python", "code": "x = 1\nprint(x)", "steps": [{"linha": 2, "acao": "imprime", "estado": [], "saida": "1"}]}
    api = walkthroughs._para_api(antigo)
    assert api["files"] == [{"caminho": "main.py", "linguagem": "python", "rotulo": "Python", "realce": "python", "linhas": ["x = 1", "print(x)"]}]
    assert api["steps"][0]["arquivo"] == "main.py"


def test_pedido_aceita_auto_e_yaml_mas_nao_invencao():
    walkthroughs._valida(walkthroughs.NovoWalkthrough(language="auto", topic="GitHub Actions"))
    walkthroughs._valida(walkthroughs.NovoWalkthrough(language="yaml", topic="compose"))
    with pytest.raises(HTTPException):
        walkthroughs._valida(walkthroughs.NovoWalkthrough(language="klingon", topic="xx"))
