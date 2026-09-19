"""A aba de Notícias: eventos de tecnologia, perto, com data de verdade.

Cada teste aqui nasceu de um defeito que a pessoa viu na tela:

- todo evento aparecia com a data de HOJE (o código caía em `date.today()`
  quando a busca não trazia data);
- entrava evento que não é de tecnologia (uma feira automotiva que fala em
  "inovação e tecnologia");
- entrava evento de outra cidade (a cidade caía para a cidade BUSCADA quando a
  página não dizia nada);
- a tela ficava em "Buscando eventos…" para sempre (a varredura acontecia
  dentro da requisição, e região sem resultado era varrida de novo a cada
  abertura).
"""

import asyncio
from types import SimpleNamespace

import httpx

from app.services import evento_da_pagina, noticias
from tests.fake_supabase import FakeSupabase


def _pagina(
    *,
    inicio="2026-10-28",
    fim=None,
    cidade="Vitória",
    estado="ES",
    imagem="https://img.exemplo/cartaz.jpg",
    preco="0",
) -> str:
    """Uma página de catálogo de evento, como Sympla e Eventbrite publicam."""
    lugar = (
        '"location": {"@type": "Place", "name": "Centro de Convenções",'
        f' "address": {{"@type": "PostalAddress", "addressLocality": "{cidade}",'
        f' "addressRegion": "{estado}"}}}},'
        if cidade
        else ""
    )
    return f"""
    <html><head>
    <script type="application/ld+json">
    {{"@context": "https://schema.org", "@type": "Event",
      "name": "Meetup de Python", "description": "Encontro da comunidade.",
      "startDate": "{inicio}", {f'"endDate": "{fim}",' if fim else ""}
      {lugar}
      "image": "{imagem}",
      "offers": {{"@type": "Offer", "price": "{preco}", "priceCurrency": "BRL"}}}}
    </script>
    <meta property="og:image" content="https://img.exemplo/og.jpg" />
    </head><body>conteúdo</body></html>
    """


def _bruto(url="https://sympla.com.br/meetup-python", titulo="Meetup de Python", trecho="Encontro"):
    return noticias.EventoBruto(url=url, titulo=titulo, trecho=trecho)


def _rodar(corotina):
    return asyncio.run(corotina)


# ---------------------------------------------------------------------------
# A página é a fonte da data, do lugar e da imagem
# ---------------------------------------------------------------------------


def test_extrai_data_lugar_e_imagem_do_json_ld():
    dados = evento_da_pagina.extrair(_pagina(), "https://sympla.com.br/x")

    assert dados.data_inicio == "2026-10-28"
    assert dados.cidade == "Vitória"
    assert dados.estado == "ES"
    assert dados.local == "Centro de Convenções"
    assert dados.imagem == "https://img.exemplo/cartaz.jpg"
    assert dados.gratuito is True


def test_sem_json_ld_a_imagem_vem_do_open_graph():
    html = '<html><head><meta property="og:image" content="/capa.png"></head></html>'
    dados = evento_da_pagina.extrair(html, "https://even3.com.br/congresso")

    # Endereço relativo vira absoluto, senão a tela pediria a imagem ao PathR.
    assert dados.imagem == "https://even3.com.br/capa.png"
    # Mas data não se inventa a partir de og: sem data, o evento não entra.
    assert dados.data_inicio is None


def test_data_com_hora_e_fuso_vira_dia():
    dados = evento_da_pagina.extrair(_pagina(inicio="2026-10-28T19:30:00-03:00"), "https://x.com/y")
    assert dados.data_inicio == "2026-10-28"


def test_evento_online_nao_conta_como_perto():
    html = """<html><head><script type="application/ld+json">
    {"@type": "Event", "name": "Live", "startDate": "2026-10-28",
     "location": {"@type": "VirtualLocation", "url": "https://zoom.us/j/1"}}
    </script></head></html>"""
    assert evento_da_pagina.extrair(html, "https://x.com/y").online is True


# ---------------------------------------------------------------------------
# O que NÃO entra
# ---------------------------------------------------------------------------


def _cliente_que_serve(html):
    def responder(_pedido):
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html, headers={"content-type": "text/html; charset=utf-8"})

    return httpx.AsyncClient(transport=httpx.MockTransport(responder))


def _montar(html, monkeypatch, *, cidade="Vitória", uf="ES", perto=None, bruto=None):
    # Sem rede: a guarda de saída resolveria o nome de verdade (ela tem testes
    # próprios em test_saida.py).
    monkeypatch.setattr(noticias.saida, "destino_pinado", lambda url: (url, {}, {}))

    async def cenario():
        async with _cliente_que_serve(html) as cliente:
            return await noticias._montar(
                cliente, bruto or _bruto(), cidade, uf, perto or {"vitoria"}
            )

    return _rodar(cenario())


def test_evento_sem_data_na_pagina_nao_entra(monkeypatch):
    """O defeito que a pessoa viu: TODO evento aparecia com a data de hoje."""
    html = '<html><head><meta property="og:title" content="Algum evento"></head></html>'
    assert _montar(html, monkeypatch) is None


def test_evento_que_ja_passou_nao_entra(monkeypatch):
    assert _montar(_pagina(inicio="2020-01-01"), monkeypatch) is None


def test_evento_de_outra_cidade_nao_entra(monkeypatch):
    """Antes, a cidade caía para a BUSCADA quando a página não dizia — e um
    evento de São Paulo virava "Vitória" por omissão."""
    fora = _pagina(cidade="São Paulo", estado="SP")
    assert _montar(fora, monkeypatch, perto={"vitoria", "vila velha"}) is None


