"""Em que idioma o app está falando com esta pessoa, agora.

## Por que um cabeçalho, e não o `locale` do banco

A tela sabe o idioma antes de o servidor saber quem está do outro lado: quem
ainda não entrou também usa o app, e quem entrou pode ter acabado de trocar o
idioma nas Configurações. O front manda `X-Pathr-Idioma` em toda requisição
(frontend/src/api/client.ts), o middleware guarda aqui, e qualquer código —
inclusive fundo dentro de um serviço, longe da requisição — pergunta.

Sem cabeçalho (chamada do agendador, script), fica o português.

## Para que serve

Texto fixo é traduzido na tela (frontend/src/i18n). O que a IA ESCREVE não
pode ser: exercício, explicação, carta e correção nascem na hora. Então a
instrução de idioma entra no prompt (app/ai_providers.generate_json), e o
modelo já responde no idioma de quem vai ler.

Quem gera material do idioma ESTUDADO (o módulo de treino) pede exceção com
`traduzir_saida=False`: ali o conteúdo é em inglês de propósito, e mandar o
modelo escrever em alemão porque a interface está em alemão quebraria a aula.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

# Os mesmos cinco da tela (frontend/src/lib/i18n.tsx).
NOMES = {
    "pt": "português do Brasil",
    "en": "English",
    "es": "español",
    "fr": "français",
    "de": "Deutsch",
}
PADRAO = "pt"

idioma_da_requisicao: ContextVar[str] = ContextVar("idioma_da_requisicao", default=PADRAO)


def normalizar(bruto: Optional[str]) -> str:
    """ "pt-BR", "PT_br" e "pt" viram "pt". Desconhecido vira o padrão."""
    codigo = str(bruto or "").strip().lower().replace("_", "-").split("-")[0]
    return codigo if codigo in NOMES else PADRAO


def atual() -> str:
    return idioma_da_requisicao.get()


def nome(codigo: Optional[str] = None) -> str:
    """O nome do idioma como se diz nele mesmo — é o que vai no prompt."""
    return NOMES.get(normalizar(codigo or atual()), NOMES[PADRAO])


def instrucao_para_o_modelo(codigo: Optional[str] = None) -> str:
    """A linha que faz o modelo responder no idioma de quem vai ler.

    Vazia em português: é o idioma em que os prompts já estão escritos, e uma
    instrução redundante só ocuparia espaço no contexto.
    """
    escolhido = normalizar(codigo or atual())
    if escolhido == PADRAO:
        return ""
    return (
        f"\n\nIDIOMA DA RESPOSTA: escreva TUDO que a pessoa vai ler em {NOMES[escolhido]} "
        "— títulos, enunciados, explicações, alternativas e mensagens. Mantenha em inglês "
        "apenas os termos técnicos que não se traduzem (nomes de linguagens, bibliotecas, "
        "comandos e o código em si). As chaves do JSON continuam exatamente como pedidas."
    )
