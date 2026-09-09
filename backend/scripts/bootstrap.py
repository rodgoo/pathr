"""Prepara um projeto Supabase novo para o PathR, do zero ao pronto.

Roda os três passos que um projeto recém-criado precisa, na ordem, e verifica
o resultado de cada um:

    1. migrations   -> cria as 28 tabelas pathr_
    2. bucket       -> cria pathr-resumes, PRIVADO
    3. seed         -> insere as 91 tags do catálogo base

Idempotente: pode rodar de novo sem duplicar nada. É de propósito — a primeira
execução costuma parar no meio por uma credencial errada, e ter que desfazer
antes de tentar de novo seria o pior momento possível para isso.

    python -m scripts.bootstrap             # executa
    python -m scripts.bootstrap --check     # só diagnostica, não escreve

O que ele NÃO faz: criar o projeto Supabase. Isso é uma ação na sua conta e
sai do dashboard (supabase.com -> New project) ou do CLI depois de
`supabase login`. Depois de criado, preencha o .env.local e rode isto.
"""

import argparse
import subprocess
import sys
from pathlib import Path

BUCKET_PLACEHOLDER = "SEU-PROJETO"


class Step:
    """Um passo com nome, para o relatório final ficar legível."""

    def __init__(self, name: str):
        self.name = name
        self.ok = False
        self.detail = ""

    def done(self, detail: str = "") -> "Step":
        self.ok = True
        self.detail = detail
        return self

    def failed(self, detail: str) -> "Step":
        self.ok = False
        self.detail = detail
        return self


def check_settings() -> list[str]:
    """As credenciais estão preenchidas e apontam para um projeto de verdade?

    Falhar aqui, antes de qualquer escrita, evita o caso ruim: metade dos
    passos aplicados num banco errado.
    """
    from app.config import settings

    problems: list[str] = []
    if not settings.supabase_url or BUCKET_PLACEHOLDER in settings.supabase_url:
        problems.append("SUPABASE_URL não preenchida (ainda com o valor de exemplo)")
    if not settings.supabase_service_role_key:
        problems.append("SUPABASE_SERVICE_ROLE_KEY não preenchida")
    if not settings.database_url or BUCKET_PLACEHOLDER in settings.database_url:
        problems.append("DATABASE_URL não preenchida — o Alembic precisa dela")
    elif "pooler" not in settings.database_url:
        problems.append(
            "DATABASE_URL não parece ser a do pooler (aws-...pooler.supabase.com). "
            "O host direto db.<ref>.supabase.co resolve só em IPv6 e falha na maioria "
            "das hospedagens"
        )
    if not settings.jwt_secret_key:
        problems.append("JWT_SECRET_KEY vazia — o login não funciona sem ela")
    if not settings.mfa_encryption_key:
        problems.append("MFA_ENCRYPTION_KEY vazia — o MFA quebra no primeiro uso")
    return problems


def run_migrations(dry: bool) -> Step:
    """`alembic upgrade head` — cria as tabelas.

    Chamado como subprocesso, e não importando a API do Alembic, porque é o
    MESMO comando que o start.sh roda no boot em produção. Se funcionar aqui,
    funciona lá.
    """
    step = Step("migrations")
    if dry:
        return step.done("(--check: não executado)")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return step.failed(f"não consegui rodar o alembic ({exc.__class__.__name__})")

    if result.returncode != 0:
        # A última linha do stderr é onde o Alembic põe a causa; o resto é
        # ruído de stack trace.
        tail = (result.stderr or result.stdout).strip().splitlines()
        return step.failed(tail[-1] if tail else f"alembic saiu com {result.returncode}")
    return step.done("schema aplicado")


