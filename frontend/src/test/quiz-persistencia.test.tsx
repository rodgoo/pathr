/**
 * O quiz que não recomeça: a aba parte do SERVIDOR, e não do navegador.
 *
 * O relato: "sair e voltar para a aba Quiz recomeça o quiz, não mostra histórico". A causa era o quiz gerado e as
 * respostas viverem só no `localStorage` (limpeza de dados, aba anônima, outro aparelho e qualquer falha os
 * levavam) e a correção só existir na tela do momento do envio. Estes testes seguram o contrário: o que o
 * servidor diz que está aberto é retomado, o que foi enviado aparece no histórico e reabre a correção.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuizTab } from "@/components/quiz/QuizTab";
import { AppStateProvider } from "@/hooks/useAppState";
import type { Quiz, QuizHistoricoItem, QuizResult, RoadmapNode } from "@/api/types";
import { mockServer } from "./server";

const node: RoadmapNode = {
  id: "n-1",
  title: "Docker",
  description: null,
  kind: "skill",
  status: "doing",
  progress_pct: 0,
  level: null,
  estimated_hours: 4,
  week_start: 1,
  week_end: 2,
  tag_ids: ["t-docker"],
  objectives: [],
  order_index: 0,
};

const pergunta = (id: string, prompt: string, ordem: number) => ({
  id,
  prompt,
  code_snippet: null,
  code_language: null,
  options: [`${prompt} A`, `${prompt} B`],
  difficulty: "medio",
  order_index: ordem,
});

const quiz: Quiz = {
  id: "q-1",
  title: "Quiz de Docker",
  kind: "practice",
  difficulty: "medio",
  question_count: 3,
  tag_ids: ["t-docker"],
  questions: [pergunta("a", "Primeira?", 0), pergunta("b", "Segunda?", 1), pergunta("c", "Terceira?", 2)],
};

const historico: QuizHistoricoItem[] = [
  {
    attempt_id: "att-1",
    quiz_id: "q-0",
    title: "Quiz anterior",
    score: 80,
    correct_count: 4,
    total: 5,
    duration_s: 300,
    finished_at: "2026-09-20T13:00:00+00:00",
  },
];

const correcao: { quiz: Quiz; result: QuizResult } = {
  quiz: { ...quiz, id: "q-0" },
  result: {
    attempt_id: "att-1",
    score: 80,
    correct_count: 1,
    total: 3,
    results: [{ question_id: "a", answer: 0, correct_index: 1, is_correct: false, explanation: "Porque o daemon roda em segundo plano." }],
  },
};

const montar = () =>
  render(
    <AppStateProvider>
      <QuizTab node={node} />
    </AppStateProvider>,
  );

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("retomar o quiz aberto", () => {
  it("volta na questão e com as respostas de onde a pessoa parou, vindas do servidor", async () => {
    const servidor = mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz, rascunho: { index: 1, answers: { a: 0 } } } }),
      "GET /quizzes/historico": () => ({ body: [] }),
    });

    montar();

    expect(await screen.findByText("Pergunta 2 de 3")).toBeInTheDocument();
    expect(screen.getByText("Segunda?")).toBeInTheDocument();
    expect(screen.getByText("1 respondidas")).toBeInTheDocument();
    expect(screen.getByText("Continuando de onde você parou.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Começar quiz" })).not.toBeInTheDocument();
    expect(servidor.calls.some((c) => c.url === "/quizzes/em-andamento?node_id=n-1")).toBe(true);
    expect(servidor.calls.some((c) => c.method === "POST" && c.url.startsWith("/quizzes/generate"))).toBe(false);
  });

  it("funciona sem nenhuma cópia no navegador (dados limpos, aba anônima, outro aparelho)", async () => {
    mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz, rascunho: null } }),
      "GET /quizzes/historico": () => ({ body: [] }),
    });
    expect(window.localStorage.length).toBe(0);

    montar();

    expect(await screen.findByText("Pergunta 1 de 3")).toBeInTheDocument();
  });

  it("grava no servidor onde a pessoa parou, depois de responder", async () => {
    const servidor = mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz, rascunho: null } }),
      "GET /quizzes/historico": () => ({ body: [] }),
      "PUT /quizzes/q-1/rascunho": () => ({ body: { salvo: true } }),
    });
    montar();
    await screen.findByText("Pergunta 1 de 3");

    fireEvent.click(screen.getByText("Primeira? B"));

    await waitFor(
      () => {
        const gravacao = servidor.calls.find((c) => c.method === "PUT" && c.url === "/quizzes/q-1/rascunho");
        expect(gravacao?.body).toEqual({ index: 0, answers: { a: 1 } });
      },
      { timeout: 3000 },
    );
  });

  it("sem servidor, cai na cópia do navegador em vez de recomeçar", async () => {
    window.localStorage.setItem("pathr:quiz-aberto:n-1", JSON.stringify(quiz));
    mockServer({
      "GET /quizzes/em-andamento": () => ({ status: 500, body: { detail: "fora do ar" } }),
      "GET /quizzes/historico": () => ({ body: [] }),
    });

    montar();

    expect(await screen.findByText("Pergunta 1 de 3")).toBeInTheDocument();
  });

  it("se o servidor diz que não há quiz aberto, a cópia antiga do navegador é descartada", async () => {
    window.localStorage.setItem("pathr:quiz-aberto:n-1", JSON.stringify(quiz));
    mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz: null, rascunho: null } }),
      "GET /quizzes/historico": () => ({ body: [] }),
    });

    montar();

    expect(await screen.findByRole("button", { name: "Começar quiz" })).toBeInTheDocument();
    expect(window.localStorage.getItem("pathr:quiz-aberto:n-1")).toBeNull();
  });
});

describe("histórico do módulo", () => {
  it("lista as tentativas enviadas ao lado do botão de começar", async () => {
    mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz: null, rascunho: null } }),
      "GET /quizzes/historico": () => ({ body: historico }),
    });

    montar();

    expect(await screen.findByText("Histórico deste módulo")).toBeInTheDocument();
    expect(await screen.findByText("80%")).toBeInTheDocument();
    expect(screen.getByText("4 de 5 certas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Começar quiz" })).toBeInTheDocument();
  });

  it("diz que ainda não há tentativas, em vez de mostrar uma lista vazia", async () => {
    mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz: null, rascunho: null } }),
      "GET /quizzes/historico": () => ({ body: [] }),
    });

    montar();

    expect(await screen.findByText("Você ainda não enviou nenhum quiz neste módulo.")).toBeInTheDocument();
  });

  it("'Ver correção' reabre a tentativa com o gabarito e a explicação, e dá para voltar", async () => {
    const servidor = mockServer({
      "GET /quizzes/em-andamento": () => ({ body: { quiz: null, rascunho: null } }),
      "GET /quizzes/historico": () => ({ body: historico }),
      "GET /quizzes/tentativas/att-1": () => ({ body: correcao }),
    });
    montar();

    fireEvent.click(await screen.findByRole("button", { name: "Ver correção" }));

    expect(await screen.findByText("Porque o daemon roda em segundo plano.")).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.url === "/quizzes/tentativas/att-1")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Voltar ao histórico" }));
    expect(await screen.findByText("Histórico deste módulo")).toBeInTheDocument();
  });
});
