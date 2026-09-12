"""Curadoria da biblioteca — as regras que decidem o que entra no catálogo.

Offline como o resto da suíte: nenhuma chamada ao YouTube, ao Tavily ou a um
LLM. O que se testa aqui é o julgamento (ordenar, filtrar, carimbar), que é
onde os erros doem — uma fonte fora do ar o log mostra, mas um vídeo de 2015
ordenado acima da documentação oficial passa despercebido.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import resource_search as rs


# --- duração ---------------------------------------------------------------


@pytest.mark.parametrize(
    "iso,esperado",
    [
        ("PT1H2M10S", 62),
        ("PT45M", 45),
        ("PT30S", 1),  # arredonda para cima a partir de 30s
        ("PT20S", None),  # menos de meio minuto não é duração útil
        ("PT2H", 120),
        (None, None),
        ("lixo", None),
    ],
)
def test_duracao_iso8601(iso, esperado):
    assert rs._iso8601_minutes(iso) == esperado


# --- pontuação -------------------------------------------------------------


def test_video_popular_e_recente_ganha_de_video_popular_e_velho():
    stats = {"viewCount": "500000", "likeCount": "25000"}
    recente = rs._score_video(stats, date.today() - timedelta(days=60))
    antigo = rs._score_video(stats, date.today() - timedelta(days=365 * 6))
    assert recente > antigo


def test_video_sem_audiencia_perde_para_video_com_audiencia():
    novo = rs._score_video({"viewCount": "12", "likeCount": "1"}, date.today())
    consagrado = rs._score_video(
        {"viewCount": "800000", "likeCount": "40000"}, date.today() - timedelta(days=200)
    )
    assert consagrado > novo


def test_video_sem_estatistica_nao_explode():
    assert 0 <= rs._score_video({}, None) <= 100


def test_dominio_de_referencia_sobe_mesmo_em_posicao_pior():
    doc_em_quarto = rs._score_article(3, "https://developer.mozilla.org/pt-BR/docs/Web/CSS")
    blog_em_primeiro = rs._score_article(0, "https://blog-qualquer.com/css")
    assert doc_em_quarto > blog_em_primeiro


def test_sugestao_de_ia_entra_abaixo_de_busca_real():
    """O teto da IA (38) fica sob o piso prático da busca. É o que garante que
    a Biblioteca, ordenada por quality_score, mostre primeiro o que foi
    encontrado num índice real."""
    pior_artigo_de_busca = rs._score_article(rank=99, url="https://exemplo.com/x")
    assert pior_artigo_de_busca > 38


# --- carência --------------------------------------------------------------


def test_tag_nunca_curada_precisa_de_busca():
    assert rs.needs_curation({"curated_at": None}) is True
    assert rs.needs_curation({}) is True


def test_tag_curada_ontem_nao_rebusca():
    ontem = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert rs.needs_curation({"curated_at": ontem}) is False


def test_tag_curada_ha_um_mes_rebusca():
    antes = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert rs.needs_curation({"curated_at": antes}) is True


def test_carimbo_ilegivel_nao_prende_a_tag_para_sempre():
    assert rs.needs_curation({"curated_at": "quinta-feira"}) is True


def test_carimbo_sem_fuso_e_tratado_como_utc():
    ingenuo = (datetime.now(timezone.utc) - timedelta(days=1)).replace(tzinfo=None).isoformat()
    assert rs.needs_curation({"curated_at": ingenuo}) is False


# --- linha para o banco ----------------------------------------------------


def test_to_row_corta_campos_longos_e_formata_data():
    candidato = rs.Candidate(
        kind="article",
        title="t" * 500,
        url="https://exemplo.com/a",
        description="d" * 3000,
        published_at=date(2024, 3, 17),
        quality_score=180,
        tag_ids=["11111111-1111-1111-1111-111111111111"],
    )
    linha = candidato.to_row()

    assert len(linha["title"]) == 300
    assert len(linha["description"]) == 1000
    assert linha["published_at"] == "2024-03-17"
    # quality_score é uma coluna 0..100: 180 viraria um dado inválido que só
    # apareceria na ordenação, silenciosamente à frente de tudo.
    assert linha["quality_score"] == 100
    assert linha["tag_ids"] == ["11111111-1111-1111-1111-111111111111"]


def test_to_row_manda_none_e_nao_string_vazia_na_descricao():
    """A coluna é anulável; string vazia viraria uma descrição em branco na
    interface, que é diferente de não ter descrição."""
    linha = rs.Candidate(kind="doc", title="x", url="https://e.com").to_row()
    assert linha["description"] is None


# --- deduplicação ----------------------------------------------------------


async def test_youtube_nao_gasta_requisicao_de_validacao(monkeypatch):
    """A URL do YouTube foi montada a partir de um id que a API devolveu.
    Revalidá-la seria pedir de volta o que já é certo."""
    chamadas = []

    async def espia(client, url):
        chamadas.append(url)
        return True

    monkeypatch.setattr(rs, "_reachable", espia)

    entrada = [
        rs.Candidate(kind="video", title="v", url="https://youtube.com/watch?v=1", provider="youtube"),
        rs.Candidate(kind="article", title="a", url="https://exemplo.com/a", provider="exemplo.com"),
    ]
    saida = await rs._keep_reachable(entrada)

    assert len(saida) == 2
    assert chamadas == ["https://exemplo.com/a"]


async def test_link_repetido_na_mesma_leva_entra_uma_vez_so(monkeypatch):
    async def sempre_ok(client, url):
        return True

    monkeypatch.setattr(rs, "_reachable", sempre_ok)

    entrada = [
        rs.Candidate(kind="article", title="a", url="https://exemplo.com/guia"),
        rs.Candidate(kind="article", title="a de novo", url="https://exemplo.com/guia/"),
        rs.Candidate(kind="article", title="A MAIÚSCULO", url="https://EXEMPLO.com/GUIA"),
    ]
    saida = await rs._keep_reachable(entrada)
    assert len(saida) == 1


async def test_link_morto_nao_vira_linha(monkeypatch):
    async def so_o_primeiro(client, url):
        return "vivo" in url

    monkeypatch.setattr(rs, "_reachable", so_o_primeiro)

    entrada = [
        rs.Candidate(kind="doc", title="ok", url="https://exemplo.com/vivo"),
        rs.Candidate(kind="doc", title="inventado", url="https://exemplo.com/morto"),
    ]
    saida = await rs._keep_reachable(entrada)
    assert [item.url for item in saida] == ["https://exemplo.com/vivo"]


# --- fontes ----------------------------------------------------------------


async def test_sem_chave_nenhuma_a_busca_nao_chama_rede(monkeypatch):
    """Sem chave, `_youtube` e `_articles` devolvem lista vazia sem tocar em
    httpx — é o mesmo contrato dos provedores de IA."""
    monkeypatch.setattr(rs.settings, "youtube_api_key", "")
    monkeypatch.setattr(rs.settings, "tavily_api_key", "")
    monkeypatch.setattr(rs.settings, "brave_api_key", "")

    assert await rs._youtube("docker") == []
    assert await rs._articles("docker") == []
    assert rs.sources_enabled() == {"youtube": False, "artigos": False}


def test_idioma_sai_de_palavra_que_so_existe_em_portugues():
    assert rs._guess_language("Como usar Docker na prática", None) == "pt"
    assert rs._guess_language("Docker networking deep dive", None) == "en"


def test_provider_sai_do_host_sem_www():
    assert rs._provider_of("https://www.dev.to/artigo") == "dev.to"
    assert rs._provider_of("https://kubernetes.io/docs/") == "kubernetes.io"


# --- vídeo não entra como artigo -------------------------------------------


def test_pagina_de_video_nao_conta_como_artigo():
    """O buscador web devolve páginas do YouTube entre os resultados de texto.
    Aceitá-las como `article` produz uma linha sem duração, sem corte de Short
    e sem pontuação por audiência — e um vídeo dentro do filtro "Artigos"."""
    assert rs._is_video_host("https://www.youtube.com/watch?v=abc") is True
    assert rs._is_video_host("https://youtu.be/abc") is True
    assert rs._is_video_host("https://vimeo.com/12345") is True
    assert rs._is_video_host("https://kodekloud.com/blog/docker") is False


async def test_tavily_descarta_resultado_que_e_video(monkeypatch):
    class RespostaFalsa:
        status_code = 200

        @staticmethod
        def json():
            return {
                "results": [
                    {"url": "https://spacelift.io/blog/docker", "title": "Docker Tutorial"},
                    {"url": "https://www.youtube.com/watch?v=ZyWBs0CU2wk", "title": "Docker em 10min"},
                ]
            }

    class ClienteFalso:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, *_, **__):
            return RespostaFalsa()

    monkeypatch.setattr(rs.settings, "tavily_api_key", "chave-de-teste")
    monkeypatch.setattr(rs.httpx, "AsyncClient", lambda **_: ClienteFalso())

    achados = await rs._articles("docker")

    # Nenhuma pagina de video sobrevive, venha ela de qual consulta vier.
    assert all("youtube.com" not in item.url for item in achados)
    assert {item.url for item in achados} == {"https://spacelift.io/blog/docker"}
    # Duas consultas (uma em portugues, outra em ingles) contra um duplo que
    # responde igual as duas: a repeticao e esperada aqui e some em
    # `_keep_reachable`, que deduplica antes de gravar.
    assert len(achados) == 2


# --- idioma: o filtro "Português" so funciona se o rotulo estiver certo -----


def test_titulo_ingles_com_uma_palavra_portuguesa_continua_ingles():
    """A regra antiga era "achou uma palavra portuguesa? e portugues", e por
    isso o filtro Portugues devolvia artigo em ingles."""
    assert rs._guess_language("How to use Docker para beginners", None) == "en"


def test_decide_por_contagem_e_nao_por_presenca():
    assert rs._guess_language("Como criar uma API do zero na prática", None) == "pt"
    assert rs._guess_language("How to build an API from scratch with Node", None) == "en"


def test_sem_palavra_funcional_nenhuma_fica_em_ingles():
    """Empate cai em ingles de proposito: quase todo conteudo tecnico e ingles,
    e o erro relatado e o inverso -- ingles aparecendo no filtro Portugues. Na
    duvida o item fica FORA do filtro mais restrito, nao dentro."""
    assert rs._guess_language("Docker Kubernetes Terraform", None) == "en"
    assert rs._guess_language("", None) == "en"


# --- classificacao: documentacao e exercicio deixam de virar "artigo" -------


def test_documentacao_oficial_nao_e_artigo():
    assert rs._classifica("https://docs.docker.com/get-started/") == "doc"
    assert rs._classifica("https://developer.mozilla.org/pt-BR/docs/Web/CSS") == "doc"
    assert rs._classifica("https://fastapi.tiangolo.com/reference/") == "doc"
    assert rs._classifica("https://flask.readthedocs.io/en/stable/") == "doc"


def test_plataforma_de_exercicio_nao_e_artigo():
    """A pessoa nao le um exercicio, ela resolve. Junta-los no mesmo filtro
    apaga a unica diferenca que importa na hora de estudar."""
    assert rs._classifica("https://www.codewars.com/collections/exercicios") == "exercise"
    assert rs._classifica("https://exercism.org/tracks/python") == "exercise"
    assert rs._classifica("https://www.hackerrank.com/skills-directory/docker_basic") == "exercise"
    assert rs._classifica("https://www.beecrowd.com.br/judge/problems") == "exercise"


def test_blog_continua_artigo():
    assert rs._classifica("https://spacelift.io/blog/docker-tutorial") == "article"
    assert rs._classifica("https://kodekloud.com/blog/docker-tutorial") == "article"


def test_repositorio_e_repositorio():
    assert rs._classifica("https://github.com/docker/awesome-compose") == "repo"


# --- curso deixou de existir como tipo -------------------------------------


async def test_ia_nao_devolve_mais_curso(monkeypatch):
    """O filtro "Cursos" saiu da Biblioteca: o app nao sabe se a pessoa
    assistiu, quanto viu, nem o que aprendeu. Um curso indicado vira doc."""

    class ResultadoFalso:
        model = "teste"
        data = {
            "recursos": [
                {"titulo": "Curso de Docker", "url": "https://exemplo.com/curso", "tipo": "course"}
            ]
        }
        content = data

    async def falso(*_args, **_kwargs):
        return ResultadoFalso()

    monkeypatch.setattr(rs, "generate_json", falso)
    achados = await rs._ai_fallback("docker", "devops")
    assert [item.kind for item in achados] == ["doc"]


def test_docs_do_github_e_documentacao_nao_repositorio():
    """`docs.github.com` termina em "github.com". A regra de repositorio
    precisa casar o host EXATO -- medido em producao, onde duas paginas do
    GitHub Docs tinham entrado como repo."""
    assert rs._classifica("https://docs.github.com/en/actions/quickstart") == "doc"
    assert rs._classifica("https://github.com/docker/compose") == "repo"


# --- consultas em dois idiomas -------------------------------------------


async def test_uma_consulta_falhando_nao_apaga_a_outra(monkeypatch):
    chamadas = []

    async def falso(consulta, quantos):
        chamadas.append(consulta)
        if "português" in consulta:
            raise RuntimeError("fora do ar")
        return [rs.Candidate(kind="doc", title="d", url="https://docs.exemplo.com/")]

    monkeypatch.setattr(rs.settings, "tavily_api_key", "k")
    monkeypatch.setattr(rs, "_tavily", falso)
    achados = await rs._buscar_varias(["x em português", "x docs"], 3)
    assert len(chamadas) == 2
    assert [a.url for a in achados] == ["https://docs.exemplo.com/"]


async def test_documentacao_e_exercicio_procuram_tambem_em_portugues(monkeypatch):
    """So a consulta inglesa deixava o filtro Portugues sem documentacao e
    sem exercicio nenhum, mesmo onde existe traducao ou plataforma brasileira."""
    consultas = []

    async def falso(consulta, quantos):
        consultas.append(consulta)
        return []

    monkeypatch.setattr(rs.settings, "tavily_api_key", "k")
    monkeypatch.setattr(rs, "_tavily", falso)
    await rs._documentacao("Docker")
    await rs._exercicios("Docker")
    assert sum("português" in c for c in consultas) == 2
    assert any("official" in c for c in consultas) and any("practice" in c for c in consultas)


def test_plataforma_brasileira_e_exercicio():
    assert rs._classifica("https://judge.beecrowd.com/pt/problems/view/1001") == "exercise"
    assert rs._classifica("https://neps.academy/br/exercise/1") == "exercise"


# ---------------------------------------------------------------------------
# A mesma pagina listada duas vezes
#
# O catalogo tem `url` como identidade, e endereços que diferem so na barra
# final, no `www.` ou no esquema entravam como linhas separadas: a mesma
# pagina aparecendo duas vezes na biblioteca, cada uma com o seu progresso, e
# quem terminasse uma continuaria vendo a outra por fazer.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outra",
    [
        "https://exemplo.com/guia/",
        "http://exemplo.com/guia",
        "https://www.exemplo.com/guia",
        "https://exemplo.com/guia#instalacao",
        "https://EXEMPLO.com/Guia",
    ],
)
def test_enderecos_da_mesma_pagina_tem_a_mesma_identidade(outra):
    assert rs.canonica("https://exemplo.com/guia") == rs.canonica(outra)


@pytest.mark.parametrize(
    "outra",
    [
        # A query separa um video do outro -- ignora-la juntaria o YouTube
        # inteiro num material so.
        "https://exemplo.com/guia?v=2",
        "https://exemplo.com/guia/avancado",
        "https://outro.com/guia",
    ],
)
def test_paginas_diferentes_continuam_diferentes(outra):
    assert rs.canonica("https://exemplo.com/guia") != rs.canonica(outra)
