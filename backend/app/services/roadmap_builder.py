"""Geração do roadmap por IA.

A entrada é o retrato do usuário — o que ele já sabe (com nível), onde quer
chegar, quantas horas tem por semana — e a saída é um plano em fases, cada
fase com módulos que apontam para tags do catálogo.

Três decisões que moldam o prompt:

1. **O nível decide a FORMA do módulo, não se ele existe.** Até N2, módulo de
   ensino. De N3 para cima, revisão curta: um checkpoint de no máximo 2h com o
   caso difícil, a armadilha de produção e a decisão de arquitetura — o que
   vem DEPOIS do que a pessoa já faz. Nunca do zero: quem está em N4 lendo "o
   que é um container" fecha o app.

   A revisão é limitada a uma por fase e a 10% do orçamento, e é a segunda
   coisa a ser cortada quando as horas não fecham. Reforço é bom; um plano que
   gasta metade do prazo repassando o que a pessoa já sabe não é.

2. **Horas antes de escopo.** O plano é dimensionado pelas horas semanais
   declaradas, não pelo ideal do assunto. Um plano de 26 semanas que exige 20h
   de quem tem 6h não é ambicioso, é um plano que será abandonado na terceira
   semana.

3. **Distância curta primeiro, salvo dependência.** Levar alguém de N1 a N3
   custa uma fração do que custa levá-lo de N0 a N3, e entrega resultado
   visível antes — o que sustenta a pessoa nas primeiras semanas, que é quando
   os planos morrem. Então, entre dois assuntos que não bloqueiam um ao outro,
   ganha o que já tem chão.

   Com duas exceções que a regra sozinha erraria, e que estão no prompt:

   - **Dependência manda.** Se o N0 é pré-requisito do N1, ele vem antes.
     Inverter isso desmancha a escada e o plano deixa de ser trilha.
   - **O N0 essencial vai CEDO, não por último.** Se o objetivo exige uma
     tecnologia em que a pessoa está no zero, ela é ao mesmo tempo a mais cara
     e a mais importante; empurrá-la para o fim de um prazo fechado é a forma
     mais confiável de ela não acontecer. O que vai para o fim — e é o
     primeiro a ser cortado quando as horas não fecham — é o N0 que o objetivo
     NÃO exige.
"""

from typing import Any

from app.ai_providers import AiResult, generate_json
from app.services import escada

ROADMAP_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "resumo": {"type": "STRING"},
        "semanas": {"type": "INTEGER"},
        "fases": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "titulo": {"type": "STRING"},
                    "objetivo": {"type": "STRING"},
                    "semana_inicio": {"type": "INTEGER"},
                    "semana_fim": {"type": "INTEGER"},
                    "modulos": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "titulo": {"type": "STRING"},
                                "descricao": {"type": "STRING"},
                                "tipo": {"type": "STRING"},
                                "nivel": {"type": "STRING"},
                                "horas": {"type": "NUMBER"},
                                "semana_inicio": {"type": "INTEGER"},
                                "semana_fim": {"type": "INTEGER"},
                                "tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                                "objetivos": {"type": "ARRAY", "items": {"type": "STRING"}},
                            },
                            "required": ["titulo", "horas", "tags"],
                        },
                    },
                },
                "required": ["titulo", "modulos"],
            },
        },
    },
    "required": ["titulo", "fases"],
}

