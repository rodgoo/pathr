"""Tradução pelo DeepL: o glossário dos termos, a detecção do que não traduziu,
e a reserva do modelo de IA.

Sem rede: `httpx.MockTransport` responde no lugar do DeepL. As frases de
exemplo são as que o DeepL real devolveu durante a integração.
"""

import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.services import traducao


class DeepLFalso:
    """Guarda os pedidos e responde como a API do DeepL."""

    def __init__(self):
        self.pedidos: list[httpx.Request] = []
        self.traducoes: dict[str, str] = {}
        self.glossarios: list[dict] = []
        self.falha = False

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.falha:
            return httpx.Response(503, json={"message": "fora"})
        caminho = pedido.url.path
        if caminho == "/v3/glossaries" and pedido.method == "GET":
            return httpx.Response(200, json={"glossaries": self.glossarios})
        if caminho == "/v3/glossaries" and pedido.method == "POST":
            corpo = json.loads(pedido.content)
            self.glossarios.append({"glossary_id": "g-novo", "name": corpo["name"]})
            return httpx.Response(201, json={"glossary_id": "g-novo", "dictionaries": corpo["dictionaries"]})
        if caminho.startswith("/v3/glossaries/") and pedido.method == "DELETE":
            return httpx.Response(204)
        if caminho == "/v2/translate":
            corpo = json.loads(pedido.content)
            return httpx.Response(
                200, json={"translations": [{"text": self.traducoes.get(t, t)} for t in corpo["text"]]}
            )
        return httpx.Response(404)

    def corpo(self, caminho: str, metodo: str = "POST") -> dict:
        pedido = next(p for p in self.pedidos if p.url.path == caminho and p.method == metodo)
        return json.loads(pedido.content)

    def traducoes_pedidas(self) -> int:
        return len([p for p in self.pedidos if p.url.path == "/v2/translate"])


@pytest.fixture
def deepl(monkeypatch):
    """Liga a chave (a suíte a desliga por padrão) e troca a rede pelo falso."""
    falso = DeepLFalso()
    monkeypatch.setattr(settings, "deepl_api_key", "chave-de-teste:fx")
    original = httpx.AsyncClient

    def cliente(**argumentos):
        argumentos.pop("transport", None)
        return original(transport=httpx.MockTransport(falso), **argumentos)

    monkeypatch.setattr(traducao.httpx, "AsyncClient", cliente)
    return falso


def _rodar(corotina):
    return asyncio.run(corotina)


# --- quando não usa o DeepL ---------------------------------------------------


def test_sem_chave_nao_traduz_e_quem_chama_mantem_a_do_modelo():
    assert _rodar(traducao.traduzir(["Hello team"], "en")) is None


def test_portugues_nao_e_traduzido_para_portugues(deepl):
    assert _rodar(traducao.traduzir(["Olá, time"], "pt")) is None
    assert deepl.pedidos == []


def test_deepl_fora_do_ar_devolve_none_sem_levantar(deepl):
    deepl.falha = True
    assert _rodar(traducao.traduzir(["Please review my code."], "en")) is None


def test_plano_free_usa_o_endereco_free(deepl):
    _rodar(traducao.traduzir(["Please review my code."], "en"))
    assert deepl.pedidos and all(p.url.host == "api-free.deepl.com" for p in deepl.pedidos)


# --- o glossário dos termos ---------------------------------------------------


def test_glossario_unico_cobre_todos_os_idiomas_com_os_termos_universais(deepl):
    """O plano Free permite UM glossário: um dicionário por idioma dentro dele."""
    _rodar(traducao.traduzir(["We deleted the old branches after the merge."], "en"))
    criado = deepl.corpo("/v3/glossaries")
    origens = {d["source_lang"] for d in criado["dictionaries"]}
    assert origens == {"en", "es", "fr", "de", "it", "ja", "zh", "ko"}
    entradas = dict(linha.split("\t") for linha in criado["dictionaries"][0]["entries"].splitlines())
    for termo in ("front end", "back end", "worktree", "branches", "merge", "deploy", "pull request"):
        assert entradas[termo] == termo
    assert deepl.corpo("/v2/translate")["glossary_id"] == "g-novo"


