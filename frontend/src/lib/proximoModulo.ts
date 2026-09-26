/**
 * Qual módulo abrir depois de concluir um.
 *
 * O servidor já promove o próximo módulo a "em andamento" ao concluir (`_advance_next` em
 * routers/roadmap.py), então o normal é achar um `doing` logo à frente. Mas a pessoa pode ter concluído
 * fora de ordem, ou o servidor não ter promovido nada (o próximo estava travado por outro pré-requisito):
 * por isso a regra não depende só do `doing`.
 *
 * Ordem de preferência, sempre entre módulos ainda por fazer (`doing` ou `todo`; `locked` e `done` não são
 * "o próximo assunto"):
 *   1. o que o servidor marcou como em andamento, DEPOIS do concluído;
 *   2. o primeiro que vem depois do concluído;
 *   3. se não sobrou nenhum depois, o primeiro que ficou para trás (um módulo pulado), antes de dizer "acabou".
 *
 * Devolve `null` quando não há mais nada a fazer: aí a tela mostra o plano concluído.
 */

import type { RoadmapNode } from "@/api/types";

export function proximoModulo(modules: readonly RoadmapNode[], concluidoId: string): RoadmapNode | null {
  const posicaoDoConcluido = modules.findIndex((module) => module.id === concluidoId);
  const disponiveis = modules
    .map((module, posicao) => ({ module, posicao }))
    .filter(({ module }) => module.id !== concluidoId && (module.status === "doing" || module.status === "todo"));

  const adiante = disponiveis.filter(({ posicao }) => posicao > posicaoDoConcluido);
  const candidatos = adiante.length > 0 ? adiante : disponiveis;
  return (candidatos.find(({ module }) => module.status === "doing") ?? candidatos[0])?.module ?? null;
}
