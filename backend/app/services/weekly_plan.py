"""O checklist da semana: o que estudar agora, no tamanho do seu nível e do seu tempo.

## Por que ele sai dos dados, e não de uma chamada de IA

Cada item vem de algo que o app já sabe: o módulo que está na semana, o nível
medido nas tecnologias dele, os conceitos vencidos na revisão e as horas que a
pessoa tem. Gerar isso com um LLM seria mais lento, gastaria cota toda
segunda-feira e — o pior — produziria uma lista que ninguém consegue explicar.
Aqui cada item tem um motivo que dá para apontar.

## As regras, e o método por trás de cada uma

- **Revisão primeiro** (repetição espaçada). Conceito vencido é conceito no
  ponto de ser esquecido; revisá-lo antes do conteúdo novo é o que consolida.
- **A composição muda com o nível** do módulo. Quem está começando precisa de
  base antes de ser testado — quiz sem material vira chute. Quem já domina não
  ganha nada revendo o básico: o ganho está em explicar (Feynman) e aplicar.
- **Os assuntos se alternam** (intercalação). Os itens essenciais de cada
  módulo entram revezados — quiz de A, quiz de B, explicação de A — em vez de
  esgotar um módulo antes do outro. Alternar custa mais na hora e retém mais
  depois.
- **Cabe no tempo.** A lista para quando o orçamento da semana acaba. Uma lista
  maior que o tempo disponível é uma lista que ninguém termina, e não terminar
  toda semana ensina a ignorá-la.
- **O que dá para conferir se confere sozinho.** Quiz e explicação deixam
  rastro no banco, e o item correspondente é marcado quando o rastro aparece.
  O resto é marcado à mão.

A composição vale pela semana inteira: um plano que muda de forma a cada
abertura da tela não é plano. Ela é refeita na virada da semana e quando a
pessoa pede.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

# Minutos estimados por tipo de item. Estimativa, não cronômetro: servem para
# a lista caber no orçamento, e erram para o lado de sobrar tempo.
MINUTOS = {
    "material": 25,
    "quiz": 15,
    "feynman": 20,
    "pratica": 40,
    "desafio": 45,
}
_REVISAO_BASE = 10
_REVISAO_POR_CONCEITO = 2
_REVISAO_TETO = 30

PILARES = {
    "revisao": "Repetição espaçada",
    "material": "Estudo guiado",
    "quiz": "Recordação ativa",
    "feynman": "Feynman",
    "pratica": "Prática deliberada",
    "desafio": "Prática deliberada",
}

_DETALHES = {
    "revisao": (
        "Vem antes do conteúdo novo: revisar no ponto em que se está esquecendo é o "
        "que consolida. Os conceitos voltam reescritos no próximo quiz."
    ),
    "material": (
        "Um vídeo, artigo ou documentação da Biblioteca. Base antes de teste — sem "
        "ela, o quiz vira chute."
    ),
    "quiz": (
        "Responder sem consultar é o que fixa. Errar aqui é parte do método: o erro "
        "volta reescrito na próxima rodada."
    ),
    "feynman": (
        "Escreva como se explicasse para alguém que nunca viu o assunto. Onde o "
        "texto travar é onde o entendimento acaba."
    ),
    "pratica": (
        "Resolver a atividade do módulo do zero, sem IA. Reconhecer a solução é "
        "diferente de produzi-la."
    ),
    "desafio": (
        "Você já tem a base. O ganho agora está em aplicar num problema maior, não "
        "em revisar o que já sabe."
    ),
}

# Quantos módulos a semana carrega no máximo. Mais que isso e a intercalação
# vira dispersão: três assuntos alternados retêm; seis viram nenhum.
_MODULOS_POR_SEMANA = 3


class ItemVerificado(Exception):
    """O item foi confirmado por evidência e não se desmarca à mão."""


def inicio_da_semana(dia: date) -> date:
    """A segunda-feira da semana de `dia`. É a chave do checklist."""
    return dia - timedelta(days=dia.weekday())


def semana_do_plano(criado_em: date, hoje: date, horizonte: int) -> int:
    """Em que semana do plano estamos, contando a da criação como a 1.

    Conta por semana de calendário, e não por blocos de sete dias a partir da
    criação: um plano criado numa quinta tem a primeira semana curta, e a
    segunda começa na segunda-feira como a de todo mundo.
    """
    semanas = (inicio_da_semana(hoje) - inicio_da_semana(criado_em)).days // 7 + 1
    return max(1, min(semanas, max(1, horizonte)))


def faixa(proficiencia: float) -> str:
    """O nível do módulo, em três faixas que mudam a composição."""
    if proficiencia <= 1:
        return "iniciante"
    if proficiencia < 3:
        return "intermediario"
    return "avancado"


def modulos_da_semana(nodes: list[dict], semana: int) -> list[dict]:
    """Os módulos que a semana carrega: atrasados primeiro, depois os dela.

    Atrasado vem na frente porque é o que a pessoa já devia ter feito, e
    empurrá-lo para o fim da lista é deixá-lo atrasar de novo. Quando nenhum
    módulo cai na semana (plano adiantado, ou cronograma sem datas), a semana
    pega os próximos em aberto — um checklist vazio com o plano pela metade
    diria "nada a fazer" quando há.
    """
    abertos = sorted(
        (
            n
            for n in nodes
            if n.get("kind") != "phase" and n.get("status") not in ("done", "skipped")
        ),
        key=lambda n: n.get("order_index") or 0,
    )

    def fim(n: dict) -> int:
        return int(n.get("week_end") or n.get("week_start") or 0)

    atrasados = [n for n in abertos if 0 < fim(n) < semana]
    da_semana = [
        n for n in abertos if int(n.get("week_start") or 0) <= semana <= fim(n) and fim(n) > 0
    ]
    escolhidos: list[dict] = []
    for n in atrasados + da_semana:
        if n not in escolhidos:
            escolhidos.append(n)
    return (escolhidos or abertos)[:_MODULOS_POR_SEMANA]


def _item(tipo: str, titulo: str, node: Optional[dict], nivel: Optional[str], minutos: int) -> dict:
    return {
        "id": f"{tipo}:{node['id']}" if node else tipo,
        "tipo": tipo,
        "pilar": PILARES[tipo],
        "titulo": titulo,
        "detalhe": _DETALHES[tipo],
        "minutos": minutos,
        "node_id": str(node["id"]) if node else None,
        "modulo": node.get("title") if node else None,
        "nivel": nivel,
        "feito": False,
        "verificado": False,
        "feito_em": None,
    }


def _itens_do_modulo(node: dict, banda: str) -> tuple[list[dict], list[dict]]:
    """(essenciais, extras) do módulo, conforme a faixa de nível."""
    titulo = node.get("title") or "módulo"

    def item(tipo: str, texto: str) -> dict:
        return _item(tipo, texto, node, banda, MINUTOS[tipo])

    if banda == "iniciante":
        return (
            [item("material", f"Estudar o material de {titulo}"), item("quiz", f"Quiz de {titulo}")],
            [item("feynman", f"Explicar {titulo} com suas palavras")],
        )
    if banda == "intermediario":
        return (
            [item("quiz", f"Quiz de {titulo}"), item("feynman", f"Explicar {titulo} com suas palavras")],
            [item("pratica", f"Atividade prática de {titulo}")],
        )
    # Avançado: sem material e sem quiz básico. Rever o que já se domina é o
    # jeito mais confortável de não progredir.
    return (
        [
            item("feynman", f"Explicar {titulo} com suas palavras"),
            item("desafio", f"Desafio aplicado de {titulo}"),
        ],
        [],
    )


def _revezar(grupos: list[list[dict]]) -> list[dict]:
    """Um item de cada grupo por vez: A1, B1, C1, A2, B2... É a intercalação."""
    saida: list[dict] = []
    for posicao in range(max((len(g) for g in grupos), default=0)):
        for grupo in grupos:
            if posicao < len(grupo):
                saida.append(grupo[posicao])
    return saida


def montar(
    modulos: list[dict],
    nivel_por_tag: dict[str, int],
    pendentes: int,
    minutos_disponiveis: int,
) -> list[dict]:
    """A lista da semana, em ordem, cortada no orçamento."""
    fila: list[dict] = []
    if pendentes > 0:
        texto = (
            "Revisar 1 conceito pendente"
            if pendentes == 1
            else f"Revisar {pendentes} conceitos pendentes"
        )
        minutos = min(_REVISAO_TETO, max(_REVISAO_BASE, pendentes * _REVISAO_POR_CONCEITO))
        fila.append(_item("revisao", texto, None, None, minutos))

    essenciais: list[list[dict]] = []
    extras: list[list[dict]] = []
    for modulo in modulos:
        tags = [str(t) for t in (modulo.get("tag_ids") or [])]
        media = sum(nivel_por_tag.get(t, 0) for t in tags) / len(tags) if tags else 0
        e, x = _itens_do_modulo(modulo, faixa(media))
        essenciais.append(e)
        extras.append(x)

    fila += _revezar(essenciais) + _revezar(extras)

    # O corte respeita a ordem, que já é a de prioridade: revisão, depois o
    # essencial revezado, depois o extra. Os dois primeiros ficam sempre —
    # uma semana apertada ainda precisa de um começo.
    orcamento = max(30, minutos_disponiveis)
    escolhidos: list[dict] = []
    usado = 0
    for posicao, item in enumerate(fila):
        if posicao < 2 or usado + item["minutos"] <= orcamento:
            escolhidos.append(item)
            usado += item["minutos"]
    return escolhidos


def aplicar_evidencias(
    itens: list[dict],
    quiz_por_node: set[str],
    feynman_por_node: set[str],
    pendentes_agora: int,
    agora: str,
) -> bool:
    """Marca o que o banco comprova. Devolve se algo mudou.

    Só quiz, explicação e revisão têm rastro verificável. Material, prática e
    desafio ficam para a pessoa marcar: inventar evidência para eles seria
    marcar como feito o que ninguém sabe se foi.
    """
    mudou = False
    for item in itens:
        if item.get("verificado"):
            continue
        tipo, node = item.get("tipo"), item.get("node_id")
        comprovado = (
            (tipo == "quiz" and node in quiz_por_node)
            or (tipo == "feynman" and node in feynman_por_node)
            or (tipo == "revisao" and pendentes_agora == 0)
        )
        if comprovado:
            item["feito"] = True
            item["verificado"] = True
            item["feito_em"] = item.get("feito_em") or agora
            mudou = True
    return mudou


def marcar(itens: list[dict], item_id: str, feito: bool, agora: str) -> dict:
    """Marca ou desmarca à mão. Levanta KeyError ou ItemVerificado."""
    for item in itens:
        if item.get("id") == item_id:
            if item.get("verificado") and not feito:
                raise ItemVerificado(item_id)
            item["feito"] = feito
            item["feito_em"] = agora if feito else None
            return item
    raise KeyError(item_id)


def preservar(novos: list[dict], antigos: list[dict]) -> list[dict]:
    """Ao refazer a lista, o que já estava feito continua feito.

    Casa pelo id, que é estável (`quiz:<módulo>`). Sem isto, pedir para
    atualizar a semana apagaria as marcações de quem já tinha avançado nela.
    """
    por_id = {a.get("id"): a for a in antigos}
    for novo in novos:
        antigo = por_id.get(novo["id"])
        if antigo and antigo.get("feito"):
            novo["feito"] = True
            novo["verificado"] = bool(antigo.get("verificado"))
            novo["feito_em"] = antigo.get("feito_em")
    return novos


def resumo(itens: list[dict]) -> dict[str, Any]:
    feitos = [i for i in itens if i.get("feito")]
    return {
        "total": len(itens),
        "feitos": len(feitos),
        "minutos": sum(int(i.get("minutos") or 0) for i in itens),
        "minutos_feitos": sum(int(i.get("minutos") or 0) for i in feitos),
    }
