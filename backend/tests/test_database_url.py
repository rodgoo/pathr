"""A validação da DATABASE_URL usada pelo Alembic.

Escrito depois de um deploy falhar no Render com

    ArgumentError: Could not parse SQLAlchemy URL from given URL string

seguido de trinta linhas de traceback que não diziam qual variável estava
errada nem por quê. Num log de deploy, onde ninguém pode inspecionar o valor,
a mensagem é o único diagnóstico disponível — então ela é o produto, e merece
teste.

Nenhuma mensagem pode conter a URL: ela carrega a senha do banco.
"""

import pytest

from app.config import settings

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "alembic_env_url", pathlib.Path(__file__).resolve().parent.parent / "alembic" / "env.py"
)


@pytest.fixture
def url_check(monkeypatch):
    """Importa só a função `_url` do env.py do Alembic.

    Carregar o módulo inteiro dispararia as migrations, então a função é
    reconstruída a partir do código-fonte — o mesmo texto que roda no deploy.
    """
    fonte = (pathlib.Path(__file__).resolve().parent.parent / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )
    inicio = fonte.index("def _url()")
    fim = fonte.index("def run_migrations_offline")
    espaco: dict = {}
    exec(  # noqa: S102 — é o próprio arquivo do projeto, não entrada externa
        "from sqlalchemy.engine.url import make_url\nfrom app.config import settings\n"
        + fonte[inicio:fim],
        espaco,
    )

    def check(valor: str) -> str:
        monkeypatch.setattr(settings, "database_url", valor)
        return espaco["_url"]()

    return check


VALIDA = "postgresql+psycopg://postgres.abc:s3nh4@aws-0.pooler.supabase.com:5432/postgres"


def test_aceita_uma_url_valida(url_check):
    assert url_check(VALIDA) == VALIDA


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("", "não configurada"),
        (f"  {VALIDA}  ", "espaço ou quebra de linha"),
        (f'"{VALIDA}"', "entre aspas"),
        (
            "postgresql+psycopg://postgres.abc:[YOUR-PASSWORD]@aws-0.pooler.supabase.com:5432/postgres",
            "colchetes",
        ),
        ("https://abcdefgh.supabase.co", "SUPABASE_URL"),
    ],
)
def test_cada_defeito_tem_mensagem_propria(url_check, valor, esperado):
    with pytest.raises(RuntimeError) as erro:
        url_check(valor)
    assert esperado in str(erro.value)


def test_aceita_senha_com_caractere_especial(url_check):
    """@ , / e espaço na senha parseiam normalmente — o SQLAlchemy divide no
    ÚLTIMO @. Recusar isso seria um falso positivo sobre uma URL que funciona."""
    valor = "postgresql+psycopg://user:se@nh/a@host:5432/db"
    assert url_check(valor) == valor


def test_acusa_o_comando_psql_copiado_do_painel(url_check):
    """O botão "psql" do Supabase copia o comando inteiro. A string parece
    certa a olho nu e é a causa mais provável do erro de parsing."""
    with pytest.raises(RuntimeError) as erro:
        url_check("psql 'postgresql://u:p@aws-0.pooler.supabase.com:5432/postgres'")
    assert "psql" in str(erro.value)


def test_acusa_porta_nao_numerica(url_check):
    with pytest.raises(RuntimeError) as erro:
        url_check("postgresql+psycopg://u:p@host:PORTA/db")
    assert "porta" in str(erro.value)


def test_nenhuma_mensagem_vaza_a_url(url_check):
    """A senha não pode aparecer no log de deploy."""
    for valor in (f'"{VALIDA}"', f"  {VALIDA}  ", "postgresql+psycopg://u:s3nh4@host:PORTA/db"):
        with pytest.raises(RuntimeError) as erro:
            url_check(valor)
        assert "s3nh4" not in str(erro.value)
