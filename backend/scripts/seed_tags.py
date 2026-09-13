"""Popula o catálogo global de tecnologias (`pathr_tag`).

Precisa rodar UMA vez antes do primeiro currículo. Sem ele o catálogo nasce
vazio, e aí cada tecnologia citada num CV vira uma tag criada na hora — sem
apelidos. Na prática isso significa que o primeiro currículo que escreve
"postgres" e o segundo que escreve "PostgreSQL" criam DUAS tags para o mesmo
assunto, e a curadoria de um não serve para o outro. É por isso que a semente
existe: ela chega com os apelidos que as pessoas realmente escrevem.

Idempotente: reexecutar não duplica. Sem `--sincronizar`, uma tag já existente
(mesmo slug) é deixada como está — inclusive a popularidade, que pode ter sido
ajustada depois.

`--sincronizar` também corrige as tags que já existem: apelidos, categoria e
cor passam a ser os da semente. Foi preciso quando os apelidos deixaram de
fundir tecnologias diferentes (`tdd` em "Testes automatizados", `kanban` em
"Scrum"): sem reescrever a linha no banco, a tag nova "TDD" existiria mas o
casamento continuaria mandando "tdd" para a antiga. A popularidade não é
tocada.

    python -m scripts.seed_tags                          # insere o que falta
    python -m scripts.seed_tags --sincronizar            # e corrige as existentes
    python -m scripts.seed_tags --sincronizar --dry-run  # só mostra o que faria
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
        help="lista o que seria feito, sem escrever nada",
    )
    parser.add_argument(
        "--sincronizar",
        action="store_true",
        help="também corrige apelidos, categoria e cor das tags existentes",
    )
    args = parser.parse_args()

    rows = seed_rows()
    supabase = get_supabase()

    atuais = {
        row["slug"]: row
        for row in (
            supabase.table("pathr_tag").select("id,slug,aliases,category,color").execute().data or []
        )
    }
    existing = set(atuais)
    missing = [row for row in rows if row["slug"] not in existing]

    print(f"catálogo: {len(rows)} tags na semente, {len(existing)} já no banco")

    if args.sincronizar:
        mudar = []
        for row in rows:
            atual = atuais.get(row["slug"])
            if not atual:
                continue
            novo = {"aliases": row["aliases"], "category": row["category"], "color": row["color"]}
            if (sorted(atual.get("aliases") or []), atual.get("category"), atual.get("color")) != (
                sorted(novo["aliases"]), novo["category"], novo["color"]
            ):
                mudar.append((atual, novo))
        print(f"a corrigir: {len(mudar)}")
        for atual, novo in mudar:
            print(f"  ~ {atual['slug']:<24} apelidos {sorted(atual.get('aliases') or [])} -> {sorted(novo['aliases'])}")
        if mudar and not args.dry_run:
            for atual, novo in mudar:
                supabase.table("pathr_tag").update(novo).eq("id", atual["id"]).execute()
            print(f"corrigidas {len(mudar)} tags.")

    if not missing:
        print("nada a inserir — todas as tags da semente já estão no banco.")
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
