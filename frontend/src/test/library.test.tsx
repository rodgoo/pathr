/**
 * O acervo, agora dentro da aba de material.
 *
 * A Biblioteca era uma tela própria no menu e foi ABSORVIDA pelo módulo: duas
 * telas listando o mesmo material com recortes diferentes davam dois lugares
 * para marcar "concluído", e só um deles contava.
 *
 * O que não podia se perder na fusão, e é o que estes testes seguram: o botão
 * de procurar material continua ao alcance mesmo com a lista cheia, a busca
 * atravessa todo o plano (não só o módulo aberto), e quem filtra por português
 * e não acha nada é informado de quanto existe em inglês em vez de receber um
 * "nada encontrado" que esconde o acervo.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MaterialTab } from "@/components/quiz/MaterialTab";
import { AppStateProvider } from "@/hooks/useAppState";
import { resetCuradoriaForTests } from "@/lib/curadoria";
import type { RoadmapNode } from "@/api/types";
import { mockServer } from "./server";

const node: RoadmapNode = {
  id: "n-1",
  title: "Containers",
  description: null,
  kind: "skill",
  status: "doing",
  progress_pct: 0,
  level: null,
  estimated_hours: 10,
  week_start: 1,
  week_end: 2,
  tag_ids: ["t"],
  objectives: [],
  order_index: 0,
};

const doc = {
  id: "d1",
  kind: "doc",
  title: "Docker docs",
  url: "https://docs.docker.com/",
  provider: "docs.docker.com",
  author: null,
  description: null,
  duration_min: null,
  language: "en",
  level: null,
  tag_ids: ["t"],
  quality_score: 90,
  user_status: null,
  user_progress_pct: 0,
  user_rating: null,
  user_position_note: null,
  user_position_seconds: null,
};

/** De outro módulo: só aparece quando a busca atravessa o plano inteiro. */
const deOutroModulo = { ...doc, id: "d2", title: "Kafka em produção", tag_ids: ["outra"] };

function montar() {
  render(
    <AppStateProvider>
      <MaterialTab node={node} />
    </AppStateProvider>,
  );
}

beforeEach(resetCuradoriaForTests);
afterEach(() => vi.unstubAllGlobals());

it("o botão de busca existe mesmo com a lista cheia", async () => {
  mockServer({ "GET /library": () => ({ body: [doc] }) });
  montar();
  expect(await screen.findByText("Docker docs")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Procurar material/ })).toBeInTheDocument();
});

it("sem busca, mostra só o material deste módulo", async () => {
  mockServer({ "GET /library": () => ({ body: [doc, deOutroModulo] }) });
  montar();
  expect(await screen.findByText("Docker docs")).toBeInTheDocument();
  expect(screen.queryByText("Kafka em produção")).not.toBeInTheDocument();
});

/**
 * Quem procura "kafka" não quer saber em qual módulo aquilo ficou guardado —
 * era justamente para isso que a Biblioteca servia, e é o que a busca daqui
 * precisa continuar fazendo.
 */
it("com busca, atravessa todo o material do plano", async () => {
  mockServer({ "GET /library": () => ({ body: [deOutroModulo] }) });
  montar();
  await screen.findByRole("searchbox", { name: "Buscar material" });

  await userEvent.type(screen.getByRole("searchbox", { name: "Buscar material" }), "kafka");

  expect(await screen.findByText("Kafka em produção")).toBeInTheDocument();
  expect(await screen.findByText(/em todo o seu plano/)).toBeInTheDocument();
});

it("em português sem resultado, diz quantos há em inglês e oferece mostrá-los", async () => {
  mockServer({
    "GET /library": (pedido) => ({ body: pedido.url.includes("language=pt") ? [] : [doc] }),
  });
  montar();
  expect(await screen.findByText(/há 1 em inglês/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Mostrar também em inglês" }));

  expect(await screen.findByText("Docker docs")).toBeInTheDocument();
});

it("o que já foi concluído desce para a seção Concluído, e o que falta vem primeiro", async () => {
  const feito = { ...doc, id: "d3", title: "Docker Compose na prática", user_status: "done" };
  mockServer({ "GET /library": () => ({ body: [feito, doc] }) });
  montar();
  const secao = await screen.findByRole("region", { name: "Concluídos" });
  expect(within(secao).getByText("Docker Compose na prática")).toBeInTheDocument();
  expect(within(secao).queryByText("Docker docs")).not.toBeInTheDocument();
  // O pendente aparece antes da seção no documento.
  const pendente = screen.getByText("Docker docs");
  expect(pendente.compareDocumentPosition(secao) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
