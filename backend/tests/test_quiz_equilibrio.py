"""A certa não pode se denunciar: alternativas do mesmo tamanho, e a ordem sorteada.

O relato: "as perguntas quase sempre maiores são as corretas; o cérebro humano procura inconscientemente as maiores e
mais bem formuladas para marcar". Um modelo de IA escreve a certa mais longa e elaborada quase sempre, então o quiz
virava um teste de "qual é a maior". Três defesas: o prompt pede alternativas do mesmo tamanho, a ordem é sorteada, e
o que ainda sai desequilibrado é reescrito numa única chamada extra.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.ai_providers import AiProviderError
from app.routers import quizzes
from tests.fake_supabase import FakeSupabase

# O sorteio REAL, guardado antes de qualquer fixture trocá-lo.
_MISTURAR_REAL = quizzes._misturar

EU = {"id": str(uuid.uuid4()), "email": "ana@exemplo.com", "timezone_name": "America/Sao_Paulo"}

# Quatro alternativas de 38 a 40 caracteres: a certa (a primeira) não é maior que a maior errada.
IGUAIS = [
    "copiar so os manifestos antes do install",
    "copiar tudo antes de rodar o npm install",
    "trocar COPY por ADD no arquivo inteiro.",
    "rodar npm install sem usar o lockfile..",
]


@pytest.fixture(autouse=True)
def sem_sorteio(monkeypatch):
    """A ordem das alternativas fica como veio, salvo nos testes que trocam o sorteio de propósito."""
    monkeypatch.setattr(quizzes, "_misturar", lambda itens: None)


def _inverter(itens):
    itens.reverse()


# --- o sorteio da ordem -------------------------------------------------------


def test_a_ordem_muda_e_o_gabarito_e_a_analise_acompanham(monkeypatch):
    monkeypatch.setattr(quizzes, "_misturar", _inverter)
    opcoes, correta, analise = quizzes._embaralhar(
        ["A", "B", "C", "D"], 1, ["por que A", "por que B", "por que C", "por que D"], "A ideia central."
    )
    assert opcoes == ["D", "C", "B", "A"]
    assert opcoes[correta] == "B", "a certa continua sendo a mesma alternativa"
    assert analise == ["por que D", "por que C", "por que B", "por que A"], "cada texto continua junto da sua alternativa"


def test_sem_analise_a_ordem_tambem_muda(monkeypatch):
    monkeypatch.setattr(quizzes, "_misturar", _inverter)
    opcoes, correta, analise = quizzes._embaralhar(["A", "B", "C", "D"], 0, None, "resumo")
    assert opcoes[correta] == "A" and analise is None


@pytest.mark.parametrize(
    "resumo, analise",
    [
        ("A alternativa 2 é a certa porque preserva a camada.", None),
        ("Resumo sem número.", ["x", "A opção B confunde COPY com ADD.", "y", "z"]),
        ("A letra C erra o cache.", None),
        ("Option 3 is right.", None),
    ],
)
def test_texto_que_cita_alternativa_por_numero_ou_letra_nao_e_embaralhado(monkeypatch, resumo, analise):
    """Embaralhar faria o texto apontar para a alternativa errada — uma explicação que contradiz o gabarito."""
    monkeypatch.setattr(quizzes, "_misturar", _inverter)
    opcoes, correta, saida = quizzes._embaralhar(["A", "B", "C", "D"], 1, analise, resumo)
    assert opcoes == ["A", "B", "C", "D"] and correta == 1 and saida == analise


def test_alternativa_correta_sem_numero_nao_conta_como_citacao(monkeypatch):
    """"A alternativa correta usa cache" fala da certa, não de uma posição: pode embaralhar."""
    monkeypatch.setattr(quizzes, "_misturar", _inverter)
    opcoes, _, _ = quizzes._embaralhar(["A", "B", "C", "D"], 1, None, "A alternativa correta usa cache de camadas.")
    assert opcoes == ["D", "C", "B", "A"]


def test_o_sorteio_de_verdade_e_uma_permutacao_e_a_certa_passa_por_todas_as_posicoes():
    posicoes = set()
    for _ in range(300):
        itens = [0, 1, 2, 3]
        _MISTURAR_REAL(itens)
        assert sorted(itens) == [0, 1, 2, 3]
        posicoes.add(itens.index(0))
    assert posicoes == {0, 1, 2, 3}, "a certa não fica presa em um lugar"


# --- medir se a certa se denuncia ---------------------------------------------


def _questao(alternativas, correta=0):
    return {"alternativas": alternativas, "correta": correta, "enunciado": "Enunciado?", "resumo": "Resumo.", "analise": None,
            "explicacao": "Resumo.", "codigo": "", "linguagem": "", "dificuldade": "medio", "conceito": "c"}


def test_certa_bem_mais_longa_destoa():
    assert quizzes._destoa(_questao(["x" * 90, "x" * 40, "x" * 42, "x" * 38], correta=0))


def test_alternativas_do_mesmo_tamanho_nao_destoam():
    assert not quizzes._destoa(_questao(["x" * 40, "y" * 41, "z" * 39, "w" * 40], correta=2))


def test_certa_que_nao_e_a_maior_nao_destoa():
    assert not quizzes._destoa(_questao(["x" * 60, "y" * 90, "z" * 40, "w" * 50], correta=0))


def test_certa_um_pouco_maior_dentro_da_tolerancia_nao_destoa():
    assert not quizzes._destoa(_questao(["x" * 43, "y" * 40, "z" * 41, "w" * 40], correta=0))


def test_as_alternativas_de_exemplo_estao_dentro_da_tolerancia():
    """Guarda o próprio dado dos testes abaixo: se IGUAIS destoasse, eles reprovariam por motivo errado."""
    assert not quizzes._destoa(_questao(IGUAIS, correta=0))


# --- reescrever o que se denuncia --------------------------------------------


@pytest.fixture
def ia(monkeypatch):
    """A IA de mentira. Cada item de `respostas` é uma chamada: exceção = falha; dict = o conteúdo inteiro; lista = as `questoes`."""
    estado = {"respostas": [], "pedidos": []}

    async def falso(sistema, prompt, schema, **k):
        estado["pedidos"].append({"sistema": sistema, "prompt": prompt})
        resposta = estado["respostas"].pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        conteudo = resposta if isinstance(resposta, dict) else {"questoes": resposta}
        return SimpleNamespace(content=conteudo, model="falso")

    monkeypatch.setattr(quizzes, "generate_json", falso)
    return estado


def _desequilibrada():
    q = _questao(
        ["copiar apenas package.json e package-lock.json antes do npm install, e o resto depois", "copiar tudo", "usar ADD", "rodar npm install"],
        correta=0,
    )
    q["analise"] = ["certa", "errada 1", "errada 2", "errada 3"]
    q["explicacao"] = quizzes._explicacao_formatada("Resumo.", q["analise"], 0)
    return q


async def test_questao_equilibrada_nao_gasta_chamada_de_ia(ia):
    boa = _questao(["x" * 40, "y" * 41, "z" * 39, "w" * 40], correta=1)
    assert await quizzes._equilibrar([boa]) == [boa]
    assert ia["pedidos"] == []


async def test_a_desequilibrada_e_reescrita_e_a_explicacao_e_refeita(ia):
    ia["respostas"] = [[{"alternativas": IGUAIS, "analise": ["por que 1", "por que 2", "por que 3", "por que 4"]}]]
    [nova] = await quizzes._equilibrar([_desequilibrada()])
    assert nova["alternativas"] == IGUAIS and nova["correta"] == 0, "o gabarito não muda"
    assert not quizzes._destoa(nova)
    assert "**Alternativa 1 — correta.** por que 1" in nova["explicacao"]
    assert "**Alternativa 2 — errada.** por que 2" in nova["explicacao"]
    assert nova["explicacao"].startswith("Resumo.")


async def test_o_pedido_leva_so_as_desequilibradas_com_o_gabarito(ia):
    ia["respostas"] = [[{"alternativas": IGUAIS, "analise": ["a", "b", "c", "d"]}]]
    boa = _questao(["x" * 40, "y" * 41, "z" * 39, "w" * 40], correta=1)
    boa["enunciado"] = "Esta esta equilibrada?"
    await quizzes._equilibrar([boa, _desequilibrada()])
    prompt = ia["pedidos"][0]["prompt"]
    assert "QUESTAO 1" in prompt and "QUESTAO 2" not in prompt
    assert "Esta esta equilibrada?" not in prompt
    assert "CORRETA: 1" in prompt


async def test_so_a_desequilibrada_muda_as_outras_ficam_como_estavam(ia):
    ia["respostas"] = [[{"alternativas": IGUAIS, "analise": ["a", "b", "c", "d"]}]]
    boa = _questao(["x" * 40, "y" * 41, "z" * 39, "w" * 40], correta=1)
    saida = await quizzes._equilibrar([boa, _desequilibrada()])
    assert saida[0] == boa and saida[1]["alternativas"] == IGUAIS


@pytest.mark.parametrize(
    "resposta",
    [
        AiProviderError("cota do dia"),
        [],  # quantidade errada
        [{"alternativas": ["so", "tres", "opcoes"]}],  # 3 alternativas
        [{"alternativas": ["a", "b", "", "d"]}],  # uma vazia
        ["texto solto"],
        [{"alternativas": ["x" * 200, "y" * 20, "z" * 20, "w" * 20]}],  # ficou PIOR: a certa ainda mais destacada
    ],
)
async def test_resposta_ruim_da_ia_mantem_a_questao_original(ia, resposta):
    """Nunca piora nem derruba o quiz: sem uma reescrita válida que melhore, fica o que já havia."""
    ia["respostas"] = [resposta]
    original = _desequilibrada()
    assert await quizzes._equilibrar([original]) == [original]


async def test_reescrita_sem_analise_nova_mantem_a_analise_antiga(ia):
    ia["respostas"] = [[{"alternativas": IGUAIS}]]
    [nova] = await quizzes._equilibrar([_desequilibrada()])
    assert nova["alternativas"] == IGUAIS and "**Alternativa 1 — correta.** certa" in nova["explicacao"]


# --- os prompts ---------------------------------------------------------------


def test_o_prompt_do_quiz_pede_alternativas_do_mesmo_tamanho_e_proibe_a_certa_maior():
    p = quizzes.SYSTEM_PROMPT
    assert "MESMO formato" in p and "10% em caracteres" in p
    assert "A certa NÃO pode" in p and "a mais longa" in p
    assert "NUNCA por número ou letra" in p, "a ordem é embaralhada depois de escrita"


def test_o_prompt_de_equilibrio_preserva_o_sentido_e_o_gabarito():
    p = quizzes.EQUILIBRIO_PROMPT
    assert "MESMO tamanho" in p and "A certa NÃO seja a mais longa" in p
    assert "Não troque a resposta" in p and "MESMA ORDEM" in p


# --- de ponta a ponta ---------------------------------------------------------


@pytest.fixture
def banco(monkeypatch):
    monkeypatch.setattr(quizzes, "_due_reviews", lambda *a, **k: [])
    monkeypatch.setattr(quizzes, "_recent_scores", lambda *a, **k: [])
    monkeypatch.setattr(quizzes, "_materiais_concluidos", lambda *a, **k: [])
    monkeypatch.setattr(quizzes.conhecimento, "pendentes", lambda *a, **k: [])
    return FakeSupabase(
        pathr_tag=[{"id": "t1", "name": "Docker"}], pathr_user_tag=[], pathr_quiz=[], pathr_question=[], pathr_attempt=[],
    )


def _do_modelo(i, certa_denunciada):
    """Uma questão como o modelo a devolve: a certa é a primeira, e nas denunciadas é muito maior que as outras."""
    if certa_denunciada:
        alternativas = ["copiar apenas os manifestos de dependencia antes do install e o restante depois", "copiar tudo", "usar ADD", "rodar install"]
    else:
        alternativas = ["a" * 30, "b" * 31, "c" * 29, "d" * 30]
    return {
        "conceito": f"c{i}", "enunciado": f"Enunciado {i} sobre camadas do Docker?", "dificuldade": "medio",
        "alternativas": alternativas, "correta": 0, "explicacao": "A ideia central.",
        "analise": ["certa", "errada 1", "errada 2", "errada 3"],
    }


async def test_quiz_gerado_com_a_certa_denunciada_sai_reescrito_em_uma_chamada_so(ia, banco):
    ia["respostas"] = [
        {"titulo": "Quiz", "questoes": [_do_modelo(0, True), _do_modelo(1, True), _do_modelo(2, False)]},
        [{"alternativas": IGUAIS, "analise": ["p1", "p2", "p3", "p4"]}, {"alternativas": IGUAIS, "analise": ["p1", "p2", "p3", "p4"]}],
    ]

    quiz = await quizzes.generate_quiz(quizzes.GenerateQuiz(tag_ids=["t1"], question_count=3), EU, banco)

    assert len(quiz["questions"]) == 3
    assert len(ia["pedidos"]) == 2, "uma chamada para gerar e UMA para reequilibrar (não uma por questão)"
    gravadas = banco.linhas("pathr_question")
    reescritas = [q for q in gravadas if q["options"] == IGUAIS]
    assert len(reescritas) == 2 and all(q["correct"] == {"index": 0} for q in reescritas)
    assert all("**Por que cada alternativa:**" in q["explanation"] for q in gravadas)


async def test_quiz_ja_equilibrado_nao_faz_chamada_extra(ia, banco):
    ia["respostas"] = [{"titulo": "Quiz", "questoes": [_do_modelo(i, False) for i in range(3)]}]
    quiz = await quizzes.generate_quiz(quizzes.GenerateQuiz(tag_ids=["t1"], question_count=3), EU, banco)
    assert len(quiz["questions"]) == 3 and len(ia["pedidos"]) == 1


async def test_o_quiz_sai_mesmo_se_o_equilibrio_falhar(ia, banco):
    ia["respostas"] = [
        {"titulo": "Quiz", "questoes": [_do_modelo(i, True) for i in range(3)]},
        AiProviderError("fora do ar"),
    ]
    quiz = await quizzes.generate_quiz(quizzes.GenerateQuiz(tag_ids=["t1"], question_count=3), EU, banco)
    assert len(quiz["questions"]) == 3
