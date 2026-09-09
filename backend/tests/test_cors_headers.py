"""Os cabeçalhos que o navegador precisa enxergar.

O site e a API são hosts irmãos, mas origens distintas. Numa resposta
cross-origin o navegador só entrega ao JavaScript os cabeçalhos da lista
segura do CORS — todo `X-...` fica invisível a menos que o servidor o declare
em `Access-Control-Expose-Headers`.

Dois cabeçalhos deste app carregam decisão de tela, e não só informação:

- `X-Pathr-Mfa`: sem ele o login não sabe que deve pedir o código do
  autenticador, e mostra "informe o código" como se fosse erro de senha.
- `X-Pathr-Unverified`: sem ele a tela não distingue senha errada de e-mail
  não confirmado, e não tem como oferecer o reenvio do link.

Ambos ficaram invisíveis em produção até isto ser corrigido. O teste existe
para que não voltem a ficar.
"""

from fastapi.testclient import TestClient

import pathlib

from app.main import app

ORIGEM = "https://pathr.notter.com.br"


def _expostos(resposta) -> set[str]:
    bruto = resposta.headers.get("access-control-expose-headers", "")
    return {parte.strip().lower() for parte in bruto.split(",") if parte.strip()}


def test_expoe_os_cabecalhos_que_a_tela_le():
    with TestClient(app) as cliente:
        resposta = cliente.get("/health", headers={"Origin": ORIGEM})

    expostos = _expostos(resposta)
    assert "x-pathr-mfa" in expostos
    assert "x-pathr-unverified" in expostos


def test_a_producao_libera_a_origem_do_site():
    """Se a origem não bater, nada acima importa: o navegador descarta a
    resposta inteira antes de ela chegar ao código.

    A verificação é no fly.toml e não em `settings`, porque em
    desenvolvimento a origem é localhost — o valor que precisa estar certo é
    o que vai para produção.
    """
    fly = (pathlib.Path(__file__).resolve().parent.parent / "fly.toml").read_text(encoding="utf-8")
    linha = next(l for l in fly.splitlines() if l.strip().startswith("CORS_ORIGINS"))
    assert ORIGEM in linha
