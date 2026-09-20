"""A API fora dos buscadores.

Veio de um erro real no Search Console: "Não encontrado (404)", uma página
afetada — `https://api.pathr.notter.com.br/`. A propriedade lá está configurada
como DOMÍNIO, então o Google varre todos os subdomínios; pediu a raiz da API,
recebeu o 404 correto (ela não tem página) e registrou como erro.

O erro não machuca o ranqueamento do site, mas fica permanente no relatório —
e erro que ninguém pode corrigir é erro que se aprende a ignorar, junto com o
próximo, que talvez importe.
"""

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_a_api_pede_para_nao_ser_rastreada():
    resposta = cliente.get("/robots.txt")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in resposta.text
    assert "Disallow: /" in resposta.text


def test_toda_resposta_diz_noindex():
    """`robots.txt` evita a visita; `noindex` tira do índice o que já foi
    visitado. São coisas diferentes, e por isso existem as duas."""
    for caminho in ("/health", "/robots.txt", "/auth/me"):
        assert cliente.get(caminho).headers.get("x-robots-tag") == "noindex, nofollow"


def test_a_raiz_continua_404():
    """Não se inventa uma página na raiz para calar o relatório: a API não tem
    página, e responder 200 com qualquer coisa seria mentir para quem pergunta.
    Quem faz o erro sumir é o robots.txt."""
    assert cliente.get("/").status_code == 404
