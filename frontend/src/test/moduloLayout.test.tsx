/**
 * O alinhamento da página do módulo: os cartões da direita começam onde começa o cartão da esquerda.
 *
 * O relato, com print: "Ao final você consegue" ficava MAIS ALTO que o cartão da pergunta. A coluna da direita
 * nascia no topo da grade, acima da descrição e das abas, e o cartão do quiz só começava depois delas.
 *
 * O jsdom não calcula layout de grade, então o que se protege aqui é a ESTRUTURA que faz o alinhamento acontecer:
 * o cabeçalho da esquerda (descrição + abas) é um item PRÓPRIO da grade, e o conteúdo da aba e os cartões
 * laterais são irmãos, na linha seguinte — nunca dentro do mesmo bloco que as abas.
 */

import { render, screen } from "@testing-library/react";
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
  mockServer({
    "GET /roadmap/current": () => ({ body: plano }),
    "GET /library": () => ({ body: [] }),
    "POST /library/curate": () => ({ body: { novos: 0, tags_buscadas: [], motivo: null } }),
    "GET /quizzes/em-andamento": () => ({ body: { quiz: null, rascunho: null } }),
    "GET /quizzes/historico": () => ({ body: [] }),
  });
  return render(
    <AppStateProvider>
      <ModulePage />
    </AppStateProvider>,
  );
}

describe("página do módulo", () => {
  it("o cabeçalho com as abas é um item da grade, e o conteúdo e os cartões laterais vêm depois, lado a lado", async () => {
    montar();

    const laterais = (await screen.findByText("Ao final você consegue")).closest("div[style*='grid-column']") as HTMLElement;
    const grade = laterais.parentElement as HTMLElement;
    const [cabecalho, conteudo, lateral] = Array.from(grade.children) as HTMLElement[];

    expect(grade.children).toHaveLength(3);
    expect(lateral).toBe(laterais);
    // As abas moram só no cabeçalho; os cartões laterais NÃO estão dentro do bloco das abas.
    expect(cabecalho.textContent).toContain("Material");
    expect(cabecalho.textContent).toContain("Quiz");
    expect(cabecalho.contains(laterais)).toBe(false);
    // Conteúdo da aba e cartões laterais são irmãos da mesma grade: começam na mesma linha.
    expect(conteudo.parentElement).toBe(lateral.parentElement);
    expect(conteudo.contains(lateral)).toBe(false);
    expect(lateral.textContent).toContain("Instalar e configurar o Docker Engine.");
    expect(lateral.textContent).toContain("Marcar como concluído");
  });

  it("o conteúdo da aba não carrega a descrição nem as abas: elas ficam acima, no cabeçalho", async () => {
    montar();
    const laterais = (await screen.findByText("Ao final você consegue")).closest("div[style*='grid-column']") as HTMLElement;
    const [cabecalho, conteudo] = Array.from((laterais.parentElement as HTMLElement).children) as HTMLElement[];

    expect(cabecalho.textContent).toContain("Conceitos e prática de containers.");
    expect(conteudo.textContent).not.toContain("Conceitos e prática de containers.");
  });
});