SYSTEM_PROMPT = """Você monta planos de estudo para profissionais de tecnologia, em português do Brasil.

Regras:

1. O plano cobre a distância entre o que a pessoa já sabe e o objetivo — e o
   NÍVEL dela decide a FORMA do módulo, não se ele existe.

   - Nível 0, 1 ou 2: módulo de ensino, do tamanho que a distância pedir.
   - Nível 3 ou mais: NUNCA ensine do zero. Entra como REVISÃO: um módulo
     curto (no máximo 2h), tipo "checkpoint", nivel "avancado", cujo conteúdo
     é resumo do que ela já sabe mais o que vem DEPOIS — o caso difícil, a
     armadilha de produção, a decisão de arquitetura. Os objetivos precisam
     ser exercícios de nível avançado, não recapitulação de básico. Quem está
     em nível 4 lendo "o que é um container" fecha o app.

   Limite: no máximo UM módulo de revisão por fase, e a soma de todos eles
   nunca passa de 10% do orçamento de horas. Revisão é reforço; o plano existe
   para cobrir o que falta.
2. Dimensione pelo tempo disponível informado. Some as horas de todos os
   módulos: o total precisa caber em (horas por semana x número de semanas),
   com folga de 15% para imprevisto. É melhor entregar um plano menor e
   inteiro do que um plano grande e abandonado.

   Quando não couber tudo, corte NESTA ordem: primeiro o que está em ZERO e o
   objetivo não exige; depois as revisões de nível 3+; por último o
   aprofundamento que o objetivo não exige. Nunca corte o que o objetivo
   exige — se nem isso couber, reduza a profundidade dos módulos e diga no
   resumo o que ficou de fora.

3. PRIORIDADE ENTRE ASSUNTOS. Entre dois assuntos que não dependem um do
   outro, comece pelo que a pessoa JÁ SABE PARCIALMENTE: sair de parcial para
   autônomo custa uma fração do que custa sair do zero, e o resultado aparece
   nas primeiras semanas, que é quando um plano é abandonado.

   Duas exceções, e elas mandam mais que a regra acima:

   a) Dependência vence sempre. Se algo em ZERO é pré-requisito de algo
      parcial, o que está em zero vem ANTES. Ver ORDEM OBRIGATORIA.
   b) O que está em ZERO e o OBJETIVO EXIGE vai CEDO — na primeira ou segunda
      fase — e não no fim. É o assunto mais longo do plano; deixá-lo para as
      últimas semanas é garantir que não seja concluído. É o resto do zero (o
      que a pessoa quer aprender mas o objetivo não exige) que vai para o fim.

4. De 3 a 5 fases, em ordem de dependência. Quando o pedido trouxer o bloco
   ORDEM OBRIGATORIA, ele NÃO é sugestão: é a ordem em que as tecnologias
   podem ser estudadas, e um módulo nunca pode vir antes daquilo de que
   depende. Onde o bloco não disser nada, use o bom senso da área — nada de
   arquitetura antes de a pessoa escrever o suficiente para ter o que
   arquitetar.
5. O campo tipo de cada módulo: skill, project, checkpoint ou reading.
   Toda fase termina com um project ou checkpoint — leitura sem entrega
   não comprova nada.
6. O campo nivel: iniciante, intermediario ou avancado.
7. O campo tags usa os nomes EXATOS da lista de tecnologias conhecidas que
   você recebeu. Só invente nome novo se o assunto realmente não estiver lá.
8. O campo objetivos traz de 2 a 4 frases começando com verbo no infinitivo,
   cada uma verificável (por exemplo: Escrever uma query com JOIN FETCH que
   elimina o N+1), nunca vaga (por exemplo: Entender JPA).
9. Não repita módulo entre fases. Não use jargão de marketing.
10. Responda apenas o JSON."""


