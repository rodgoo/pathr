"""As correções da revisão: cada teste prende um defeito que existiu.

1. "Rate limiter com corrida check-then-insert permite estourar tetos diários"
2. "Feature flag de candidaturas só esconde a aba; a API continua aberta a todos"
3. "Envio automático de candidatura pode mandar currículo para e-mail errado
   extraído do anúncio"
4. "Exceção genérica em atividades.gerar() pode mascarar erro real como corrida"

(O quinto — a assinatura de aparelho — mora em tests/test_sessoes_ativas.py,
junto do resto das sessões.)
"""

import asyncio
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.routers import candidaturas as rotas
from app.config import settings
from app.services import atividades, limites
from app.services import candidaturas as servico
from tests.fake_supabase import FakeSupabase

EU = {"id": "11111111-1111-1111-1111-111111111111", "email": "eu@exemplo.com", "name": "Ana"}


# --- 1. o teto do limitador vale mesmo com pedidos ao mesmo tempo -----------


def test_limitador_conta_o_proprio_pedido_antes_de_decidir():
    """Registrar DEPOIS de contar abria uma janela: pedidos simultâneos liam
    todos "0 usados" e passavam todos. Agora cada um já entra na conta que lê."""
    banco = FakeSupabase(pathr_rate_event=[])
    regra = limites.Regra("teste", 3, timedelta(hours=1), "chega")

    for _ in range(3):
        limites.consumir(banco, regra, "203.0.113.7")

    with pytest.raises(HTTPException) as erro:
        limites.consumir(banco, regra, "203.0.113.7")
    assert erro.value.status_code == 429


def test_limitador_nao_deixa_passar_mais_que_o_teto():
    banco = FakeSupabase(pathr_rate_event=[])
    regra = limites.Regra("paralelo", 5, timedelta(hours=1), "chega")

    passaram = 0
    for _ in range(20):
        try:
            limites.consumir(banco, regra, "203.0.113.9")
            passaram += 1
        except HTTPException:
            pass
    assert passaram == 5


def test_limitador_sem_chave_nao_limita():
    banco = FakeSupabase(pathr_rate_event=[])
    for _ in range(10):
        limites.consumir(banco, limites.CADASTRO_POR_IP, None)
    assert banco.linhas("pathr_rate_event") == []


# --- 2. o recurso desligado fecha a API, não só a aba ----------------------


def _banco_com_flag(estado: str):
    return FakeSupabase(pathr_feature_flag=[{"key": "candidaturas", "state": estado}], pathr_application=[])


def test_api_de_candidaturas_recusa_quem_nao_tem_o_recurso():
    """Esconder a aba é apresentação: sem isto, qualquer conta com sessão
    chamava /candidaturas direto e usava o recurso desligado."""
    with pytest.raises(HTTPException) as erro:
        rotas.recurso_ligado(EU, _banco_com_flag("ninguem"))
    # 404 e não 403: para quem não tem, o recurso não existe.
    assert erro.value.status_code == 404

    # "somente admin" fecha para conta comum e abre para o dono. Quem é dono
    # sai do e-mail nas configurações (services/moderacao.e_super_admin).
    with pytest.raises(HTTPException):
        rotas.recurso_ligado(EU, _banco_com_flag("admin"))

    # Ligado para todos: passa e devolve o próprio usuário.
    assert rotas.recurso_ligado(EU, _banco_com_flag("todos"))["id"] == EU["id"]


def test_recurso_em_somente_admin_abre_para_o_dono(monkeypatch):
    monkeypatch.setattr(settings, "super_admin_emails", ["dono@exemplo.com"])
    dono = {**EU, "email": "dono@exemplo.com"}
    assert rotas.recurso_ligado(dono, _banco_com_flag("admin"))["email"] == "dono@exemplo.com"
    # Mesmo sendo dono, "ninguém" fecha para todo mundo.
    with pytest.raises(HTTPException):
        rotas.recurso_ligado(dono, _banco_com_flag("ninguem"))


def test_todas_as_rotas_de_candidaturas_passam_pela_guarda():
    """A dependência está no router, e não em cada rota: rota nova nasce
    fechada, sem depender de alguém lembrar de protegê-la."""
    guardas = [d.dependency for d in rotas.router.dependencies]
    assert rotas.recurso_ligado in guardas


