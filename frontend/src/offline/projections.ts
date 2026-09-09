/**
 * Aplica a fila de escritas sobre uma resposta guardada.
 *
 * Por que isto precisa existir: sem projeção, marcar um módulo como concluído
 * no avião e fechar o app faria o progresso "voltar" ao reabrir — a tela
 * leria o cache, que ainda é de antes da marcação, e a pessoa concluiria que
 * o app perdeu o que ela fez. A escrita continua guardada na fila, mas
 * ninguém acredita num app que mostra o contrário do que registrou.
 *
 * A projeção NÃO é uma segunda implementação das regras do servidor: ela
 * repete só a parte visível da resposta (o status do módulo, o status do
 * material, o texto do rascunho) e a aritmética que o painel mostra. Quando a
 * rede volta, a resposta real do servidor substitui tudo isto.
 */

import type { Resource, Roadmap } from "@/api/types";
import type { PendingWrite } from "./outbox";

/** `/roadmap/current`, `/roadmap/{id}` — mas não `/roadmap/nodes/...`. */
const CAMINHO_PLANO = /^\/roadmap\/(current|[^/]+)(\?|$)/;
const CAMINHO_NO = /^\/roadmap\/nodes\/([^/?]+)$/;
const CAMINHO_RASCUNHO = /^\/roadmap\/nodes\/([^/?]+)\/draft(\?|$)/;
const CAMINHO_PROGRESSO_MATERIAL = /^\/library\/([^/?]+)\/progress$/;

/**
 * A resposta guardada em `path`, com as escritas pendentes por cima.
 *
 * Devolve o corpo intacto quando não há nada a projetar — é o caso da maioria
 * das rotas, e forçar uma cópia de tudo só gastaria memória.
 */
export function project(path: string, body: unknown, fila: PendingWrite[]): unknown {
  if (fila.length === 0) return body;

  if (CAMINHO_RASCUNHO.test(path)) return projetaRascunho(path, body, fila);
  if (path.startsWith("/library?") || path === "/library") return projetaBiblioteca(body, fila);
  if (CAMINHO_PLANO.test(path) && !path.startsWith("/roadmap/nodes")) {
    return projetaPlano(body, fila);
  }
  return body;
}

/** O plano com o status dos módulos alterados offline, e as contas refeitas. */
function projetaPlano(body: unknown, fila: PendingWrite[]): unknown {
  const plano = body as Roadmap | null;
  if (!plano?.phases) return body;

  const alteracoes = new Map<string, Record<string, unknown>>();
  for (const item of fila) {
    const alvo = CAMINHO_NO.exec(item.path);
    if (alvo && item.method === "PATCH" && item.body) alteracoes.set(alvo[1], item.body);
  }
  if (alteracoes.size === 0) return body;

  const phases = plano.phases.map((fase) => ({
    ...fase,
    modules: fase.modules.map((modulo) => {
      const mudanca = alteracoes.get(modulo.id);
      if (!mudanca) return modulo;
      const status = (mudanca.status as Roadmap["phases"][number]["status"]) ?? modulo.status;
      return {
        ...modulo,
        status,
        // Concluir um módulo o leva a 100% mesmo sem o servidor confirmar: é
        // o que a barra de progresso mostraria depois da sincronização.
        progress_pct:
          typeof mudanca.progress_pct === "number"
            ? mudanca.progress_pct
            : status === "done"
              ? 100
              : modulo.progress_pct,
      };
    }),
  }));

  const modulos = phases.flatMap((fase) => fase.modules);
  const done = modulos.filter((modulo) => modulo.status === "done").length;

  return {
    ...plano,
    phases,
    done_nodes: done,
    progress_pct: modulos.length > 0 ? Math.round((done / modulos.length) * 100) : plano.progress_pct,
  };
}

/** A lista de materiais com o status e o "onde parei" marcados offline. */
function projetaBiblioteca(body: unknown, fila: PendingWrite[]): unknown {
  if (!Array.isArray(body)) return body;

  const alteracoes = new Map<string, Record<string, unknown>>();
  for (const item of fila) {
    const alvo = CAMINHO_PROGRESSO_MATERIAL.exec(item.path);
    if (alvo && item.body) alteracoes.set(alvo[1], item.body);
  }
  if (alteracoes.size === 0) return body;

  return (body as Resource[]).map((recurso) => {
    const mudanca = alteracoes.get(recurso.id);
    if (!mudanca) return recurso;
    return {
      ...recurso,
      user_status: (mudanca.status as Resource["user_status"]) ?? recurso.user_status,
      user_position_note:
        mudanca.position_note !== undefined
          ? (mudanca.position_note as string | null)
          : recurso.user_position_note,
      user_progress_pct:
        typeof mudanca.progress_pct === "number" ? mudanca.progress_pct : recurso.user_progress_pct,
      user_position_seconds:
        mudanca.position_seconds !== undefined
          ? (mudanca.position_seconds as number | null)
          : recurso.user_position_seconds,
    };
  });
}

/** O rascunho da atividade — o texto que a pessoa escreveu sem rede. */
function projetaRascunho(path: string, body: unknown, fila: PendingWrite[]): unknown {
  const pendente = fila.find((item) => item.method === "PUT" && `${item.path}` === path);
  if (!pendente?.body || typeof pendente.body.content !== "string") return body;
  return {
    ...(body as Record<string, unknown> | null),
    content: pendente.body.content,
    updated_at: new Date(pendente.queuedAt).toISOString(),
  };
}
