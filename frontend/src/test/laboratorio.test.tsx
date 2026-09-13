/**
 * Laboratório de código: só as linguagens do perfil, e sugestões que geram o
 * exemplo com um clique.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Walkthrough } from "@/api/types";
import { AppStateProvider } from "@/hooks/useAppState";
import { CodeLabPage } from "@/pages/CodeLabPage";
import { mockServer } from "./server";

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

const paraMim = {
  do_perfil: true,
  linguagens: [
    { id: "java", rotulo: "Java", realce: "java" },
    { id: "sql", rotulo: "SQL", realce: "sql" },
  ],
  sugestoes: [
    {
      language: "java",
      language_label: "Java",
      topic: "Spring Boot Fundamentals: Criar um projeto",
      level: "iniciante",
      motivo: "Próximo no seu roadmap: Spring Boot Fundamentals",
      origem: "roadmap",
    },
    {
      language: "sql",
      language_label: "SQL",
      topic: "INNER JOIN e LEFT JOIN",
      level: "intermediario",
      motivo: "Próximo passo em SQL",
      origem: "proximo_nivel",
    },
  ],
};

const gerado: Walkthrough = {
  id: "w1",
  language: "sql",
  language_label: "SQL",
  highlight: "sql",
  topic: "INNER JOIN e LEFT JOIN",
  level: "intermediario",
  title: "Juntando pedidos e clientes",
  summary: "",
  code: "SELECT 1;",
  lines: ["SELECT 1;"],
  steps: [{ linha: 1, acao: "seleciona 1", estado: [], saida: "" }],
  concepts: [],
  created_at: null,
};

function monta(resposta: unknown = paraMim) {
  // Como o servidor: depois de gerar, a lista traz o exemplo novo.
  const guardados: Walkthrough[] = [];
  const servidor = mockServer({
    "GET /walkthroughs/para-mim": () => ({ body: resposta }),
    "GET /walkthroughs": () => ({ body: guardados }),
    "POST /walkthroughs": () => {
      guardados.push(gerado);
      return { status: 201, body: gerado };
    },
  });
  return {
    servidor,
    user: userEvent.setup(),
    ...render(
      <AppStateProvider>
        <CodeLabPage />
      </AppStateProvider>,
    ),
  };
}

describe("laboratório de código", () => {
  it("o gerador oferece só as linguagens do perfil", async () => {
    const { user } = monta();
    const seletor = await screen.findByLabelText("Linguagem do seu perfil");
    await user.click(seletor);
    const opcoes = screen.getAllByRole("option").map((o) => o.textContent);
    expect(opcoes).toEqual(["Java", "SQL"]);
  });

  it("mostra várias sugestões com o motivo, e uma gera o exemplo no nível dela", async () => {
    const { user, servidor } = monta();
    expect(await screen.findByText("Próximo no seu roadmap: Spring Boot Fundamentals")).toBeInTheDocument();
    expect(screen.getByText("Próximo passo em SQL")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Gerar exemplo: INNER JOIN e LEFT JOIN em SQL" }));
    expect(await screen.findByText("Juntando pedidos e clientes")).toBeInTheDocument();
    expect(servidor.calls.find((c) => c.method === "POST")?.body).toEqual({
      language: "sql",
      topic: "INNER JOIN e LEFT JOIN",
      level: "intermediario",
    });
  });

  it("sem linguagem no perfil, manda escolher", async () => {
    monta({ ...paraMim, do_perfil: false, sugestoes: [] });
    expect(await screen.findByText("Marque as linguagens que você estuda")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Escolher linguagens" })).toBeInTheDocument();
  });
});
