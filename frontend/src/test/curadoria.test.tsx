/**
 * A curadoria que roda sozinha.
 *
 * O produto promete um roadmap COM material. Estes testes seguram as duas
 * pontas dessa promessa: um módulo vazio procura por conta própria, e não
 * procura de novo a cada render — a chamada custa duas APIs externas mais a
 * verificação de cada link, e um efeito mal contido gastaria a cota inteira
 * indo e voltando entre duas abas.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MaterialTab } from "@/components/quiz/MaterialTab";
import { AppStateProvider } from "@/hooks/useAppState";
import { resetCuradoriaForTests } from "@/lib/curadoria";
import type { RoadmapNode } from "@/api/types";
import { mockServer, type Handler } from "./server";

const node: RoadmapNode = {
  id: "n-1",
  title: "Filas e workers",
  description: null,
  kind: "skill",
  status: "doing",
  progress_pct: 0,
  level: null,
  estimated_hours: 10,
  week_start: 1,
  week_end: 2,
  tag_ids: ["t-celery"],
  objectives: [],
  order_index: 0,
};

const umMaterial = {
  id: "r-1",
  kind: "video",
  title: "Celery do zero",
  url: "https://exemplo",
  provider: "YouTube",
  author: null,
  description: null,
  duration_min: 90,
  language: "pt",
  level: null,
  tag_ids: ["t-celery"],
  quality_score: 9,
  user_status: null,
  user_progress_pct: 0,
  user_rating: null,
  user_position_note: null,
  user_position_seconds: null,
};

/** A aba abre um material navegando, então precisa do estado de navegação. */
const montar = (no = node) =>
  render(
    <AppStateProvider>
      <MaterialTab node={no} />
    </AppStateProvider>,
  );

beforeEach(resetCuradoriaForTests);
afterEach(() => vi.unstubAllGlobals());

/** A biblioteca começa vazia e passa a ter um item depois da curadoria. */
function servidorQueAcha() {
  let achou = false;
  const curate: Handler = () => {
    achou = true;
    return { body: { novos: 1, tags_buscadas: ["Celery"], motivo: null } };
  };
  return mockServer({
    "GET /library": () => ({ body: achou ? [umMaterial] : [] }),
    "POST /library/curate": curate,
  });
}

describe("busca automática de material", () => {
  it("procura sozinha quando o módulo abre sem nada", async () => {
    const servidor = servidorQueAcha();

    montar();

    // Ninguém tocou em botão nenhum — o material aparece porque a tela foi
    // atrás dele.
    expect(await screen.findByText("Celery do zero")).toBeInTheDocument();
    expect(servidor.calls.filter((c) => c.url.startsWith("/library/curate"))).toHaveLength(1);
  });

  it("procura para o módulo certo, não pelas tags do perfil", async () => {
    const servidor = servidorQueAcha();

    montar();
    await screen.findByText("Celery do zero");

    // Sem o `node_id` o backend buscaria pelas tags do perfil inteiro, e o
    // módulo aberto continuaria vazio.
    expect(servidor.calls.some((c) => c.url === "/library/curate?node_id=n-1")).toBe(true);
  });

  it("não repete a busca no mesmo módulo", async () => {
    const servidor = mockServer({
      "GET /library": () => ({ body: [] }),
      "POST /library/curate": () => ({ body: { novos: 0, tags_buscadas: [], motivo: "Buscamos há pouco." } }),
    });

    const { rerender } = montar();
    await screen.findByText("Sem material para este módulo ainda");
    const arvore = (
      <AppStateProvider>
        <MaterialTab node={node} />
      </AppStateProvider>
    );
    rerender(arvore);
    rerender(arvore);

    await waitFor(() =>
      expect(servidor.calls.filter((c) => c.url.startsWith("/library/curate"))).toHaveLength(1),
    );
  });

  it("cai no botão manual quando a busca automática não traz nada", async () => {
    mockServer({
      "GET /library": () => ({ body: [] }),
      "POST /library/curate": () => ({ body: { novos: 0, tags_buscadas: [], motivo: "Buscamos há pouco." } }),
    });

    montar();

    // O caminho de insistir continua existindo — e é o único que mostra o
    // motivo devolvido pelo servidor.
    expect(await screen.findByRole("button", { name: "Procurar material" })).toBeInTheDocument();
  });
});
