"""Tira do catálogo o material que não trata do assunto da tag em que está.

Corrigir a busca (`resource_search.fala_do_assunto`) protege as curadorias FUTURAS. O que já foi gravado antes
dela — guias de criptomoedas em "Docker" — continua no catálogo global, aparecendo para todo mundo que estuda
aquele assunto. Este script limpa esse passivo.

Ele é conservador de propósito, porque `pathr_user_resource.resource_id` é `ON DELETE CASCADE`: apagar um recurso
leva junto o "concluído", as notas e o progresso de quem já interagiu com ele. Então, para cada recurso:

1. DESANEXA das tags em que ele não trata do assunto (tira o id da tag de `tag_ids`). Só isso já o tira da tela
   daquele módulo, e não destrói nada de ninguém.
2. APAGA a linha só se, depois de desanexar, ela ficou sem nenhuma tag E ninguém interagiu com ela. Recurso que
   alguém marcou fica no catálogo, sem tag — invisível nos módulos, com o progresso da pessoa intacto.

Vídeo fica de fora: o YouTube ordena por relevância e o título raramente repete o assunto por extenso.

    python -m scripts.limpar_material_fora_do_tema            # SÓ MOSTRA o que faria (o padrão)
    python -m scripts.limpar_material_fora_do_tema --apply    # faz

ATENÇÃO: `get_supabase()` usa o `.env.local`, e no desenvolvimento ele aponta para o banco REAL. O padrão é a
simulação por isso: leia a lista, confira se cada item é mesmo lixo, e só então rode com `--apply`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.resource_search import fala_do_assunto

# O que a busca web grava e que pode ter vindo fora do assunto. Vídeo não entra (ver o cabeçalho).
TIPOS_JULGADOS = frozenset({"article", "doc", "exercise", "repo", "course", "book", "podcast"})


@dataclass
class Acao:
    resource_id: str
    titulo: str
    url: str
    tags_removidas: list[str] = field(default_factory=list)  # nomes, para a pessoa ler
    tag_ids_finais: list[str] = field(default_factory=list)
    apagar: bool = False


def planejar(
    recursos: Iterable[dict[str, Any]],
    nomes_das_tags: dict[str, str],
    com_interacao: set[str],
) -> list[Acao]:
    """O que fazer com cada recurso. Pura: não fala com o banco, e é o que os testes exercitam.

    `nomes_das_tags`: id da tag -> nome. `com_interacao`: ids de recursos que alguém marcou/avaliou/anotou.
    Só devolve recursos que MUDAM; o que está certo não aparece.
    """
    acoes: list[Acao] = []
    for recurso in recursos:
        if recurso.get("kind") not in TIPOS_JULGADOS:
            continue
        tag_ids = [str(t) for t in (recurso.get("tag_ids") or [])]
        removidas = [
            t
            for t in tag_ids
            if t in nomes_das_tags
            and not fala_do_assunto(nomes_das_tags[t], recurso.get("title"), recurso.get("description"), recurso.get("url"))
        ]
        if not removidas:
            continue
        finais = [t for t in tag_ids if t not in removidas]
        rid = str(recurso["id"])
        acoes.append(
            Acao(
                resource_id=rid,
                titulo=str(recurso.get("title") or ""),
                url=str(recurso.get("url") or ""),
                tags_removidas=[nomes_das_tags[t] for t in removidas],
                tag_ids_finais=finais,
                apagar=not finais and rid not in com_interacao,
            )
        )
    return acoes


def _todos(supabase, tabela: str, colunas: str, tamanho: int = 1000) -> list[dict[str, Any]]:
    """Todas as linhas, em páginas: o PostgREST devolve no máximo ~1000 por consulta."""
    linhas: list[dict[str, Any]] = []
    inicio = 0
    while True:
        pagina = supabase.table(tabela).select(colunas).range(inicio, inicio + tamanho - 1).execute().data or []
        linhas.extend(pagina)
        if len(pagina) < tamanho:
            return linhas
        inicio += tamanho


def main() -> int:
    parser = argparse.ArgumentParser(description="Tira do catálogo o material que não trata do assunto da tag.")
    parser.add_argument("--apply", action="store_true", help="aplica; sem isto só mostra o que faria")
    args = parser.parse_args()

    from app.database import get_supabase

    supabase = get_supabase()
    recursos = _todos(supabase, "pathr_resource", "id,kind,title,url,description,tag_ids")
    nomes = {str(t["id"]): str(t.get("name") or t.get("slug") or "") for t in _todos(supabase, "pathr_tag", "id,name,slug")}
    com_interacao = {str(r["resource_id"]) for r in _todos(supabase, "pathr_user_resource", "resource_id")}

    acoes = planejar(recursos, nomes, com_interacao)
    print(f"{len(recursos)} recursos no catálogo; {len(acoes)} com material fora do assunto.\n")
    for acao in acoes:
        verbo = "APAGAR " if acao.apagar else "desanexar"
        print(f"[{verbo}] {acao.titulo[:80]}\n    {acao.url}\n    fora de: {', '.join(acao.tags_removidas)}")
    if not acoes:
        return 0
    if not args.apply:
        print("\nSimulação: nada foi alterado. Rode com --apply para aplicar.")
        return 0

    for acao in acoes:
        if acao.apagar:
            supabase.table("pathr_resource").delete().eq("id", acao.resource_id).execute()
        else:
            supabase.table("pathr_resource").update({"tag_ids": acao.tag_ids_finais}).eq("id", acao.resource_id).execute()
    print(f"\nAplicado: {sum(a.apagar for a in acoes)} apagados, {sum(not a.apagar for a in acoes)} desanexados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
