/**
 * Laboratório de código: só as linguagens do perfil, e sugestões que geram o
 * exemplo com um clique.
 */

import { render, screen, within } from "@testing-library/react";
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
    { id: "auto", rotulo: "Automático (pelo assunto)", realce: "text" },
    { id: "java", rotulo: "Java", realce: "java" },
    { id: "sql", rotulo: "SQL", realce: "sql" },
    { id: "yaml", rotulo: "YAML (GitHub Actions, Compose, Kubernetes)", realce: "yaml" },
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
  files: [{ caminho: "consulta.sql", linguagem: "sql", rotulo: "SQL", realce: "sql", linhas: ["SELECT 1;"] }],
  steps: [{ arquivo: "consulta.sql", linha: 1, acao: "seleciona 1", estado: [], saida: "" }],
  concepts: [],
  created_at: null,
};

const WORKFLOW = [
  "name: CI",
  "on:",
  "  push:",
  "jobs:",
  "  testes:",
  "    runs-on: ubuntu-latest",
  "    steps:",
  "      - uses: actions/checkout@v4",
  "      - run: mvn -B test",
];
const TESTE = ["package com.exemplo;", "", "class SomaTest {", "  @Test void soma() { assertEquals(4, 2 + 2); }", "}"];

const doGithub: Walkthrough = {
  ...gerado,
  id: "w2",
  language: "yaml",
  language_label: "YAML (GitHub Actions, Compose, Kubernetes)",
  highlight: "yaml",
  topic: "GitHub e testes automatizados",
  title: "Testes rodando no GitHub Actions",
  code: WORKFLOW.join("\n"),
  lines: WORKFLOW,
  files: [
    { caminho: ".github/workflows/ci.yml", linguagem: "yaml", rotulo: "YAML", realce: "yaml", linhas: WORKFLOW },
    { caminho: "src/test/java/com/exemplo/SomaTest.java", linguagem: "java", rotulo: "Java", realce: "java", linhas: TESTE },
  ],
  steps: [
    { arquivo: ".github/workflows/ci.yml", linha: 9, acao: "o runner roda mvn -B test", estado: [], saida: "[INFO] Running com.exemplo.SomaTest" },
    { arquivo: "src/test/java/com/exemplo/SomaTest.java", linha: 4, acao: "assertEquals(4, 4) passa", estado: [], saida: "Tests run: 1, Failures: 0" },
  ],
};

function monta(resposta: unknown = paraMim, iniciais: Walkthrough[] = []) {
  // Como o servidor: depois de gerar, a lista traz o exemplo novo.
  const guardados: Walkthrough[] = [...iniciais];
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
  it("o gerador começa no automático e oferece as linguagens do perfil e os arquivos de ferramenta", async () => {
    const { user, servidor } = monta();
    const seletor = await screen.findByLabelText("Linguagem ou arquivo");
    await user.click(seletor);
    const opcoes = screen.getAllByRole("option").map((o) => o.textContent);
    expect(opcoes).toEqual(["Automático (pelo assunto)", "Java", "SQL", "YAML (GitHub Actions, Compose, Kubernetes)"]);
    await user.keyboard("{Escape}");

    await user.type(screen.getByPlaceholderText(/GitHub Actions rodando os testes/), "GitHub e testes automatizados");
    await user.click(screen.getByRole("button", { name: /Gerar exemplo$/ }));
    await screen.findByText("Juntando pedidos e clientes");
    expect(servidor.calls.find((c) => c.method === "POST")?.body).toEqual({
      language: "auto",
      topic: "GitHub e testes automatizados",
      level: "iniciante",
    });
  });

  it("exemplo com vários arquivos: a aba acompanha o arquivo onde o passo acontece", async () => {
    window.localStorage.setItem("pathr:codigo", JSON.stringify({ id: "w2", passo: 0 }));
    const { user } = monta(paraMim, [doGithub]);

    const abas = await screen.findByRole("tablist", { name: "Arquivos do exemplo" });
    const [workflow, teste] = within(abas).getAllByRole("tab");
    expect(workflow).toHaveTextContent("ci.yml");
    expect(workflow).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Arquivo .github/workflows/ci.yml")).toHaveTextContent("mvn -B test");

    await user.click(screen.getByRole("button", { name: "Próximo passo" }));
    expect(teste).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Arquivo src/test/java/com/exemplo/SomaTest.java")).toHaveTextContent("assertEquals(4, 2 + 2)");
    expect(screen.getByText("SomaTest.java · linha 4")).toBeInTheDocument();
    expect(screen.getByText(/Tests run: 1, Failures: 0/)).toBeInTheDocument();

    // Dá para olhar outro arquivo; o passo seguinte traz de volta.
    await user.click(workflow);
    expect(workflow).toHaveAttribute("aria-selected", "true");
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
