"""O catalogo de idiomas e a conversao entre as reguas.

Offline. O que se testa aqui e a promessa central do modulo: o app mede numa
escala so (CEFR) e apresenta na prova que a pessoa escolheu. Se a conversao
errar, a meta "7.0 no IELTS" vira um alvo que o nivelamento nunca alcanca -- ou
que ele da por alcancado cedo demais, que e pior.
"""

import pytest

from app.services import languages as lang


def test_catalogo_tem_os_idiomas_pedidos():
    codigos = {idioma.codigo for idioma in lang.IDIOMAS}
    assert {"en", "es", "fr", "de", "it", "ja", "zh", "ko", "pt"} <= codigos


def test_todo_idioma_oferece_cefr():
    """Quem nao presta prova nenhuma precisa de uma regua. O CEFR e o piso
    comum, e e a escala em que o app realmente mede."""
    for idioma in lang.IDIOMAS:
        assert any(exame.id == "cefr" for exame in idioma.exames), idioma.codigo


def test_ingles_tem_as_provas_que_o_mercado_pede():
    ids = {exame.id for exame in lang.idioma("en").exames}
    assert {"ielts", "toefl_ibt", "toeic", "cambridge"} <= ids


@pytest.mark.parametrize(
    "idioma,exame,rotulo,cefr",
    [
        ("en", "ielts", "7.0", "C1"),
        ("en", "ielts", "5.5", "B2"),
        ("en", "toefl_ibt", "95", "C1"),
        ("en", "toefl_ibt", "42", "B1"),
        ("en", "cambridge", "FCE", "B2"),
        ("ja", "jlpt", "N2", "B2"),
        ("zh", "hsk", "HSK 5", "B2"),
        ("ko", "topik", "TOPIK 6", "C2"),
        ("de", "testdaf", "TDN 5", "C1"),
        ("pt", "celpe_bras", "Avançado", "C1"),
    ],
)
def test_meta_na_prova_vira_meta_em_cefr(idioma, exame, rotulo, cefr):
    assert lang.cefr_da_meta(idioma, exame, rotulo) == cefr


def test_nivel_medido_volta_para_a_regua_escolhida():
    """O caminho inverso: a tela mostra o que a pessoa entende. Quem estuda
    para o IELTS quer ler 7.0, nao C1."""
    assert lang.meta_no_exame("en", "ielts", "C1") == "7.0"
    assert lang.meta_no_exame("ja", "jlpt", "B2") == "N2"


def test_conversao_de_ida_e_volta_nao_promete_mais_do_que_mediu():
    """C1 no IELTS cobre 7.0 e 8.0. Voltar tem que dar 7.0 -- anunciar 8.0
    seria dar por certo o que nao foi medido."""
    assert lang.meta_no_exame("en", "ielts", "C1") == "7.0"


def test_faixa_desconhecida_nao_inventa_equivalencia():
    assert lang.cefr_da_meta("en", "ielts", "12.0") is None
    assert lang.cefr_da_meta("en", "exame-que-nao-existe", "7.0") is None
    assert lang.cefr_da_meta("xx", "ielts", "7.0") is None


def test_idioma_fora_do_catalogo_e_recusado():
    assert lang.existe("en") is True
    assert lang.existe("EN") is True
    assert lang.existe("klingon") is False
    assert lang.existe("") is False


def test_toda_faixa_aponta_para_um_nivel_valido():
    """Um CEFR digitado errado numa faixa nova quebraria a meta em silencio:
    a conversao devolveria algo que o nivelamento nao sabe medir."""
    for idioma in lang.IDIOMAS:
        for exame in idioma.exames:
            assert exame.faixas, f"{idioma.codigo}/{exame.id} sem faixas"
            for faixa in exame.faixas:
                assert faixa.cefr in lang.CEFR, f"{idioma.codigo}/{exame.id}: {faixa.cefr}"


def test_catalogo_json_tem_o_formato_que_a_tela_espera():
    dados = lang.catalogo()
    primeiro = dados[0]
    assert set(primeiro) == {"codigo", "nome", "nativo", "exames"}
    exame = primeiro["exames"][0]
    assert set(exame) == {"id", "nome", "descricao", "faixas"}
    assert set(exame["faixas"][0]) == {"rotulo", "cefr", "nota"}


# ---------------------------------------------------------------------------
# Itens do nivelamento: o que o modelo devolve nem sempre da para responder.
#
# O caso real que trouxe estes testes: um item de listening chegou com o
# enunciado "Based on the audio, who is assigned to push the new feature?" e,
# no contexto, so a descricao da cena ("Daily stand-up meeting on Zoom"). O
# app nao toca audio e a cena nao diz quem ficou com a tarefa -- a pergunta
# nao tinha resposta, e mesmo assim contava para o nivel medido.
# ---------------------------------------------------------------------------

from app.routers import languages as router  # noqa: E402

TRANSCRICAO = "Ana: I'll push the feature to staging after lunch.\nMarc: Great, I'll review it."