def test_glossario_de_lista_antiga_e_trocado_para_liberar_a_vaga(deepl):
    deepl.glossarios.append({"glossary_id": "g-velho", "name": "pathr-termos-0000000000"})
    _rodar(traducao.traduzir(["Please review my code."], "en"))
    apagados = [p.url.path for p in deepl.pedidos if p.method == "DELETE"]
    assert apagados == ["/v3/glossaries/g-velho"]


def test_glossario_atual_e_reaproveitado_sem_criar_outro(deepl):
    deepl.glossarios.append({"glossary_id": "g-atual", "name": traducao.nome_do_glossario()})
    _rodar(traducao.traduzir(["Please review my code."], "en"))
    assert not any(p.method == "POST" and p.url.path == "/v3/glossaries" for p in deepl.pedidos)
    assert deepl.corpo("/v2/translate")["glossary_id"] == "g-atual"


def test_mudar_a_lista_muda_o_nome_do_glossario(monkeypatch):
    antes = traducao.nome_do_glossario()
    monkeypatch.setattr(traducao, "TERMOS_DO_GLOSSARIO", traducao.TERMOS_DO_GLOSSARIO + ("monorepo",))
    assert traducao.nome_do_glossario() != antes


# --- a saída é português? -----------------------------------------------------


@pytest.mark.parametrize(
    "saida",
    [
        # Devolvidas pelo DeepL real com glossário, REESCRITAS em inglês —
        # nenhuma igual à entrada, então comparar com ela não pegaria.
        "The deployment failed after the last commit on the main branch.",
        "The build failed due to a bug in the pipeline.",
        "Our release branch is frozen until Tuesday.",
        "El deploy falló después del último commit.",
        "デプロイは最後のコミットの後に失敗しました。",
    ],
)
def test_saida_que_nao_e_portugues_e_recusada(saida):
    assert not traducao.parece_portugues(saida)


@pytest.mark.parametrize(
    "saida",
    [
        "Faça o merge do branch antes da release.",
        "Crie uma worktree, corrija a query e abra uma pull request.",
        "Eu trabalho com front end e meu colega cuida do back end.",
        "Qual framework o backend utiliza?",
        "Você poderia me enviar o relatório até sexta-feira?",
        "reservar",
        "branch",
    ],
)
def test_portugues_com_termos_em_ingles_e_aceito(saida):
    """Os termos técnicos ficam em inglês de propósito e não podem fazer uma
    frase portuguesa parecer inglesa."""
    assert traducao.parece_portugues(saida)


@pytest.mark.parametrize(
    "original,traduzida,preserva",
    [
        # Caso de produção: o glossário não pegou "branches" numa frase
        # reestruturada.
        ("We deleted the old branches after the merge.", "Após o merge, excluímos os ramos antigos.", False),
        ("We deleted the old branches after the merge.", "Apagamos os branches antigos após o merge.", True),
        # Grafias trocadas pelo DeepL contam como o mesmo termo.
        ("I work on the front end and my colleague handles the back end.",
         "Eu trabalho com front-end e meu colega cuida do back-end.", True),
        # Plural que vira singular não é tradução do termo.
        ("Create worktrees for the branches.", "Crie uma worktree para cada branch.", True),
        ("Create a new worktree for each branch.", "Crie uma nova árvore de trabalho para cada ramo.", False),
        # "merge request" é um termo só; "merge" dentro dele não é cobrado à parte.
        ("Open a merge request today.", "Abra uma merge request hoje.", True),
        ("Could you send me the report by Friday?", "Você poderia me enviar o relatório até sexta?", True),
    ],
)
def test_termo_de_programacao_nao_pode_sumir_da_traducao(original, traduzida, preserva):
    assert traducao.preserva_termos(original, traduzida) is preserva


def test_palavra_com_sentido_comum_fica_fora_do_glossario():
    """Medido com o glossário real: "release a new phone" virou "realizará uma
    release de um novo celular", e "books on the stack" virou "na stack"."""
    for ambiguo in ("build", "release", "daily", "stack", "script", "commit", "query", "log"):
        assert ambiguo not in traducao.TERMOS_DO_GLOSSARIO
        assert ambiguo in traducao.TERMOS_UNIVERSAIS  # mas vai para o prompt do modelo
    for tecnico in ("front end", "back end", "worktree", "branches", "merge", "deploy", "pull request"):
        assert tecnico in traducao.TERMOS_DO_GLOSSARIO


