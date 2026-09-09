"""Geração do roadmap por IA.

A entrada é o retrato do usuário — o que ele já sabe (com nível), onde quer
chegar, quantas horas tem por semana — e a saída é um plano em fases, cada
fase com módulos que apontam para tags do catálogo.

Duas decisões que moldam o prompt:

1. **Só cobre lacuna.** Um módulo sobre algo que a pessoa já faz em nível 4 é
   tempo que ela não tem. O prompt recebe explicitamente o que NÃO deve
   ensinar, e é a lista mais importante que ele recebe.

2. **Horas antes de escopo.** O plano é dimensionado pelas horas semanais
   declaradas, não pelo ideal do assunto. Um plano de 26 semanas que exige 20h
   de quem tem 6h não é ambicioso, é um plano que será abandonado na terceira
   semana.
"""

from typing import Any

from app.ai_providers import AiResult, generate_json

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

1. O plano cobre APENAS a distância entre o que a pessoa já sabe e o objetivo
   declarado. Nunca inclua módulo sobre tecnologia que ela já domina em nível
   3 ou mais, a não ser que o objetivo exija explicitamente aprofundá-la.
2. Dimensione pelo tempo disponível informado. Some as horas de todos os
   módulos: o total precisa caber em (horas por semana x número de semanas),
   com folga de 15% para imprevisto. É melhor entregar um plano menor e
   inteiro do que um plano grande e abandonado.
3. De 3 a 5 fases, em ordem de dependência: nada de Docker antes de a pessoa
   conseguir rodar a aplicação, nada de arquitetura antes de ela escrever o
   suficiente para ter o que arquitetar.
4. O campo tipo de cada módulo: skill, project, checkpoint ou reading.
   Toda fase termina com um project ou checkpoint — leitura sem entrega
   não comprova nada.
5. O campo nivel: iniciante, intermediario ou avancado.
6. O campo tags usa os nomes EXATOS da lista de tecnologias conhecidas que
   você recebeu. Só invente nome novo se o assunto realmente não estiver lá.
7. O campo objetivos traz de 2 a 4 frases começando com verbo no infinitivo,
   cada uma verificável (por exemplo: Escrever uma query com JOIN FETCH que
   elimina o N+1), nunca vaga (por exemplo: Entender JPA).
8. Não repita módulo entre fases. Não use jargão de marketing.
9. Responda apenas o JSON."""


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
    to_learn = [item["name"] for item in known if item["proficiency"] == 0]

    budget = weeks * weekly_hours
    lines = [
        f"OBJETIVO: {objective}",
        f"PRAZO: {weeks} semanas, {weekly_hours}h por semana (orcamento total ~{budget}h)",
        f"MOMENTO ATUAL: {current_role or 'nao informado'}, {years or 0} anos de experiencia",
        "",
        "JA DOMINA (NAO ensine isto): " + (", ".join(dominated) or "nada declarado"),
        "SABE PARCIALMENTE (pode aprofundar): " + (", ".join(partial) or "nada declarado"),
        "QUER APRENDER: " + (", ".join(to_learn) or "nao declarado"),
    ]
    if targets:
        lines.append("PRIORIDADE EXPLICITA: " + ", ".join(targets))
    if extra.strip():
        lines += ["", "CONTEXTO ADICIONAL ESCRITO PELA PESSOA:", extra.strip()[:2000]]
    lines += [
        "",
        "TECNOLOGIAS CONHECIDAS PELO SISTEMA (use estes nomes nas tags):",
        ", ".join(catalog_names[:400]),
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
