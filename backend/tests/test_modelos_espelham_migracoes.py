"""models.py precisa declarar o que as migrations criaram.

`alembic revision --autogenerate` compara SQLModel.metadata com o banco: tabela
ou constraint que existe na migration e não existe aqui vira DROP na próxima
migração gerada. Este teste lê o TEXTO das migrations (sem banco) e confere os
nomes contra o metadata.
"""

import re
from pathlib import Path

from sqlmodel import SQLModel

from app import models  # noqa: F401 — popula o metadata

VERSOES = Path(__file__).resolve().parents[1] / "alembic" / "versions"

TABELAS_ESPERADAS = {
    "pathr_answer_bank",
    "pathr_extension_token",
    "pathr_news_event",
    "pathr_news_attendance",
    "pathr_news_scan",
}


def _nomes_no_metadata() -> set[str]:
    nomes: set[str] = set()
    for tabela in SQLModel.metadata.tables.values():
        nomes |= {c.name for c in tabela.constraints if c.name}
        nomes |= {i.name for i in tabela.indexes if i.name}
    return nomes


def _upgrade(texto: str) -> str:
    return texto.split("def downgrade", 1)[0]


def _migrations() -> dict[str, str]:
    return {p.name: _upgrade(p.read_text(encoding="utf-8")) for p in sorted(VERSOES.glob("*.py"))}


def test_as_cinco_tabelas_estao_no_metadata():
    assert TABELAS_ESPERADAS <= set(SQLModel.metadata.tables)


def test_toda_tabela_criada_nas_migrations_0039_a_0042_esta_no_metadata():
    criadas = set()
    for nome, texto in _migrations().items():
        if nome[:4] in {"0039", "0040", "0041", "0042"}:
            criadas |= set(re.findall(r'create_table\(\s*"(pathr_\w+)"', texto))
    assert criadas == TABELAS_ESPERADAS
    assert criadas <= set(SQLModel.metadata.tables)


def test_toda_unicidade_e_indice_nomeado_das_migrations_esta_no_metadata():
    """Só os `uq_pathr_*` (unicidades) e os índices das tabelas novas: o resto do
    histórico de índices tem outros nomes gerados e fica fora deste teste."""
    esperados: set[str] = set()
    for texto in _migrations().values():
        esperados |= set(re.findall(r'create_unique_constraint\(\s*"(uq_pathr_\w+)"', texto))
        esperados |= set(re.findall(r'create_index\(\s*"(uq_pathr_\w+)"', texto))
        esperados |= set(re.findall(r'create_index\(\s*"(ix_pathr_(?:news|extension)\w*)"', texto))

    faltando = esperados - _nomes_no_metadata()
    assert not faltando, f"nas migrations e ausentes de models.py: {sorted(faltando)}"
    # As nove que a revisão apontou, explicitamente.
    assert {
        "uq_pathr_activity_draft_user_node",
        "uq_pathr_answer_bank_pergunta",
        "uq_pathr_english_item_session_order",
        "uq_pathr_english_session_practice_day",
        "uq_pathr_friendship_pair",
        "uq_pathr_news_event_source_url",
        "uq_pathr_news_attendance_pessoa_evento",
        "uq_pathr_news_scan_regiao",
        "uq_pathr_user_username_lower",
    } <= esperados


def test_colunas_das_tabelas_novas_batem_com_as_migrations():
    esperadas = {
        "pathr_news_event": {
            "id", "title", "summary", "venue", "city", "state", "event_start", "event_end", "is_free",
            "price_info", "registration_start", "registration_end", "ticket_url", "source", "source_url",
            "created_at", "updated_at", "image_url",
        },
        "pathr_news_attendance": {"id", "user_id", "event_id", "created_at"},
        "pathr_news_scan": {"id", "city", "state", "scanned_at", "found"},
        "pathr_answer_bank": {
            "id", "user_id", "question_key", "question", "answer", "source", "used_count",
            "created_at", "updated_at",
        },
        "pathr_extension_token": {
            "id", "user_id", "token_hash", "name", "created_at", "last_used_at", "revoked_at",
        },
    }
    for tabela, colunas in esperadas.items():
        assert {c.name for c in SQLModel.metadata.tables[tabela].columns} == colunas, tabela