def test_sentido_comum_traduzido_nao_e_cobrado():
    assert traducao.preserva_termos(
        "The company will release a new phone next month.", "A empresa vai lançar um novo celular no mês que vem."
    )


def test_prompt_do_modelo_distingue_sentido_tecnico_do_comum():
    from app.routers import language_practice as router

    assert "SENTIDO TÉCNICO" in router.PRACTICE_PROMPT
    assert "release" in router.PRACTICE_PROMPT


def test_traducao_que_perdeu_um_termo_fica_com_a_do_modelo(deepl):
    original = "We deleted the old branches after the merge."
    deepl.traducoes = {original: "Após o merge, excluímos os ramos antigos."}
    assert _rodar(traducao.traduzir([original], "en")) == [None]


def test_item_que_voltou_em_ingles_fica_none_e_o_resto_passa(deepl):
    entrada_ruim = "The deploy failed after the last commit on the main branch."
    entrada_boa = "Merge the branch before the release."
    deepl.traducoes = {
        entrada_ruim: "The deployment failed after the last commit on the main branch.",
        entrada_boa: "Faça o merge do branch antes da release.",
    }
    saida = _rodar(traducao.traduzir([entrada_ruim, entrada_boa], "en"))
    assert saida == [None, "Faça o merge do branch antes da release."]


def test_contexto_vai_junto_e_o_cache_evita_pagar_de_novo(deepl):
    deepl.traducoes = {"book": "reservar"}
    contexto = "Could you book a meeting room for tomorrow?"
    assert _rodar(traducao.traduzir(["book"], "en", contexto=contexto)) == ["reservar"]
    assert deepl.corpo("/v2/translate")["context"] == contexto
    pedidas = deepl.traducoes_pedidas()
    assert _rodar(traducao.traduzir(["book"], "en", contexto=contexto)) == ["reservar"]
    assert deepl.traducoes_pedidas() == pedidas


# --- as duas integrações ------------------------------------------------------


def test_treino_troca_a_traducao_do_modelo_pela_do_deepl(deepl):
    from app.routers import language_practice as router

    deepl.traducoes = {"I already merged the pull request": "Já fiz o merge da pull request"}
    prontos = [
        {
            "payload": {"pecas": ["x"], "traducao": "Eu já fundi a solicitação"},
            "gabarito": {"frases": ["I already merged the pull request"]},
        },
        {"payload": {"alternativas": ["a"]}, "gabarito": {"indice": 0}},
    ]
    _rodar(router._traduz_pelo_deepl("en", prontos))
    assert prontos[0]["payload"]["traducao"] == "Já fiz o merge da pull request"
    assert "traducao" not in prontos[1]["payload"]


def test_treino_mantem_a_do_modelo_quando_o_deepl_devolve_ingles(deepl):
    from app.routers import language_practice as router

    original = "The build broke because of a bug in the pipeline."
    deepl.traducoes = {original: "The build failed due to a bug in the pipeline."}
    pronto = {
        "payload": {"texto": "x", "traducao": "O build quebrou por causa de um bug no pipeline."},
        "gabarito": {"texto": original},
    }
    _rodar(router._traduz_pelo_deepl("en", [pronto]))
    assert pronto["payload"]["traducao"] == "O build quebrou por causa de um bug no pipeline."


def test_consulta_de_palavra_usa_o_deepl_e_sobrevive_a_ia_fora(deepl, monkeypatch):
    from app.routers import languages as router
    from tests.fake_supabase import FakeSupabase

    deepl.traducoes = {"book": "reservar"}

    async def ia_fora(*_a, **_k):
        raise router.AiProviderError("fora do ar")

    monkeypatch.setattr(router, "generate_json", ia_fora)
    resposta = _rodar(router.lookup_word(
        router.VocabLookup(term="book", language="en", context="Could you book a meeting room?"),
        current_user={"id": "11111111-1111-1111-1111-111111111111"},
        supabase=FakeSupabase(pathr_english_vocab=[]),
    ))
    assert resposta["translation"] == "reservar"


def test_prompts_do_modelo_levam_a_mesma_lista_de_termos():
    """A reserva e o DeepL precisam preservar os mesmos termos."""
    from app.routers import language_practice as router

    for termo in ("front end", "back end", "worktree", "branches", "merge", "deploy"):
        assert termo in router.PRACTICE_PROMPT