# --- 3. o envio automático só manda para endereço que é mesmo da empresa ----


@pytest.mark.parametrize(
    "email,empresa,url,confiavel",
    [
        ("vagas@empresaboa.com.br", "Empresa Boa", "https://empresaboa.com.br/vaga/1", True),
        # Nome de caixa de recrutamento, mas domínio sem nenhuma relação com o
        # anúncio ou a empresa: não confia. O nome da caixa é reforço, nunca
        # substituto da checagem de domínio (ver docstring de email_confiavel).
        ("rh@outra.com", "Empresa Boa", "https://empresaboa.com.br/vaga/1", False),
        ("contato@empresaboa.com.br", "Empresa Boa", "https://empresaboa.com.br/vaga/1", True),
        ("contato@empresaboa.com.br", "Empresa Boa", None, True),
        ("joao.silva@gmail.com", "Empresa Boa", "https://empresaboa.com.br/vaga/1", False),
        ("financeiro@fornecedor.com", "Empresa Boa", "https://empresaboa.com.br/vaga/1", False),
        ("", "Empresa Boa", None, False),
        (None, "Empresa Boa", None, False),
    ],
)
def test_email_confiavel_para_envio_sem_conferencia(email, empresa, url, confiavel):
    assert servico.email_confiavel(email, empresa, url) is confiavel


def test_envio_automatico_pula_email_que_nao_da_para_confiar(monkeypatch):
    """O endereço continua na fila (a pessoa confere e manda), mas não sai
    sozinho: currículo tem nome, telefone e histórico, e a caixa errada é
    vazamento sem volta."""
    enviados = []
    monkeypatch.setattr(servico.emails, "send_application", lambda **kw: enviados.append(kw) or True)
    monkeypatch.setattr(servico, "curriculo_em_anexo", lambda *_: ("cv.pdf", "YmFzZTY0"))

    banco = FakeSupabase(pathr_application=[], pathr_resume=[])
    linhas = [{
        "id": "a1", "title": "Dev Java", "company": "Empresa Boa", "score": 95,
        "to_email": "pessoa@gmail.com", "url": "https://empresaboa.com.br/vaga/1", "snippet": "Java",
    }]

    assert asyncio.run(servico.enviar_automaticamente(banco, EU, linhas)) == []
    assert enviados == []


# --- 4. só a corrida é tratada como corrida --------------------------------


class _ErroDoBanco(Exception):
    def __init__(self, mensagem, code=None):
        super().__init__(mensagem)
        self.code = code


def test_atividade_reconhece_a_corrida_pelo_codigo_do_banco():
    assert atividades._e_violacao_de_unicidade(_ErroDoBanco("duplicate key value", "23505"))
    assert atividades._e_violacao_de_unicidade(_ErroDoBanco("duplicate key value violates unique constraint"))
    assert atividades._e_violacao_de_unicidade(_ErroDoBanco("x", None)) is False
    assert atividades._e_violacao_de_unicidade(_ErroDoBanco("connection refused")) is False


def test_falha_de_verdade_sobe_em_vez_de_virar_corrida(monkeypatch):
    """Antes, QUALQUER erro na inserção devolvia a atividade aberta anterior: o
    defeito real sumia, e a pessoa via uma atividade velha como se fosse nova."""
    node = {"id": "22222222-2222-2222-2222-222222222222", "title": "Spring", "tag_ids": []}
    aberta = {"id": "ex1", "user_id": EU["id"], "node_id": str(node["id"]), "statement": "antiga", "answered_at": None}
    banco = FakeSupabase(pathr_activity_exercise=[aberta], pathr_explanation=[], pathr_tag=[])

    async def sem_ia(*_a, **_k):
        raise atividades.AiProviderError("provedor fora")

    monkeypatch.setattr(atividades, "generate_json", sem_ia)

    original = banco.table

    def tabela(nome):
        consulta = original(nome)
        if nome == "pathr_activity_exercise":
            def quebrado(*_a, **_k):
                raise _ErroDoBanco("permission denied for table pathr_activity_exercise", "42501")

            consulta.insert = quebrado
        return consulta

    monkeypatch.setattr(banco, "table", tabela)

    with pytest.raises(_ErroDoBanco):
        asyncio.run(atividades.gerar(banco, EU["id"], node))
