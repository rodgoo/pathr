"""A Sympla parou de publicar `schema.org/Event` em JSON-LD nas páginas de evento.

O relato de produção: a aba de Notícias nunca mostrava nenhum evento. A busca
achava dezenas de candidatos reais (confirmado em produção: 55 para
Vitória/ES, a maioria da Sympla), mas TODOS eram descartados por falta de
data — `extrair()` só sabia ler JSON-LD, e a página da Sympla hoje não tem
nenhum. A data continua na página, só que em `<script id="__NEXT_DATA__">`,
o payload de hidratação do Next.js (confirmado baixando uma página real da
Sympla em produção).
"""

import json

from app.services.evento_da_pagina import extrair


def _pagina_sympla(evento: dict, com_json_ld: bool = False) -> str:
    """Um HTML mínimo com a MESMA estrutura que a página real da Sympla usa
    para o `__NEXT_DATA__` — só os campos que `extrair` lê, não a página toda."""
    next_data = {
        "props": {
            "pageProps": {
                "hydrationData": {
                    "eventHydration": {
                        "event": evento,
                    }
                }
            }
        }
    }
    json_ld = (
        f'<script type="application/ld+json">{json.dumps({"@type": "Event", **evento})}</script>'
        if com_json_ld
        else ""
    )
    return (
        "<html><head>"
        '<meta property="og:title" content="Fallback OG"/>'
        f"{json_ld}"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        "</head><body></body></html>"
    )


_EVENTO = {
    "name": "TI-ES - Data &amp; AI Meetup  #1",
    "startDate": "2026-11-18 18:00:00",
    "endDate": "2026-11-18 21:00:00",
    "strippedDetail": "Prepare-se para aprender muito sobre tecnologia, dados e IA.",
    "eventsAddress": {
        "name": "SENAC Vitória",
        "city": "Vitória",
        "state": "ES",
    },
    "images": {
        "logoCover": "https://images.sympla.com.br/evento-cover.png",
        "logoLarge": "https://images.sympla.com.br/evento-lg.png",
    },
}


def test_le_data_e_local_do_next_data_quando_nao_ha_json_ld():
    """O caso real: a página não tem NENHUM `<script type="application/ld+json">`."""
    dados = extrair(_pagina_sympla(_EVENTO), "https://www.sympla.com.br/evento/x")

    assert dados.data_inicio == "2026-11-18"
    assert dados.data_fim == "2026-11-18"
    assert dados.cidade == "Vitória"
    assert dados.estado == "ES"
    assert dados.local == "SENAC Vitória"
    assert dados.imagem == "https://images.sympla.com.br/evento-cover.png"


def test_desescapa_entidade_html_do_titulo_e_do_resumo():
    dados = extrair(_pagina_sympla(_EVENTO), "https://www.sympla.com.br/evento/x")

    # `_texto` também colapsa espaço duplo — o `&nbsp;` do nome vira um "
    # espaço normal nesse processo.
    assert dados.titulo == "TI-ES - Data & AI Meetup #1"
    assert "&amp;" not in (dados.titulo or "")


def test_json_ld_continua_tendo_prioridade_quando_existe():
    """Eventbrite, Meetup e Even3 não têm este problema — e não devem passar
    pelo caminho da Sympla."""
    dados = extrair(_pagina_sympla(_EVENTO, com_json_ld=True), "https://example.com/evento")

    # A data veio do JSON-LD (mesma chave "startDate" do dicionário de
    # teste), não precisou do __NEXT_DATA__.
    assert dados.data_inicio == "2026-11-18"


def test_pagina_sem_next_data_nem_json_ld_continua_sem_data():
    """Página que não é da Sympla e não tem JSON-LD: nenhuma data inventada."""
    html = '<html><head><meta property="og:title" content="Evento qualquer"/></head></html>'
    dados = extrair(html, "https://example.com/evento")

    assert dados.data_inicio is None
    assert dados.titulo == "Evento qualquer"


def test_next_data_mal_formado_nao_quebra_a_extracao():
    html = (
        "<html><head>"
        '<script id="__NEXT_DATA__" type="application/json">{nao e json valido</script>'
        '<meta property="og:title" content="Ainda funciona pelo OG"/>'
        "</head></html>"
    )
    dados = extrair(html, "https://www.sympla.com.br/evento/x")

    assert dados.data_inicio is None
    assert dados.titulo == "Ainda funciona pelo OG"


def test_next_data_sem_a_estrutura_esperada_nao_quebra():
    html = (
        "<html><head>"
        '<script id="__NEXT_DATA__" type="application/json">{"props": {"pageProps": {}}}</script>'
        "</head></html>"
    )
    dados = extrair(html, "https://www.sympla.com.br/evento/x")

    assert dados.data_inicio is None
