"""Ajustes dinâmicos de rota: o plano se corrige com a evidência que o app já tem.

O roadmap era gerado uma vez e nunca mais mudava — embora o app já medisse o
nível (quiz), as lacunas (revisão e Feynman) e o ritmo real (atividade). A
evidência para replanejar estava toda no banco; faltava quem a lesse.

## Três ajustes, cada um com o motivo à vista

- **Compactar** o módulo cujo domínio foi MEDIDO. Só quiz conta: o nível que
  veio do currículo é o que a pessoa escreveu sobre si, e compactar por ele
  pularia justamente o que ela superestimou. O módulo não some — vira revisão
  curta, que é a regra do produto para N3+ desde que "N3+ deixa de ser
  exclusão e vira revisão".
- **Reforçar** o módulo onde a lacuna se repete: conceitos acumulados na
  revisão, quiz abaixo de 50%, explicação abaixo de 50. Avançar por cima de uma
  base que falha empilha o próximo assunto sobre ela.
- **Reagendar** quando o ritmo real se afasta do planejado, ou quando os dois
  ajustes acima mudaram o tamanho dos módulos. Um cronograma que exige mais do
  que a pessoa tem não é ambicioso: é um cronograma que atrasa sem avisar.

Cada módulo é compactado ou reforçado no máximo uma vez (o histórico fica em
`pathr_roadmap.meta`). Sem esse limite, um módulo difícil ganharia horas toda
semana até o plano não terminar nunca.

Nada aqui fala com o banco: recebe a evidência pronta e devolve as mudanças.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

DOMINIO = 3
LIMIAR_PENDENCIAS = 3
NOTA_BAIXA = 50
# Fora desta faixa o ritmo real conta como desvio. Dentro, é variação normal
# de semana — replanejar por ela faria o cronograma tremer toda segunda.
RITMO_LENTO = 0.7
RITMO_RAPIDO = 1.3
DIAS_DE_RITMO = 14
# Menos que uma semana de histórico não é ritmo, é um dia bom ou ruim.
MINIMO_DE_DIAS = 7


@dataclass
class Evidencia:
    # tag_id -> (proficiência, origem). A origem decide se o nível é medido.
    nivel_por_tag: dict[str, tuple[int, str]]
    pendentes_por_tag: dict[str, int]
    nota_quiz_por_node: dict[str, float]
    nota_feynman_por_node: dict[str, int]
    horas_planejadas: float
    # None quando o plano é novo demais para ter ritmo.
    horas_reais: Optional[float]
    semana_atual: int
    ja_reforcados: set[str] = field(default_factory=set)
    ja_compactados: set[str] = field(default_factory=set)


def horas_por_semana(minutos_por_dia: dict[date, int], hoje: date, dias: int) -> float:
    """Horas de estudo por semana na janela dos últimos `dias`."""
    dias = max(1, dias)
    inicio = hoje - timedelta(days=dias - 1)
    total = sum(m for d, m in minutos_por_dia.items() if inicio <= d <= hoje)
    return round(total / 60 / (dias / 7), 1)


def reagendar(
    modulos: list[dict], horas_por_node: dict[str, float], ritmo: float, semana_inicial: int
) -> dict[str, tuple[int, int]]:
    """Distribui os módulos em semanas, em ordem, no ritmo dado.

    Enche cada semana até o ritmo e transborda para a seguinte — um módulo de
    6h num ritmo de 4h/semana ocupa duas semanas, não uma semana "estourada".
    """
    ritmo = max(0.5, ritmo)
    semana, usado = max(1, semana_inicial), 0.0
    agenda: dict[str, tuple[int, int]] = {}
    for modulo in modulos:
        restante = max(0.5, horas_por_node.get(str(modulo["id"]), 0.0) or 0.5)
        if usado >= ritmo - 1e-9:
            semana, usado = semana + 1, 0.0
        inicio = semana
        while restante > 1e-9:
            livre = ritmo - usado
            if livre <= 1e-9:
                semana, usado = semana + 1, 0.0
                continue
            gasto = min(livre, restante)
            usado += gasto
            restante -= gasto
        agenda[str(modulo["id"])] = (inicio, semana)
    return agenda


def propor(nodes: list[dict], ev: Evidencia) -> tuple[list[dict], dict[str, dict]]:
    """(mudanças para mostrar, campos a gravar por nó)."""
    modulos = sorted(
        (n for n in nodes if n.get("kind") != "phase"), key=lambda n: n.get("order_index") or 0
    )
    abertos = [n for n in modulos if n.get("status") not in ("done", "skipped")]
    horas = {str(n["id"]): float(n.get("estimated_hours") or 0) for n in modulos}
    mudancas: list[dict] = []
    campos: dict[str, dict] = {}

    for node in abertos:
        nid = str(node["id"])
        tags = [str(t) for t in (node.get("tag_ids") or [])]
        if not tags:
            continue

        medido = all(
            ev.nivel_por_tag.get(t, (0, ""))[0] >= DOMINIO
            and ev.nivel_por_tag.get(t, (0, ""))[1] == "quiz"
            for t in tags
        )
        if medido and nid not in ev.ja_compactados:
            antes = horas[nid]
            depois = max(1.0, round(antes * 0.5, 1))
            if depois < antes:
                horas[nid] = depois
                campos.setdefault(nid, {}).update({"estimated_hours": depois, "level": "avancado"})
                mudancas.append(
                    {
                        "node_id": nid,
                        "titulo": node.get("title"),
                        "tipo": "compactar",
                        "motivo": (
                            "Você mostrou domínio medido em quiz (N3 ou mais) em todas as "
                            "tecnologias deste módulo. Ele vira revisão curta em vez de "
                            "ensino do zero."
                        ),
                        "antes": {"horas": antes},
                        "depois": {"horas": depois},
                    }
                )
                continue

        motivos: list[str] = []
        pendentes = sum(ev.pendentes_por_tag.get(t, 0) for t in tags)
        if pendentes >= LIMIAR_PENDENCIAS:
            motivos.append(f"{pendentes} conceitos pendentes de revisão")
        nota_quiz = ev.nota_quiz_por_node.get(nid)
        if nota_quiz is not None and nota_quiz < NOTA_BAIXA:
            motivos.append(f"último quiz em {nota_quiz:.0f}%")
        nota_feynman = ev.nota_feynman_por_node.get(nid)
        if nota_feynman is not None and nota_feynman < NOTA_BAIXA:
            motivos.append(f"última explicação em {nota_feynman}/100")

        if motivos and nid not in ev.ja_reforcados:
            antes = horas[nid]
            depois = round(min(antes + 4, max(antes * 1.5, antes + 1)), 1)
            horas[nid] = depois
            campos.setdefault(nid, {})["estimated_hours"] = depois
            mudancas.append(
                {
                    "node_id": nid,
                    "titulo": node.get("title"),
                    "tipo": "reforcar",
                    "motivo": (
                        "Mais tempo neste módulo: "
                        + ", ".join(motivos)
                        + ". Avançar agora empilharia o próximo assunto sobre uma base "
                        "que ainda falha."
                    ),
                    "antes": {"horas": antes},
                    "depois": {"horas": depois},
                }
            )

    ritmo = ev.horas_planejadas
    motivo_ritmo: Optional[str] = None
    if ev.horas_reais is not None and ev.horas_planejadas > 0:
        razao = ev.horas_reais / ev.horas_planejadas
        if razao < RITMO_LENTO or razao > RITMO_RAPIDO:
            ritmo = min(max(ev.horas_reais, 1.0), ev.horas_planejadas * 1.5)
            motivo_ritmo = (
                f"Nas últimas semanas você estudou {ev.horas_reais:.1f}h por semana; o "
                f"plano previa {ev.horas_planejadas:.0f}h. O cronograma foi recalculado "
                "no seu ritmo real."
            )

    if (motivo_ritmo or mudancas) and abertos:
        fim_antes = max(int(n.get("week_end") or 0) for n in abertos)
        agenda = reagendar(abertos, horas, ritmo, ev.semana_atual)
        por_id = {str(n["id"]): n for n in nodes}
        for nid, (inicio, fim) in agenda.items():
            node = por_id[nid]
            if (inicio, fim) != (node.get("week_start"), node.get("week_end")):
                campos.setdefault(nid, {}).update({"week_start": inicio, "week_end": fim})
        fim_depois = max(fim for _, fim in agenda.values())

        # As fases acompanham os filhos: sem isto a linha do tempo mostraria a
        # fase terminando antes do último módulo dela.
        for fase in (n for n in nodes if n.get("kind") == "phase"):
            semanas = []
            for filho in modulos:
                if str(filho.get("parent_id")) != str(fase["id"]):
                    continue
                gravado = campos.get(str(filho["id"]), {})
                inicio = gravado.get("week_start", filho.get("week_start"))
                fim = gravado.get("week_end", filho.get("week_end"))
                if inicio and fim:
                    semanas.append((int(inicio), int(fim)))
            if semanas:
                novo = (min(s for s, _ in semanas), max(f for _, f in semanas))
                if novo != (fase.get("week_start"), fase.get("week_end")):
                    campos.setdefault(str(fase["id"]), {}).update(
                        {"week_start": novo[0], "week_end": novo[1]}
                    )

        if motivo_ritmo or fim_depois != fim_antes:
            mudancas.append(
                {
                    "node_id": None,
                    "titulo": "Cronograma",
                    "tipo": "reagendar",
                    "motivo": motivo_ritmo
                    or (
                        "Os módulos ajustados acima mudaram de tamanho, e as semanas "
                        "seguintes foram redistribuídas."
                    ),
                    "antes": {"fim_semana": fim_antes},
                    "depois": {"fim_semana": fim_depois},
                }
            )

    return mudancas, campos
