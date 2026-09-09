"""Ambiente do Alembic.

Duas coisas específicas deste projeto:

1. **A URL vem do ambiente**, nunca do alembic.ini — assim nenhuma senha de
   banco entra no repositório.
2. **Só as tabelas `pathr_` são consideradas.** O PathR tem projeto Supabase
   próprio, então em condições normais o filtro não muda nada. Ele existe como
   rede de proteção: um `DATABASE_URL` apontado por engano para outro banco
   faria o `--autogenerate` propor migrations que APAGAM tudo que ele não
   reconhece. Com o filtro, o pior caso é uma migration vazia.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.config import settings
from app import models  # noqa: F401 — o import é o que popula SQLModel.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

PREFIX = "pathr_"


def include_object(object_, name, type_, reflected, compare_to):
    """Ignora tudo que não seja do PathR."""
    if type_ == "table":
        return bool(name and name.startswith(PREFIX))
    # Índices e constraints são avaliados pela tabela dona.
    if type_ in ("index", "unique_constraint", "foreign_key_constraint"):
        table = getattr(object_, "table", None)
        return bool(table is not None and table.name.startswith(PREFIX))
    return True


def _url() -> str:
    url = settings.database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Use a string do pooler do Supabase "
            "(aws-...pooler.supabase.com) — o host direto resolve só em IPv6."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