def check_tables(dry: bool = False) -> Step:
    """As tabelas estão visíveis pelo PostgREST?

    Não basta o Alembic ter rodado: o PostgREST mantém um cache de schema, e é
    por ele que o app fala com o banco. Esta é a mesma checagem que /health faz.
    """
    from app.health import _CORE_TABLES

    step = Step("tabelas visíveis")
    if dry:
        # As migrations não rodaram neste modo, então a ausência das tabelas é
        # o esperado — reportá-la como falha faria um diagnóstico correto
        # parecer um problema.
        return step.done("(--check: depende das migrations)")
    try:
        from app.database import get_supabase

        supabase = get_supabase()
        for table in _CORE_TABLES:
            supabase.table(table).select("*").limit(0).execute()
    except Exception as exc:  # noqa: BLE001
        return step.failed(f"{exc.__class__.__name__} — o PostgREST ainda não vê o schema")
    return step.done(f"{len(_CORE_TABLES)} tabelas centrais respondem")


def ensure_bucket(dry: bool) -> Step:
    """Cria o bucket dos currículos, PRIVADO.

    Privado não é detalhe: o currículo tem nome, telefone e histórico
    profissional de alguém. Um bucket público deixaria qualquer pessoa com a
    URL baixar o arquivo — e a URL é previsível (user_id/hash.pdf).
    """
    from app.config import settings

    step = Step(f"bucket {settings.resume_bucket}")
    try:
        from app.database import get_supabase

        storage = get_supabase().storage
        # Compara pelo `id`, que é como o storage.from_() endereça o bucket.
        # O `name` costuma ser igual, mas é o id que a aplicação usa.
        existing = {bucket.id for bucket in storage.list_buckets()}
        if settings.resume_bucket in existing:
            return step.done("já existe")
        if dry:
            return step.done("(--check: seria criado)")
        storage.create_bucket(settings.resume_bucket, options={"public": False})
    except Exception as exc:  # noqa: BLE001
        return step.failed(f"{exc.__class__.__name__}: {exc}")
    return step.done("criado como privado")


def _tables_exist() -> bool:
    """As tabelas já estão lá? Só para o dry-run saber se pode inspecionar."""
    try:
        from app.database import get_supabase

        get_supabase().table("pathr_tag").select("*").limit(0).execute()
    except Exception:  # noqa: BLE001
        return False
    return True


def seed_catalog(dry: bool) -> Step:
    """As 91 tags base. Sem elas, cada currículo cria tags do zero e sem
    apelidos — "postgres" e "PostgreSQL" viram dois assuntos diferentes."""
    from app.services.tag_seed import seed_rows

    step = Step("catálogo de tags")
    if dry and not _tables_exist():
        return step.done("(--check: depende das migrations)")
    try:
        from app.database import get_supabase

        supabase = get_supabase()
        rows = seed_rows()
        existing = {
            row["slug"]
            for row in (supabase.table("pathr_tag").select("slug").execute().data or [])
        }
        missing = [row for row in rows if row["slug"] not in existing]
        if not missing:
            return step.done(f"{len(existing)} tags já no banco")
        if dry:
            return step.done(f"(--check: {len(missing)} seriam inseridas)")
        for start in range(0, len(missing), 50):
            supabase.table("pathr_tag").insert(missing[start : start + 50]).execute()
    except Exception as exc:  # noqa: BLE001
        return step.failed(f"{exc.__class__.__name__}: {exc}")
    return step.done(f"{len(missing)} tags inseridas")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepara um projeto Supabase novo para o PathR.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="diagnostica sem escrever nada",
    )
    args = parser.parse_args()

    print("PathR — preparo do projeto Supabase\n")

    problems = check_settings()
    if problems:
        print("Faltam credenciais no .env.local:\n")
        for problem in problems:
            print(f"  - {problem}")
        print("\nVeja .env.example. Nada foi executado.")
        return 1

    print(f"modo:    {'diagnóstico (--check)' if args.check else 'aplicando'}\n")

    steps = [
        run_migrations(args.check),
        check_tables(args.check),
        ensure_bucket(args.check),
        seed_catalog(args.check),
    ]

    print()
    for step in steps:
        mark = "ok  " if step.ok else "FALHA"
        print(f"  {mark} {step.name}: {step.detail}")

    failed = [step for step in steps if not step.ok]
    if failed:
        print(f"\n{len(failed)} passo(s) falharam. Corrija e rode de novo — o script é idempotente.")
        return 1

    if args.check:
        print("\nDiagnóstico concluído. Rode sem --check para aplicar.")
        return 0

    print("\nPronto. O backend pode subir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
