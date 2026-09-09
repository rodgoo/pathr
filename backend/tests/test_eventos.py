"""O canal que avisa as telas abertas de que algo mudou.

Estes testes cobrem o que não se vê quando funciona e é caro quando falha: o
aviso chegar a quem deve, NÃO chegar a quem não deve, e uma conexão lenta não
virar memória presa.

Nada aqui toca banco. A camada de `LISTEN/NOTIFY`, que leva o aviso a outras
máquinas, precisa de um Postgres de verdade e fica fora da suíte de propósito
— ela é degradação graciosa por desenho: sem ela o app continua avisando as
telas desta máquina, e as demais se corrigem ao voltar ao foco.
"""

import asyncio

import pytest

from app.services import eventos


@pytest.fixture(autouse=True)
def sem_notify(monkeypatch):
    """Silencia a parte que fala com o Postgres."""

    async def nada(*_args, **_kwargs):
        return None

    monkeypatch.setattr(eventos, "_notificar_outras_maquinas", nada)
    yield
    eventos._ouvintes.clear()


@pytest.mark.asyncio
async def test_aviso_chega_a_quem_esta_ouvindo():
    fila = eventos.inscrever("user-1")

    await eventos.publicar("user-1", "/roadmap/nodes/n-1", origem="aba-a")

    assert fila.get_nowait() == {"rota": "/roadmap/nodes/n-1", "origem": "aba-a"}


@pytest.mark.asyncio
async def test_aviso_nao_vaza_para_outra_conta():
    minha = eventos.inscrever("user-1")
    alheia = eventos.inscrever("user-2")

    await eventos.publicar("user-1", "/profile", origem="")

    assert minha.qsize() == 1
    # O canal é por usuário. Um aviso cruzado faria a tela de outra pessoa
    # reconsultar — e, pior, revelaria o ritmo de uso de quem não deveria.
    assert alheia.qsize() == 0


@pytest.mark.asyncio
async def test_todas_as_telas_da_mesma_conta_recebem():
    celular = eventos.inscrever("user-1")
    notebook = eventos.inscrever("user-1")

    await eventos.publicar("user-1", "/library/r-1/progress", origem="celular")

    # É o ponto inteiro da funcionalidade: dois aparelhos, um aviso cada.
    assert celular.qsize() == 1
    assert notebook.qsize() == 1


@pytest.mark.asyncio
async def test_fila_cheia_descarta_o_mais_velho():
    fila = eventos.inscrever("user-1")

    for i in range(eventos.LIMITE_DA_FILA + 3):
        await eventos.publicar("user-1", f"/rota/{i}", origem="")

    # Um aviso é um empurrão para reconsultar: dez empilhados valem o mesmo
    # que um. O que não pode é a fila crescer sem limite numa conexão parada.
    assert fila.qsize() == eventos.LIMITE_DA_FILA
    # E o que sobrou é o RECENTE — é ele que descreve o estado atual.
    ultimos = [fila.get_nowait()["rota"] for _ in range(eventos.LIMITE_DA_FILA)]
    assert ultimos[-1] == f"/rota/{eventos.LIMITE_DA_FILA + 2}"


@pytest.mark.asyncio
async def test_cancelar_solta_a_memoria():
    fila = eventos.inscrever("user-1")
    assert eventos.conexoes_abertas("user-1") == 1

    eventos.cancelar("user-1", fila)

    # Sem isto, cada aba que alguém abre e fecha deixaria uma fila para sempre
    # no dicionário — um vazamento que só aparece depois de semanas no ar.
    assert eventos.conexoes_abertas("user-1") == 0
    assert "user-1" not in eventos._ouvintes


@pytest.mark.asyncio
async def test_publicar_sem_ninguem_ouvindo_nao_falha():
    # Ninguém com aquela conta está com o app aberto. É o caso comum, e não
    # pode custar uma exceção no meio de uma escrita bem-sucedida.
    await eventos.publicar("user-fantasma", "/profile", origem="")


@pytest.mark.asyncio
async def test_aviso_espera_ate_chegar():
    """A fila é o que o endpoint SSE aguarda — ela precisa bloquear, não
    girar em vazio consumindo CPU enquanto nada acontece."""
    fila = eventos.inscrever("user-1")

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(fila.get(), timeout=0.05)

    await eventos.publicar("user-1", "/tags/mine", origem="")
    assert (await asyncio.wait_for(fila.get(), timeout=1))["rota"] == "/tags/mine"