def test_pagina_que_nao_abre_nao_entra(monkeypatch):
    assert _montar(None, monkeypatch) is None


def test_evento_da_regiao_entra_completo(monkeypatch):
    campos = _montar(_pagina(fim="2026-10-29"), monkeypatch)

    assert campos is not None
    assert campos["event_start"] == "2026-10-28"
    assert campos["event_end"] == "2026-10-29"
    assert campos["city"] == "Vitória"
    assert campos["state"] == "ES"
    assert campos["image_url"] == "https://img.exemplo/cartaz.jpg"
    assert campos["is_free"] is True


def test_sem_imagem_na_pagina_usa_o_icone_do_site(monkeypatch):
    html = """<html><head><script type="application/ld+json">
    {"@type": "Event", "name": "Meetup", "startDate": "2026-10-28",
     "location": {"@type": "Place", "address": {"addressLocality": "Vitória", "addressRegion": "ES"}}}
    </script></head></html>"""
    campos = _montar(html, monkeypatch)

    assert campos is not None
    # Nunca sem imagem: o card ficaria só texto no meio dos outros.
    assert "sympla.com.br" in campos["image_url"]


# ---------------------------------------------------------------------------
# Só tecnologia
# ---------------------------------------------------------------------------


def test_feira_automotiva_nao_e_evento_de_tecnologia(monkeypatch):
    """O EXPOAUTOS que apareceu na tela: fala em "inovação e tecnologia", mas é
    do setor automotivo."""
    candidatos = [
        _bruto(
            "https://sympla.com.br/expoautos",
            "EXPOAUTOS - O Espírito Santo Sobre Rodas",
            "Encontro do setor automotivo com negócios, inovação, tecnologia e networking.",
        ),
        _bruto("https://sympla.com.br/data-ai", "Data & AI Saturday", "Palestras sobre dados e IA."),
    ]

    async def falsa(_sistema, _prompt, _schema):
        return SimpleNamespace(
            content={"itens": [{"indice": 0, "tecnologia": False}, {"indice": 1, "tecnologia": True}]}
        )

    monkeypatch.setattr(noticias, "generate_json", falsa)
    restantes = _rodar(noticias.somente_tecnologia(candidatos))

    assert [b.titulo for b in restantes] == ["Data & AI Saturday"]


def test_ia_fora_do_ar_nao_esvazia_a_aba(monkeypatch):
    """Sem classificação, passa tudo: data e região ainda filtram depois, e uma
    aba vazia é pior do que uma aba com um evento a mais."""

    async def quebra(*_args):
        raise noticias.AiProviderError("sem provedor")

    monkeypatch.setattr(noticias, "generate_json", quebra)
    candidatos = [_bruto()]
    assert _rodar(noticias.somente_tecnologia(candidatos)) == candidatos


# ---------------------------------------------------------------------------
# A varredura não entra em laço
# ---------------------------------------------------------------------------


def _banco(**tabelas):
    padrao = {"pathr_news_event": [], "pathr_news_scan": [], "pathr_news_attendance": []}
    return FakeSupabase(**{**padrao, **tabelas})


def test_regiao_varrida_ha_pouco_nao_e_varrida_de_novo(monkeypatch):
    banco = _banco()
    chamou = []

    async def busca(cidade, uf):
        chamou.append((cidade, uf))
        return []

    monkeypatch.setattr(noticias, "buscar_bruto", busca)

    assert _rodar(noticias.atualizar_regiao(banco, "Vitória", "ES")) == 0
    assert len(chamou) == 1
    # A marca ficou gravada MESMO sem nenhum evento encontrado — é isto que
    # impede a varredura de recomeçar a cada abertura da tela.
    assert banco.table("pathr_news_scan").select("*").execute().data
    assert noticias.precisa_buscar(banco, "Vitória", "ES") is False

    assert _rodar(noticias.atualizar_regiao(banco, "Vitória", "ES")) == 0
    assert len(chamou) == 1  # não buscou de novo


def test_sem_cidade_no_perfil_nao_varre():
    banco = _banco()
    assert noticias.precisa_buscar(banco, None, None) is False
    assert noticias.precisa_buscar(banco, "Vitória", None) is False


# ---------------------------------------------------------------------------
# A listagem
# ---------------------------------------------------------------------------


def test_listagem_so_traz_cidade_dentro_do_raio():
    banco = _banco(
        pathr_news_event=[
            {"id": "1", "title": "Perto", "city": "Vitória", "state": "ES", "event_start": "2026-10-28"},
            {"id": "2", "title": "Longe", "city": "São Paulo", "state": "SP", "event_start": "2026-10-28"},
            {"id": "3", "title": "Sem cidade", "city": None, "state": "ES", "event_start": "2026-10-28"},
        ]
    )

    lista = noticias.listar_por_regiao(banco, "u1", "Vitória", "ES", 50.0)

    # "mesmo estado" e "sem cidade" não são "perto de você".
    assert [e["titulo"] for e in lista] == ["Perto"]


def test_listagem_leva_a_imagem_para_a_tela():
    banco = _banco(
        pathr_news_event=[
            {
                "id": "1",
                "title": "Meetup",
                "city": "Vitória",
                "state": "ES",
                "event_start": "2026-10-28",
                "image_url": "https://img.exemplo/cartaz.jpg",
            }
        ]
    )

    lista = noticias.listar_por_regiao(banco, "u1", "Vitória", "ES", 50.0)
    assert lista[0]["imagem"] == "https://img.exemplo/cartaz.jpg"
