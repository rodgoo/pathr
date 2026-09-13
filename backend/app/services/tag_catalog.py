"""O catálogo global de tecnologias, e como um nome vira uma tag.

`pathr_tag` é global e compartilhado: se cada usuário criasse as próprias
tags, "React" e "ReactJS" seriam assuntos diferentes, a biblioteca curada
para um não serviria para o outro e o roadmap não teria como saber que dois
currículos citam a mesma coisa.

O casamento acontece em três passos, do mais barato ao mais caro:

1. **Slug exato.** "PostgreSQL" -> `postgresql`. Resolve a maioria.
2. **Alias.** Cada tag carrega uma lista de apelidos (`postgres`, `psql`,
   `pg`), e é aí que mora a variação real dos currículos.
3. **Criação.** O que sobrou vira tag nova, com `popularity=0`. O catálogo
   cresce com o uso em vez de precisar prever tudo — mas só por este
   caminho, para que uma tag nova sempre tenha vindo de um currículo real.

A normalização é agressiva de propósito (minúsculas, sem acento, sem
pontuação) porque a entrada é texto livre de um documento de terceiro.
"""

import re
import unicodedata
from typing import Any, Iterable, Optional

from supabase import Client

# Categorias aceitas em `pathr_tag.category`. Fora desta lista vira
# "ferramenta", que é o balde honesto para o que não se encaixa.
CATEGORIES = {
    "linguagem", "framework", "banco", "cloud", "devops", "dados", "ia",
    "arquitetura", "testes", "seguranca", "mobile", "frontend", "backend",
    "ferramenta", "metodologia", "soft-skill", "idioma",
    # Setor de negócio ("bancário", "varejo"): a vaga cobra, e sem categoria
    # própria virava ferramenta.
    "dominio",
}

# Cor default por categoria — o app pinta a tag por família quando a tag não
# tem cor própria. Mesma paleta de apoio do frontend (src/lib/tokens.ts).
CATEGORY_COLORS = {
    "linguagem": "#cfa25e",
    "framework": "#9184d9",
    "banco": "#6aa6de",
    "cloud": "#5cb0b0",
    "devops": "#5cb0b0",
    "dados": "#6aa6de",
    "ia": "#d189ab",
    "arquitetura": "#6aa6de",
    "testes": "#63b48f",
    "seguranca": "#d189ab",
    "mobile": "#9184d9",
    "frontend": "#9184d9",
    "backend": "#cfa25e",
    "ferramenta": "#9397ab",
    "metodologia": "#9397ab",
    "soft-skill": "#9397ab",
    "idioma": "#d189ab",
    "dominio": "#63b48f",
}


def slugify(name: str) -> str:
    """"Node.js" -> "node-js", "C#" -> "c-sharp", "C++" -> "c-plus-plus".

    `#` e `+` viram palavra em vez de sumirem: sem isso "C#" e "C" colidiriam
    no mesmo slug, e o catálogo passaria a tratar duas linguagens como uma.
    """
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = text.replace("#", "-sharp").replace("++", "-plus-plus")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def normalize_category(raw: Optional[str]) -> str:
    value = (raw or "").strip().lower()
    # O catálogo agrupa framework pelo lado em que ele roda (Spring Boot em
    # backend, React em frontend). Uma tag nova "framework" abria um grupo com
    # um item só na tela de competências; backend é o lado mais comum no que os
    # currículos chamam de framework.
    if value == "framework":
        return "backend"
    return value if value in CATEGORIES else "ferramenta"


def _alias_keys(tag: dict[str, Any]) -> Iterable[str]:
    """Todo jeito conhecido de escrever esta tag, já normalizado."""
    yield tag["slug"]
    yield slugify(tag.get("name") or "")
    for alias in tag.get("aliases") or []:
        if isinstance(alias, str) and alias.strip():
            yield slugify(alias)


class TagCatalog:
    """Índice em memória do catálogo, carregado uma vez por requisição.

    Uma leitura só em vez de uma consulta por tecnologia: um currículo cita
    de 15 a 40 tecnologias, e 40 idas ao PostgREST numa rota que já espera
    por uma chamada de IA é latência que dá para não pagar.
    """

    def __init__(self, supabase: Client):
        self._supabase = supabase
        self._by_key: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> "TagCatalog":
        rows = (
            self._supabase.table("pathr_tag")
            .select("id,slug,name,category,aliases,color,popularity")
            .execute()
            .data
            or []
        )
        for tag in rows:
            for key in _alias_keys(tag):
                # Primeiro a registrar vence: o slug canônico entra antes dos
                # apelidos, então um apelido nunca sequestra outra tag.
                self._by_key.setdefault(key, tag)
        self._loaded = True
        return self

    def find(self, name: str) -> Optional[dict[str, Any]]:
        if not self._loaded:
            self.load()
        return self._by_key.get(slugify(name))

    def create(self, name: str, category: str) -> dict[str, Any]:
        """Cria a tag que faltava. `popularity=0` a joga para o fim do
        autocomplete até que o uso a promova."""
        slug = slugify(name)
        category = normalize_category(category)
        payload = {
            "slug": slug,
            "name": name.strip()[:80],
            "category": category,
            "color": CATEGORY_COLORS.get(category),
            "aliases": [],
            "popularity": 0,
        }
        try:
            created = self._supabase.table("pathr_tag").insert(payload).execute().data[0]
        except Exception:
            # Corrida entre dois usuários enviando currículos que citam a mesma
            # tecnologia nova: o slug é UNIQUE, então o segundo insert falha e
            # o certo é ficar com o que já está lá.
            existing = (
                self._supabase.table("pathr_tag").select("*").eq("slug", slug).limit(1).execute().data
            )
            if not existing:
                raise
            created = existing[0]
        for key in _alias_keys(created):
            self._by_key.setdefault(key, created)
        return created

    def resolve(self, name: str, category: str = "") -> dict[str, Any]:
        """A tag para este nome, criando-a se ainda não existir."""
        return self.find(name) or self.create(name, category)
