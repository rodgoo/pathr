/**
 * O checklist da semana na tela.
 *
 * O que se verifica é o contrato com quem usa: a ordem do servidor é mantida
 * (é a do método), marcar grava, o que o banco confirmou não se desmarca, e
 * uma falha ao gravar devolve a caixa ao estado real em vez de mentir.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { WeeklyChecklist } from "@/components/dashboard/WeeklyChecklist";
import { AppStateProvider } from "@/hooks/useAppState";
import { mockServer, type Handler } from "./server";

afterEach(() => vi.unstubAllGlobals());

const item = (id: string, titulo: string, extra: Record<string, unknown> = {}) => ({
  id,
  tipo: "quiz",
  pilar: "Recordação ativa",
  titulo,
  detalhe: "Responder sem consultar é o que fixa.",
  minutos: 15,
  node_id: "n1",
  modulo: "React",
  nivel: "intermediario",
  feito: false,
  verificado: false,
  feito_em: null,
  ...extra,
});

const semana = {
  semana: 2,
  inicio: "2026-09-07",
  orcamento_min: 480,
  ajustes: [],
  resumo: { total: 3, feitos: 1, minutos: 45, minutos_feitos: 15 },
  itens: [
    item("revisao", "Revisar 4 conceitos pendentes", { tipo: "revisao", pilar: "Repetição espaçada", node_id: null, nivel: null }),
    item("quiz:n1", "Quiz de React"),
    item("feynman:n1", "Explicar React com suas palavras", {
      tipo: "feynman",
      pilar: "Feynman",
      feito: true,
      verificado: true,
    }),
  ],
};

function montar(rotas: Record<string, Handler>) {
  const server = mockServer({ "GET /plan/week": () => ({ body: semana }), ...rotas });
  render(
    <AppStateProvider>
      <WeeklyChecklist />
    </AppStateProvider>,
  );
  return server;
}

it("mostra os itens na ordem do servidor, com o método de cada um", async () => {
  montar({});
  expect(await screen.findByText("Semana 2 do plano")).toBeInTheDocument();
  const titulos = screen.getAllByRole("checkbox").map((caixa) => caixa.id);
  expect(titulos).toEqual(["semana-revisao", "semana-quiz:n1", "semana-feynman:n1"]);
  expect(screen.getByText(/1 de 3 feitos/)).toBeInTheDocument();
  expect(screen.getAllByText("Recordação ativa").length).toBeGreaterThan(0);
});

it("marcar grava no servidor", async () => {
  const server = montar({
    "PATCH /plan/week/items": () => ({
      body: { item: {}, resumo: { total: 3, feitos: 2, minutos: 45, minutos_feitos: 30 } },
    }),
  });
  await userEvent.click(await screen.findByRole("checkbox", { name: "Quiz de React" }));
  const chamada = server.calls.find((c) => c.method === "PATCH");
  expect(chamada?.url).toContain("/plan/week/items/quiz%3An1");
  expect(chamada?.body).toEqual({ feito: true });
  expect(await screen.findByText(/2 de 3 feitos/)).toBeInTheDocument();
});

it("o que o banco confirmou não se desmarca", async () => {
  montar({});
  const caixa = await screen.findByRole("checkbox", { name: "Explicar React com suas palavras" });
  expect(caixa).toBeChecked();
  expect(caixa).toBeDisabled();
  expect(screen.getByText(/confirmado pelo que você fez/)).toBeInTheDocument();
});

it("falha ao gravar devolve a caixa ao estado real", async () => {
  montar({
    "PATCH /plan/week/items": () => ({ status: 500, body: { detail: "Não deu para salvar." } }),
  });
  const caixa = await screen.findByRole("checkbox", { name: "Quiz de React" });
  await userEvent.click(caixa);
  expect(await screen.findByRole("alert")).toHaveTextContent("Não deu para salvar.");
  expect(caixa).not.toBeChecked();
});
