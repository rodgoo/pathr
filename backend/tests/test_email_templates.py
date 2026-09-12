"""Os cinco e-mails: o que quebra sem aparecer em lugar nenhum.

Defeito de e-mail não derruba teste nem log — ele chega torto na caixa de
entrada de alguém, e ninguém conta. O que está coberto aqui é o que tem
consequência: texto de quem usa entrando cru no HTML, o assunto perdendo o
número que o torna útil, e as defesas do desenho (marca legível com imagem
bloqueada, fundo pintado, botão que sobrevive ao Outlook).

A aparência em si não dá para testar em texto; ela foi conferida renderizando
os cinco, com imagem ligada e desligada.
"""

import pytest

from app.services import email as emails

SITE = "https://pathr.notter.com.br"


@pytest.fixture(autouse=True)
def _site(monkeypatch):
    monkeypatch.setattr(emails.settings, "frontend_url", SITE)


@pytest.fixture
def enviados(monkeypatch):
    """Captura (assunto, html) em vez de falar com a Brevo."""
    caixa: list[tuple[str, str]] = []
    monkeypatch.setattr(
        emails, "_send", lambda to, nome, assunto, html: caixa.append((assunto, html)) or True
    )
    return caixa


def _todos(caixa) -> list[str]:
    return [html for _, html in caixa]


# --- o que vem de quem usa não pode virar HTML ------------------------------


def test_titulo_de_item_e_escapado(enviados):
    """O título vem do plano da pessoa, que vem do roadmap, que vem da IA.

    Sem escape, um item com `<` fecharia a tabela no meio e desmontaria a
    mensagem — e um com `<a>` viraria link de verdade dentro do e-mail.
    """
    emails.send_daily_plan("a@b.c", "Ana", ["Ler <script>alerta()</script> & cia"], 30)
    _, html = enviados[0]
    assert "<script>" not in html
    assert "&lt;script&gt;alerta()&lt;/script&gt; &amp; cia" in html


def test_nome_e_escapado(enviados):
    emails.send_daily_plan("a@b.c", "<b>Ana</b> Paula", ["Ler algo"], 10)
    _, html = enviados[0]
    assert "<b>Ana</b>" not in html
    assert "Bom dia, &lt;b&gt;Ana&lt;/b&gt;." in html


def test_so_o_primeiro_nome(enviados):
    """"Bom dia, Ana Paula Ribeiro" soa com um formulário falando."""
    emails.send_daily_plan("a@b.c", "Ana Paula Ribeiro", ["Ler algo"], 10)
    assert "Bom dia, Ana." in enviados[0][1]


def test_sem_nome_nao_deixa_virgula_solta(enviados):
    emails.send_daily_plan("a@b.c", "", ["Ler algo"], 10)
    assert "Bom dia." in enviados[0][1]
    assert "Bom dia, ." not in enviados[0][1]


# --- o assunto precisa dizer o que tem dentro -------------------------------


def test_assunto_do_plano_traz_quantidade_e_tempo(enviados):
    """"Novidades do PathR" ensina a ignorar. O número decide sem abrir."""
    emails.send_daily_plan("a@b.c", "Ana", ["um", "dois", "três"], 45)
    assert enviados[0][0] == "Seu plano de hoje: 3 itens, 45 min"


def test_assunto_no_singular_quando_falta_um(enviados):
    emails.send_daily_plan("a@b.c", "Ana", ["um"], 15)
    assert enviados[0][0] == "Seu plano de hoje: 1 item, 15 min"


def test_assunto_do_resumo_traz_os_numeros(enviados):
    emails.send_weekly_summary("a@b.c", "Ana", 6, 8, 192, 12)
    assert enviados[0][0] == "Sua semana: 6 de 8 itens e 3,2 h de estudo"


def test_hora_usa_virgula_e_nao_ponto(enviados):
    """Ponto, em português, lê como separador de milhar."""
    emails.send_weekly_summary("a@b.c", "Ana", 1, 4, 90, 0)
    assert "1,5 h" in enviados[0][0]


def test_assunto_da_sequencia_concorda_no_singular(enviados):
    emails.send_streak_at_risk("a@b.c", "Ana", 1)
    assert enviados[0][0] == "1 dia seguidos — não pare hoje".replace(" seguidos", " seguido")


# --- as defesas do desenho --------------------------------------------------