def _item(**campos):
    base = {
        "habilidade": "grammar",
        "banda": "B1",
        "contexto": "",
        "enunciado": "Which sentence sounds most natural in a code review?",
        "alternativas": ["a", "b", "c", "d"],
        "correta": 1,
        "explicacao": "porque sim",
    }
    return {**base, **campos}


def _linhas(*itens):
    return router._linhas_de_itens(list(itens), "assess-1", "user-1", "B1", 0)


def test_item_de_listening_sem_transcricao_nao_chega_a_tela():
    """Sem o dialogo escrito, listening nao tem do que ser respondido."""
    linhas = _linhas(
        _item(
            habilidade="listening",
            contexto="Daily stand-up meeting on Zoom. The team lead announces the next steps.",
            enunciado="Based on the audio, who is assigned to push the new feature to staging?",
        )
    )
    assert linhas == []


def test_item_de_listening_com_transcricao_passa():
    linhas = _linhas(
        _item(
            habilidade="listening",
            contexto=TRANSCRICAO,
            enunciado="Who is going to push the feature to staging?",
        )
    )
    assert len(linhas) == 1
    assert linhas[0]["skill"] == "listening"
    assert linhas[0]["context"] == TRANSCRICAO


def test_enunciado_que_manda_ouvir_cai_em_qualquer_habilidade():
    """O app nao reproduz som. Rotular de vocabulary nao muda isso."""
    linhas = _linhas(
        _item(habilidade="vocabulary", enunciado="Listen to the recording and pick the answer.")
    )
    assert linhas == []


def test_item_normal_continua_passando():
    linhas = _linhas(_item(), _item(habilidade="business"))
    assert [linha["skill"] for linha in linhas] == ["grammar", "business"]


def test_habilidade_desconhecida_vira_grammar():
    linhas = _linhas(_item(habilidade="pronunciation"))
    assert linhas[0]["skill"] == "grammar"


def test_item_descartado_nao_abre_buraco_na_ordem():
    """`order_index` conta linha aceita, nao item recebido: com buraco, a
    segunda tentativa reusaria uma posicao ja ocupada."""
    linhas = _linhas(
        _item(habilidade="listening", contexto="Daily stand-up on Zoom."),
        _item(),
        _item(habilidade="business"),
    )
    assert [linha["order_index"] for linha in linhas] == [0, 1]


def test_item_malformado_continua_sendo_descartado():
    assert _linhas(_item(alternativas=["a", "b"])) == []
    assert _linhas(_item(correta=9)) == []
    assert _linhas(_item(enunciado="   ")) == []


# ---------------------------------------------------------------------------
# O nivelamento como fluxo: responder, retomar, e o que fazer com o erro.
#
# Os casos vieram de um relato de uso. A pessoa saiu da tela no meio do teste,
# voltou, respondeu -- e a tela congelou sem dizer se acertou. O clique
# seguinte respondia "item ja respondido" e nada avancava: o item ficava
# gravado no servidor e sem gabarito no cliente, sem saida. Ao dar F5, o teste
# sumia por completo, porque o id dele so existia na memoria da tela.
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

from tests.fake_supabase import FakeSupabase  # noqa: E402

USUARIO = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@b.co"}


def _banco(itens_pendentes: int = 3, **extra) -> FakeSupabase:
    tentativa = {
        "id": "aaaa",
        "user_id": USUARIO["id"],
        "language": "en",
        "kind": "placement",
        "status": "in_progress",
        "item_count": 20,
        "answered_count": 1,
        "correct_count": 1,
        "started_at": "2026-01-01T00:00:00Z",
        **extra,
    }
    itens = [
        {
            "id": "item-0",
            "assessment_id": "aaaa",
            "user_id": USUARIO["id"],
            "skill": "grammar",
            "cefr_band": "B1",
            "prompt": "Which sentence is correct?",
            "options": ["a", "b", "c", "d"],
            "correct": {"index": 2},
            "feedback": "porque sim",
            "is_correct": True,
            "user_answer": "2",
            "order_index": 0,
        }
    ]
    for indice in range(itens_pendentes):
        itens.append(
            {
                "id": f"pendente-{indice}",
                "assessment_id": "aaaa",
                "user_id": USUARIO["id"],
                "skill": "grammar",
                "cefr_band": "B1",
                "prompt": f"Pergunta {indice}?",
                "options": ["a", "b", "c", "d"],
                "correct": {"index": 1},
                "feedback": "explicacao",
                "is_correct": None,
                "order_index": indice + 1,
            }
        )
    return FakeSupabase(
        pathr_english_assessment=[tentativa],
        pathr_english_item=itens,
        pathr_review_item=[],
    )


def _responde(duplo, item_id: str, escolha: int):
    return asyncio.run(
        router.answer_assessment(
            "aaaa", router.AnswerItem(item_id=item_id, answer=escolha), USUARIO, duplo
        )
    )


