/**
 * A Biblioteca: a busca sempre ao alcance, e o vazio que diz a verdade.
 *
 * Os dois defeitos que estes testes seguram: o botão "Procurar material" só
 * existia com a lista vazia e sem filtro — e como o idioma contava como
 * filtro, quem usava "Português" nunca o via. E com "Português" a tela dizia
 * "nada encontrado" mesmo havendo documentação em inglês.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AppStateProvider } from "@/hooks/useAppState";
import { LibraryPage } from "@/pages/LibraryPage";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

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
};

function montar() {
  render(
    <AppStateProvider>
      <LibraryPage />
    </AppStateProvider>,
  );
}

it("o botão de busca existe mesmo com a lista cheia", async () => {
  mockServer({ "GET /library": () => ({ body: [doc] }) });
  montar();
  expect(await screen.findByText("Docker docs")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Procurar material/ })).toBeInTheDocument();
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
