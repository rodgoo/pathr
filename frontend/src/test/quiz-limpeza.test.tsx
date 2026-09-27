/**
 * O andamento de quizzes abandonados não se acumula para sempre no navegador.
 *
 * Cada quiz grava `pathr:quiz:<id>` e só o envio apaga a entrada; quem larga
 * quizzes no meio (o normal num app de estudo) deixava uma chave por quiz.
 */

import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { Quiz } from "@/api/types";
import { QuizRunner, limparProgressosAntigos } from "@/components/quiz/QuizRunner";
import { AppStateProvider } from "@/hooks/useAppState";

const DIA = 24 * 60 * 60 * 1000;
const AGORA = Date.UTC(2026, 8, 26, 12);
const guarda = (id: string, extra: object = {}) =>
  window.localStorage.setItem(`pathr:quiz:${id}`, JSON.stringify({ index: 1, answers: { a: 0 }, ...extra }));
const existe = (id: string) => window.localStorage.getItem(`pathr:quiz:${id}`) !== null;

beforeEach(() => window.localStorage.clear());

describe("limparProgressosAntigos", () => {
  it("apaga o que passou de 30 dias e mantém o recente", () => {
    guarda("velho", { at: AGORA - 31 * DIA });
    guarda("recente", { at: AGORA - 2 * DIA });
    limparProgressosAntigos(AGORA);
    expect(existe("velho")).toBe(false);
    expect(existe("recente")).toBe(true);
  });

  it("entrada de versão antiga ganha data em vez de ser apagada na hora", () => {
    guarda("legado");
    limparProgressosAntigos(AGORA);
    expect(existe("legado")).toBe(true);
    expect(JSON.parse(window.localStorage.getItem("pathr:quiz:legado")!).at).toBe(AGORA);
    // ...e expira como as outras, um mês depois.
    limparProgressosAntigos(AGORA + 31 * DIA);
    expect(existe("legado")).toBe(false);
  });

  it("mantém só os 20 mais recentes", () => {
    for (let i = 0; i < 25; i += 1) guarda(`q${i}`, { at: AGORA - i * 1000 });
    limparProgressosAntigos(AGORA);
    expect(existe("q0")).toBe(true);
    expect(existe("q19")).toBe(true);
    expect(existe("q20")).toBe(false);
    expect(existe("q24")).toBe(false);
  });

  it("não mexe em chaves que não são de progresso de quiz", () => {
    window.localStorage.setItem("pathr:quiz-aberto:n-1", "{}");
    window.localStorage.setItem("pathr:idioma", "pt");
    limparProgressosAntigos(AGORA);
    expect(window.localStorage.getItem("pathr:quiz-aberto:n-1")).toBe("{}");
    expect(window.localStorage.getItem("pathr:idioma")).toBe("pt");
  });
});

it("abrir um quiz limpa os abandonados e grava o próprio andamento com data", () => {
  guarda("abandonado", { at: Date.now() - 40 * DIA });
  const quiz: Quiz = {
    id: "atual",
    title: "Docker",
    kind: "module",
    difficulty: "medium",
    question_count: 1,
    tag_ids: [],
    questions: [
      { id: "q1", prompt: "Pergunta?", code_snippet: null, code_language: null, options: ["a", "b"], difficulty: "easy", order_index: 0 },
    ],
  };
  render(
    <AppStateProvider>
      <QuizRunner quiz={quiz} />
    </AppStateProvider>,
  );
  expect(existe("abandonado")).toBe(false);
  expect(typeof JSON.parse(window.localStorage.getItem("pathr:quiz:atual")!).at).toBe("number");
});