def test_item_ja_respondido_devolve_o_gabarito_em_vez_de_travar():
    """Era 409 sem gabarito: a tela ficava sem correcao e sem 'Proxima'."""
    duplo = _banco()

    resultado = _responde(duplo, "item-0", 0)

    assert resultado["correct_index"] == 2
    assert resultado["is_correct"] is True
    assert resultado["explanation"] == "porque sim"
    assert resultado["finished"] is False


def test_resposta_repetida_nao_conta_de_novo():
    """Reler o desfecho nao pode mexer no placar nem na resposta gravada."""
    duplo = _banco()

    _responde(duplo, "item-0", 0)

    tentativa = duplo.linhas("pathr_english_assessment")[0]
    assert tentativa["answered_count"] == 1
    assert tentativa["correct_count"] == 1
    # A escolha original continua sendo a valida.
    item = next(l for l in duplo.linhas("pathr_english_item") if l["id"] == "item-0")
    assert item["user_answer"] == "2"
    assert item["is_correct"] is True


def test_erro_vira_ponto_de_melhora():
    """O acerto virava nota e o erro nao virava nada -- justo a lacuna que o
    teste acabou de provar."""
    duplo = _banco()

    _responde(duplo, "pendente-0", 3)  # a correta e 1

    melhoras = duplo.linhas("pathr_review_item")
    assert len(melhoras) == 1
    assert melhoras[0]["kind"] == "language"
    assert melhoras[0]["front"] == "Pergunta 0?"
    # O verso traz a resposta certa e a explicacao.
    assert "b" in melhoras[0]["back"] and "explicacao" in melhoras[0]["back"]


def test_acerto_nao_vira_ponto_de_melhora():
    duplo = _banco()

    _responde(duplo, "pendente-0", 1)

    assert duplo.linhas("pathr_review_item") == []


def test_mesmo_conceito_nao_entra_duas_vezes_na_fila():
    """Refazer o nivelamento e errar a mesma ideia nao pode criar duas linhas:
    a pessoa reveria a mesma lacuna em paralelo."""
    duplo = _banco()
    duplo.tabelas["pathr_review_item"].append(
        {
            "id": "ja-existe",
            "user_id": USUARIO["id"],
            "kind": "language",
            "front": "Pergunta 0?",
            "back": "b",
        }
    )

    _responde(duplo, "pendente-0", 3)

    assert len(duplo.linhas("pathr_review_item")) == 1


def test_nivelamento_aberto_e_encontravel_sem_o_id():
    """E o que permite voltar depois de um F5: o id nao existe mais na tela,
    mas o teste continua no banco."""
    duplo = _banco()

    aberto = router.active_assessment("en", USUARIO, duplo)

    assert aberto is not None
    assert str(aberto["id"]) == "aaaa"
    assert aberto["answered_count"] == 1
    assert aberto["item_count"] == 20
    # Vem com os itens ainda nao respondidos, para retomar direto.
    assert [item["id"] for item in aberto["items"]] == ["pendente-0", "pendente-1", "pendente-2"]


def test_sem_nivelamento_aberto_devolve_nulo():
    duplo = _banco(status="done")

    assert router.active_assessment("en", USUARIO, duplo) is None


def test_nivelamento_encerrado_nao_e_oferecido_como_retomada():
    duplo = _banco(status="abandoned")

    assert router.active_assessment("en", USUARIO, duplo) is None


def test_pontos_de_melhora_contam_so_os_vencidos():
    """Ponto agendado para semana que vem nao e divida de hoje."""
    duplo = FakeSupabase(
        pathr_review_item=[
            {
                "id": "1",
                "user_id": USUARIO["id"],
                "kind": "language",
                "front": "a",
                "back": "b",
                "due_at": "2020-01-01T00:00:00+00:00",
            },
            {
                "id": "2",
                "user_id": USUARIO["id"],
                "kind": "language",
                "front": "c",
                "back": "d",
                "due_at": "2999-01-01T00:00:00+00:00",
            },
        ]
    )

    resposta = router.improvements(USUARIO, duplo)

    assert len(resposta["items"]) == 2
    assert resposta["due_count"] == 1


def test_comecar_um_novo_encerra_o_anterior(monkeypatch):
    """Sem encerrar, o antigo ficaria 'in_progress' para sempre e a tela
    ofereceria a retomada de um teste que a pessoa decidiu refazer."""
    duplo = _banco()

    async def _nada(*_args, **_kwargs):
        return None

    monkeypatch.setattr(router, "_generate_items", _nada)

    asyncio.run(router.start_assessment("en", USUARIO, duplo))

    tentativas = duplo.linhas("pathr_english_assessment")
    antiga = next(l for l in tentativas if str(l["id"]) == "aaaa")
    assert antiga["status"] == "abandoned"
    # E o novo e o unico aberto.
    abertas = [l for l in tentativas if l["status"] == "in_progress"]
    assert len(abertas) == 1
    assert str(abertas[0]["id"]) != "aaaa"
