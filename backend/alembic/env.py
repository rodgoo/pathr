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
from sqlalchemy.engine.url import make_url
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
    """A URL do banco, validada com uma mensagem que diz o que fazer.

    Sem isto, um valor malformado sobe como
    `ArgumentError: Could not parse SQLAlchemy URL from given URL string` —
    trinta linhas de traceback que não dizem qual é o defeito nem em qual
    variável. Num log de deploy, onde não dá para inspecionar o valor, isso é
    a diferença entre corrigir em um minuto e ficar chutando.

    Nenhuma mensagem daqui inclui a URL: ela carrega a senha do banco, e log
    de deploy costuma ser retido e compartilhado.
    """
    url = settings.database_url

    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Copie a connection string do "
            "Supabase (Settings -> Database) usando o POOLER "
            "(aws-...pooler.supabase.com): o host direto db.<ref>.supabase.co "
            "resolve só em IPv6 e a maioria das hospedagens não alcança."
        )

    if url != url.strip():
        raise RuntimeError(
            "DATABASE_URL tem espaço ou quebra de linha nas pontas. "
            "Recole o valor sem espaços em volta."
        )

    # A função roda num namespace isolado nos testes (o mesmo texto que roda
    # no deploy), então nada de imports aqui — só operações de string.
    nome, igual, _resto = url.partition("=")
    if igual and nome and nome == nome.upper() and nome.replace("_", "").isalnum():
        # Aconteceu de verdade num deploy: a linha inteira do .env.local foi
        # colada no campo de VALOR do painel, virando
        # "DATABASE_URL=postgresql://...". O painel guarda o texto literal, e
        # o resultado é uma URL cujo esquema é "DATABASE_URL=postgresql".
        #
        # Vale conferir as OUTRAS variáveis também: quem colou assim uma vez
        # provavelmente repetiu, e as demais não têm validação própria — elas
        # simplesmente não funcionam, sem erro no boot.
        raise RuntimeError(
            f"DATABASE_URL contém o nome da variável no valor "
            f"(começa com '{nome}='). No painel, o nome vai no "
            "campo Key e só a URL no campo Value. Confira as outras variáveis: "
            "se esta foi colada assim, as demais provavelmente também."
        )

    if url.startswith("psql "):
        # O painel do Supabase oferece um botão de cópia "psql", que entrega o
        # COMANDO inteiro: psql 'postgresql://...'. É a causa mais provável de
        # "Could not parse SQLAlchemy URL", porque a string parece certa a olho
        # nu — o prefixo e as aspas passam despercebidos.
        raise RuntimeError(
            "DATABASE_URL contém o comando psql, não só a URL. Use o botão de "
            "cópia URI (ou apague o prefixo 'psql ' e as aspas em volta)."
        )

    if url[0] in "\"'" or url[-1] in "\"'":
        raise RuntimeError(
            "DATABASE_URL está entre aspas. Painéis de variáveis de ambiente "
            "guardam o valor literal — tire as aspas."
        )

    if "[" in url or "]" in url:
        raise RuntimeError(
            "DATABASE_URL ainda tem o marcador de senha entre colchetes. "
            "Substitua [YOUR-PASSWORD] pela senha real do banco "
            "(Supabase -> Settings -> Database) e remova os colchetes."
        )

    if not url.startswith(("postgresql+", "postgresql://", "postgres://")):
        esquema = url.split("://")[0] if "://" in url else "(sem esquema)"
        raise RuntimeError(
            f"DATABASE_URL não parece uma URL de Postgres (esquema: {esquema}). "
            "Ela é a connection string do banco, não a URL da API do Supabase "
            "— esta última vai em SUPABASE_URL."
        )

    try:
        make_url(url)
    except Exception as exc:  # noqa: BLE001 — a mensagem é o produto aqui
        raise RuntimeError(
            "DATABASE_URL não pôde ser interpretada "
            f"({exc.__class__.__name__}). Confira o host e a porta: a porta "
            "precisa ser um número (5432 no pooler de sessão, 6543 no de "
            "transação). Copie novamente do Supabase pelo botão URI."
        ) from exc

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