def build_prompt(
    *,
    objective: str,
    weeks: int,
    weekly_hours: int,
    current_role: str,
    years: float,
    known: list[dict[str, Any]],
    targets: list[str],
    catalog_names: list[str],
    extra: str = "",
) -> str:
    """O retrato do usuário como texto. Cada bloco existe para responder uma
    pergunta que o modelo faria se pudesse perguntar."""
    alvos = {nome.casefold() for nome in targets}
    dominated = [
        f"{item['name']} (nivel {item['proficiency']}/5)"
        for item in known
        if item["proficiency"] >= 3
    ]
    partial = [
        f"{item['name']} (nivel {item['proficiency']}/5)"
        for item in known
        if 0 < item["proficiency"] < 3
    ]
    # O que está no zero se divide em dois, e a diferença decide a ORDEM do
    # plano: o zero que o objetivo exige é o assunto mais longo e mais
    # importante — vai cedo. O zero que a pessoa só gostaria de aprender vai
    # por último, e é o primeiro a sair quando as horas não fecham.
    zero_essencial = [
        item["name"]
        for item in known
        if item["proficiency"] == 0 and item["name"].casefold() in alvos
    ]
    zero_desejado = [
        item["name"]
        for item in known
        if item["proficiency"] == 0 and item["name"].casefold() not in alvos
    ]

    budget = weeks * weekly_hours
    lines = [
        f"OBJETIVO: {objective}",
        f"PRAZO: {weeks} semanas, {weekly_hours}h por semana (orcamento total ~{budget}h)",
        f"MOMENTO ATUAL: {current_role or 'nao informado'}, {years or 0} anos de experiencia",
        "",
        # Os blocos vão na ordem em que devem ser considerados. O modelo lê de
        # cima para baixo, e o que aparece primeiro pesa mais — então a ordem
        # do texto repete a regra 3 em vez de contrariá-la.
        "JA DOMINA — SO REVISAO CURTA (nunca do zero; checkpoint de ate 2h com "
        "o caso dificil e a armadilha de producao, nivel avancado): "
        + (", ".join(dominated) or "nada declarado"),
        "SABE PARCIALMENTE — COMECE POR AQUI (distancia curta, resultado "
        "rapido; aprofundar ate autonomo): " + (", ".join(partial) or "nada declarado"),
        "DO ZERO E EXIGIDO PELO OBJETIVO (o mais caro do plano; agende CEDO, "
        "primeira ou segunda fase): " + (", ".join(zero_essencial) or "nada declarado"),
        "DO ZERO, APENAS DESEJADO (deixe para o fim; corte isto primeiro se "
        "as horas nao fecharem): " + (", ".join(zero_desejado) or "nada declarado"),
    ]
    if targets:
        lines.append("MARCADO COMO ALVO PELA PESSOA: " + ", ".join(targets))
    if extra.strip():
        lines += ["", "CONTEXTO ADICIONAL ESCRITO PELA PESSOA:", extra.strip()[:2000]]
    lines += [
        "",
        "TECNOLOGIAS CONHECIDAS PELO SISTEMA (use estes nomes nas tags):",
        ", ".join(catalog_names[:400]),
    ]

    # A ordem de aprendizado vai como DADO, e não como pedido de bom senso.
    #
    # Ordenar é o que o modelo mais erra, e aqui o erro custa a trilha inteira:
    # a pessoa abre o plano, vê Docker na primeira semana e não tem como saber
    # que aquilo está fora de ordem. O grafo de services/escada.py é curado e
    # revisável, e diz o que vem antes do quê.
    #
    # Entra ANTES da geração, e não só como correção depois: reordenar módulos
    # prontos conserta a sequência, mas o CONTEÚDO de cada um continua sem
    # supor o que veio antes — e é isso que separa uma trilha de uma lista.
    dependencias = escada.ordem_para_o_prompt(catalog_names[:400])
    if dependencias:
        lines += [
            "",
            "ORDEM OBRIGATORIA (o que so pode ser estudado depois de que):",
            dependencias,
        ]
    return "\n".join(lines)


async def generate(prompt: str) -> tuple[dict[str, Any], AiResult]:
    result = await generate_json(SYSTEM_PROMPT, prompt, ROADMAP_SCHEMA)
    return _normalize(result.content), result


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Revalida a resposta. Necessário porque os provedores que não são o
    Gemini só garantem JSON válido, não este formato."""
    phases = []
    for phase in raw.get("fases") or []:
        if not isinstance(phase, dict) or not str(phase.get("titulo") or "").strip():
            continue
        modules = []
        for module in phase.get("modulos") or []:
            if not isinstance(module, dict):
                continue
            title = str(module.get("titulo") or "").strip()
            if not title:
                continue
            modules.append(
                {
                    "titulo": title[:200],
                    "descricao": str(module.get("descricao") or "").strip()[:1000],
                    "tipo": _kind(module.get("tipo")),
                    "nivel": _level(module.get("nivel")),
                    "horas": _hours(module.get("horas")),
                    "semana_inicio": _week(module.get("semana_inicio")),
                    "semana_fim": _week(module.get("semana_fim")),
                    "tags": [
                        str(tag).strip() for tag in (module.get("tags") or []) if str(tag).strip()
                    ][:8],
                    "objetivos": [
                        str(item).strip()
                        for item in (module.get("objetivos") or [])
                        if str(item).strip()
                    ][:6],
                }
            )
        if not modules:
            continue
        phases.append(
            {
                "titulo": str(phase.get("titulo")).strip()[:200],
                "objetivo": str(phase.get("objetivo") or "").strip()[:600],
                "semana_inicio": _week(phase.get("semana_inicio")),
                "semana_fim": _week(phase.get("semana_fim")),
                "modulos": modules,
            }
        )

    return {
        "titulo": str(raw.get("titulo") or "Plano de estudos").strip()[:200],
        "resumo": str(raw.get("resumo") or "").strip()[:2000],
        "semanas": _week(raw.get("semanas")) or 12,
        "fases": phases,
    }


def _kind(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    return value if value in {"skill", "project", "checkpoint", "reading"} else "skill"


def _level(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    return value if value in {"iniciante", "intermediario", "avancado"} else "intermediario"


def _hours(raw: Any) -> float:
    try:
        return max(0.0, min(200.0, round(float(raw), 1)))
    except (TypeError, ValueError):
        return 0.0


def _week(raw: Any) -> int:
    try:
        return max(0, min(104, int(raw)))
    except (TypeError, ValueError):
        return 0