def test_marca_aparece_como_texto_em_todos(enviados):
    """Imagem bloqueada é o padrão em boa parte dos clientes. Se a identidade
    morasse só no logotipo, o topo ficaria vazio."""
    emails.send_verification_email("a@b.c", "Ana", "t")
    emails.send_password_reset("a@b.c", "Ana", "t")
    emails.send_daily_plan("a@b.c", "Ana", ["x"], 10)
    emails.send_weekly_summary("a@b.c", "Ana", 1, 2, 60, 3)
    emails.send_streak_at_risk("a@b.c", "Ana", 3)
    assert len(enviados) == 5
    for html in _todos(enviados):
        assert ">PathR</span>" in html
        assert f'src="{SITE}/logo-email.png"' in html
        # Decorativo: o nome está escrito ao lado. Com alt="PathR" o leitor de
        # tela anunciaria duas vezes, e com imagem bloqueada o texto
        # alternativo sairia preto sobre o painel escuro.
        assert 'alt=""' in html


def test_logotipo_e_png_e_nao_svg(enviados):
    """Gmail e Outlook descartam SVG."""
    emails.send_daily_plan("a@b.c", "Ana", ["x"], 10)
    assert ".svg" not in enviados[0][1]


def test_todos_tem_linha_de_previsualizacao(enviados):
    """Sem ela o cliente puxa o primeiro texto visível — "PathR" — repetindo o
    remetente e gastando a única linha de contexto antes de abrir."""
    emails.send_verification_email("a@b.c", "Ana", "t")
    emails.send_weekly_summary("a@b.c", "Ana", 6, 8, 192, 0)
    for html in _todos(enviados):
        assert "display:none;max-height:0" in html
        assert html.index("display:none;max-height:0") < html.index(">PathR</span>")


def test_fundo_escuro_e_pintado_nas_tabelas(enviados):
    """Cliente que ignora o CSS do corpo põe a mensagem sobre branco; sem
    bgcolor atrás dele, o texto claro some."""
    emails.send_daily_plan("a@b.c", "Ana", ["x"], 10)
    html = enviados[0][1]
    assert f'bgcolor="{emails._FUNDO}"' in html
    assert f'bgcolor="{emails._PAINEL}"' in html


def test_botao_e_tabela_e_nao_link_com_padding(enviados):
    """Outlook ignora padding em <a> e o botão viraria texto sublinhado."""
    emails.send_daily_plan("a@b.c", "Ana", ["x"], 10)
    assert f'<td align="center" bgcolor="{emails._ROXO}"' in enviados[0][1]


# --- o que cada tipo promete ------------------------------------------------


def test_link_de_confirmacao_leva_o_token_e_aparece_escrito(enviados):
    emails.send_verification_email("a@b.c", "Ana", "tok/com+sinais")
    html = enviados[0][1]
    # Escapado na URL: um "+" cru viraria espaço do outro lado.
    assert f"{SITE}/confirmar-email?token=tok%2Fcom%2Bsinais" in html
    # E repetido em texto, para quem tem o botão bloqueado.
    assert html.count("confirmar-email?token=") == 2


def test_senha_avisa_quem_nao_pediu(enviados):
    emails.send_password_reset("a@b.c", "Ana", "t")
    assert "Se não foi você que pediu" in enviados[0][1]


def test_avisos_do_plano_dizem_onde_desligar(enviados):
    """E os da conta NÃO dizem: sem eles não se entra na conta, e oferecer
    "ajuste seus avisos" ensinaria a desligar o que é preciso receber."""
    emails.send_daily_plan("a@b.c", "Ana", ["x"], 10)
    emails.send_weekly_summary("a@b.c", "Ana", 1, 2, 60, 0)
    emails.send_streak_at_risk("a@b.c", "Ana", 2)
    for html in _todos(enviados):
        assert "Avisos e privacidade" in html

    enviados.clear()
    emails.send_verification_email("a@b.c", "Ana", "t")
    emails.send_password_reset("a@b.c", "Ana", "t")
    for html in _todos(enviados):
        assert "Avisos e privacidade" not in html


def test_lista_longa_vira_resumo_em_vez_de_rolagem(enviados):
    emails.send_daily_plan("a@b.c", "Ana", [f"item {n}" for n in range(1, 10)], 90)
    html = enviados[0][1]
    assert "item 6" in html and "item 7" not in html
    assert "e mais 3 itens" in html


def test_resumo_muda_o_recado_conforme_a_semana(enviados):
    emails.send_weekly_summary("a@b.c", "Ana", 8, 8, 240, 5)
    assert "Semana fechada por inteiro" in enviados[0][1]

    enviados.clear()
    emails.send_weekly_summary("a@b.c", "Ana", 0, 8, 0, 0)
    assert "recomeçar sem dívida" in enviados[0][1]


def test_resumo_sem_sequencia_nao_mostra_a_coluna(enviados):
    """Zero dias seguidos num placar de destaque é um zero em destaque."""
    emails.send_weekly_summary("a@b.c", "Ana", 3, 8, 120, 0)
    assert "dias seguidos" not in enviados[0][1]
