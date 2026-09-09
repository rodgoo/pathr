"""Popula o catálogo global de tecnologias (`pathr_tag`).

Precisa rodar UMA vez antes do primeiro currículo. Sem ele o catálogo nasce
vazio, e aí cada tecnologia citada num CV vira uma tag criada na hora — sem
apelidos. Na prática isso significa que o primeiro currículo que escreve
"postgres" e o segundo que escreve "PostgreSQL" criam DUAS tags para o mesmo
assunto, e a curadoria de um não serve para o outro. É por isso que a semente
existe: ela chega com os apelidos que as pessoas realmente escrevem.

Idempotente: reexecutar não duplica nem sobrescreve o que foi editado à mão.
Uma tag já existente (mesmo slug) é deixada como está — inclusive a
popularidade, que pode ter sido ajustada depois.

    python -m scripts.seed_tags            # insere o que falta
    python -m scripts.seed_tags --dry-run  # só mostra o que faria
"""

import argparse
import sys

from app.database import get_supabase
from app.services.tag_seed import seed_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Popula pathr_tag com o catálogo base.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="lista o que seria inserido, sem escrever nada",
    )
    args = parser.parse_args()

    rows = seed_rows()
    supabase = get_supabase()

    existing = {
        row["slug"]
        for row in (supabase.table("pathr_tag").select("slug").execute().data or [])
    }
    missing = [row for row in rows if row["slug"] not in existing]

    print(f"catálogo: {len(rows)} tags na semente, {len(existing)} já no banco")

    if not missing:
        print("nada a fazer — o catálogo já está completo.")
        return 0

    print(f"faltando: {len(missing)}")
    for row in missing:
        print(f"  + {row['slug']:<24} {row['name']}  [{row['category']}]")

    if args.dry_run:
        print("\n--dry-run: nada foi escrito.")
        return 0

    # Em lotes: o PostgREST tem limite de tamanho de corpo, e 91 linhas com
    # apelidos passam folgado — mas o lote mantém isso verdadeiro se a semente
    # crescer.
    for start in range(0, len(missing), 50):
        supabase.table("pathr_tag").insert(missing[start : start + 50]).execute()

    print(f"\ninseridas {len(missing)} tags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
