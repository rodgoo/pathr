"""Os defaults precisam existir NO BANCO, não só no Python.

Este arquivo existe por causa de um bug real: o modelo declarava
`default_factory=uuid.uuid4` para toda chave primária, os testes de modelo
passavam, e o primeiro INSERT de verdade falhou com

    null value in column "id" of relation "pathr_tag" violates not-null

A causa está no cabeçalho de app/models.py: em runtime o app fala com o
Postgres via PostgREST, não por sessão SQLAlchemy — e um default do Python só
é aplicado quando o SQLAlchemy monta o INSERT. Pelo PostgREST a coluna nem é
enviada.

O conserto (`_mirror_defaults_to_database`) copia todo default do Python para
o banco. Estes testes garantem que a cópia continua acontecendo, para nenhuma
coluna futura repetir o erro.
"""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

from app import models  # noqa: F401 — popula e corrige o metadata

PREFIX = "pathr_"


def _pathr_columns():
    for table in SQLModel.metadata.tables.values():
        if not table.name.startswith(PREFIX):
            continue
        for column in table.columns:
            yield table.name, column


def test_todo_default_do_python_tem_espelho_no_banco():
    """A invariante central. Se este teste falhar, algum INSERT vai quebrar em
    produção com "violates not-null constraint"."""
    orfaos = [
        f"{table}.{column.name}"
        for table, column in _pathr_columns()
        if column.default is not None and column.server_default is None
    ]
    assert orfaos == []


def test_chaves_primarias_proprias_geram_uuid_no_banco():
    """Só as que o app gera.

    Em pathr_profile, pathr_streak e pathr_english_profile a chave primária É
    a FK do usuário — uma linha por conta. Ali o id vem do chamador, e um
    `gen_random_uuid()` criaria uma linha órfã, apontando para usuário nenhum.
    O critério certo é o default do modelo, não "é chave primária".
    """
    alvos = [
        (table, column)
        for table, column in _pathr_columns()
        if column.primary_key and column.default is not None
    ]
    assert len(alvos) >= 20, "esperava chaves primárias geradas pelo app"
    for table, column in alvos:
        assert "gen_random_uuid()" in str(column.server_default.arg), table


def test_chave_que_e_fk_do_usuario_nao_ganha_uuid_aleatorio():
    """A outra metade da regra acima, dita explicitamente."""
    for table_name in ("pathr_profile", "pathr_streak", "pathr_english_profile"):
        column = SQLModel.metadata.tables[table_name].columns["user_id"]
        assert column.primary_key
        assert column.server_default is None, table_name


def test_timestamps_recebem_now_e_nao_current_date():
    """datetime é subclasse de date: a ordem errada no despacho daria
    `current_date` a uma coluna de timestamp, truncando a hora em silêncio."""
    for table, column in _pathr_columns():
        if column.default is None or not column.default.is_callable:
            continue
        if column.type.python_type is datetime:
            assert "now()" in str(column.server_default.arg), f"{table}.{column.name}"
        elif column.type.python_type is date:
            assert "current_date" in str(column.server_default.arg), f"{table}.{column.name}"


def test_campos_obrigatorios_continuam_sem_default():
    """Inventar um default para `email` ou `slug` esconderia um dado que o
    chamador esqueceu de mandar — a coluna deve recusar o INSERT."""
    obrigatorios = {
        ("pathr_user", "email"),
        ("pathr_user", "password_hash"),
        ("pathr_tag", "slug"),
        ("pathr_tag", "name"),
    }
    for table, column in _pathr_columns():
        if (table, column.name) in obrigatorios:
            assert column.server_default is None, f"{table}.{column.name}"
            assert not column.nullable


@pytest.mark.parametrize(
    "table_name,column_name,esperado",
    [
        ("pathr_user", "mfa_enabled", "false"),
        ("pathr_user", "failed_attempts", "0"),
        ("pathr_user", "locale", "'pt-BR'"),
        ("pathr_english_vocab", "ease", "2.5"),
    ],
)
def test_escalares_viram_literal_sql_do_tipo_certo(table_name, column_name, esperado):
    """Booleano vira `false`, não `False`; string vira aspas simples."""
    column = SQLModel.metadata.tables[table_name].columns[column_name]
    assert str(column.server_default.arg) == esperado


def test_default_de_jsonb_sai_com_aspas_e_funcao_sem():
    """A distinção que quebrou a primeira versão da migration 0002: `{}` num
    JSONB precisa de aspas, `gen_random_uuid()` não pode ter."""
    dialect = postgresql.dialect()
    compiler = dialect.ddl_compiler(dialect, None)

    tag = SQLModel.metadata.tables["pathr_tag"]
    assert compiler.get_column_default_string(tag.columns["aliases"]) == "'[]'"
    assert compiler.get_column_default_string(tag.columns["id"]) == "gen_random_uuid()"
    assert compiler.get_column_default_string(tag.columns["slug"]) is None
