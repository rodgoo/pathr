/**
 * Marcar módulo como concluído deve buscar o roadmap uma única vez.
 *
 * O bug: o onClick buscava `roadmapApi.current()` para achar o próximo
 * módulo e, poucas linhas depois, chamava `plan.reload()` — que dispara de
 * novo o `useQuery` interno e refaz a MESMA chamada. O teste conta quantas
 * vezes `GET /roadmap/current` é chamado depois do clique: deve ser só uma
 * (a busca explícita), reaproveitada via `plan.set`, em vez de duas.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppStateProvider } from "@/hooks/useAppState";
import { ModulePage } from "@/pages/ModulePage";
import { mockServer } from "./server";

const modulo = {
  id: "n-1",
  title: "Docker",
  description: "Conceitos e prática de containers.",
  kind: "skill",
  status: "doing",
  progress_pct: 0,
  level: "intermediario",
  estimated_hours: 4,
  week_start: 1,
  week_end: 2,
  tag_ids: ["t-docker"],
  objectives: ["Instalar e configurar o Docker Engine."],
  order_index: 1,
};

const plano = {
  id: "r-1",
  title: "Plano",
  horizon_weeks: 12,
  weekly_hours: 8,
  status: "active",
  total_nodes: 1,
  done_nodes: 0,
  progress_pct: 0,
  phases: [{ ...modulo, id: "p-1", title: "Fundamentos de DevOps", kind: "phase", modules: [modulo] }],
};

afterEach(() => vi.unstubAllGlobals());

function montar() {
  let chamadasAoRoadmap = 0;
  const server = mockServer({
    "GET /roadmap/current": () => {
      chamadasAoRoadmap += 1;
      // A primeira chamada é a carga inicial da tela; a segunda é a busca
      // explícita do próximo módulo, feita DEPOIS do PATCH que concluiu
      // este — e é essa resposta que já traz o módulo marcado como feito.
      const concluido = chamadasAoRoadmap > 1;
      return {
        body: {
          ...plano,
          phases: plano.phases.map((fase) => ({
            ...fase,
            modules: fase.modules.map((mod) => (concluido ? { ...mod, status: "done" } : mod)),
          })),
        },
      };
    },
    "GET /library": () => ({ body: [] }),
    "POST /library/curate": () => ({ body: { novos: 0, tags_buscadas: [], motivo: null } }),
    "GET /quizzes/em-andamento": () => ({ body: { quiz: null, rascunho: null } }),
    "GET /quizzes/historico": () => ({ body: [] }),
    "PATCH /roadmap/nodes/n-1": () => ({ body: { ...modulo, status: "done" } }),
  });
  return {
    server,
    user: userEvent.setup(),
    ...render(
      <AppStateProvider>
        <ModulePage />
      </AppStateProvider>,
    ),
  };
}

describe("concluir módulo", () => {
  it("busca o roadmap atualizado só uma vez, não duas", async () => {
    const { server, user } = montar();

    const botao = await screen.findByRole("button", { name: "Marcar como concluído" });

    const buscasAntes = server.calls.filter(
      (call) => call.method === "GET" && call.url === "/roadmap/current",
    ).length;
    expect(buscasAntes).toBe(1);

    await user.click(botao);
    // Com só um módulo no plano, concluí-lo some com o próximo módulo a
    // mostrar — a tela cai no estado de "plano concluído". Isso confirma que
    // `plan.set` aplicou a resposta já buscada, sem esperar outra viagem ao
    // servidor para refletir o novo status.
    await screen.findByText("Plano concluído");

    const buscasDepois = server.calls.filter(
      (call) => call.method === "GET" && call.url === "/roadmap/current",
    ).length;
    // Antes do fix seriam 3: a carga inicial, a busca explícita do próximo
    // módulo e o `reload()` refazendo a mesma chamada.
    expect(buscasDepois).toBe(2);
  });
});
