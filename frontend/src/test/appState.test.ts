/**
 * O reducer de interface.
 *
 * Ficou pequeno depois que os dados saíram para o servidor, mas as
 * transições que sobraram são as que acoplam telas — e é exatamente por isso
 * que valem teste sem montar componente.
 */

import { describe, expect, it } from "vitest";
import { INITIAL_STATE, reducer, type Action, type AppState } from "@/hooks/appState";

const run = (actions: Action[], from: AppState = INITIAL_STATE) => actions.reduce(reducer, from);

describe("navegação", () => {
  it("leva a aba do módulo quando o atalho a nomeia", () => {
    const state = reducer(INITIAL_STATE, { type: "navigate", screen: "modulo", moduleTab: "quiz" });
    expect(state.screen).toBe("modulo");
    expect(state.moduleTab).toBe("quiz");
  });

  it("preserva a aba quando o atalho não a nomeia", () => {
    const state = run([
      { type: "setModuleTab", tab: "atividade" },
      { type: "navigate", screen: "modulo" },
    ]);
    expect(state.moduleTab).toBe("atividade");
  });

  it("abre um módulo específico e limpa o quiz anterior", () => {
    const state = run([
      { type: "openQuiz", quizId: "quiz-1" },
      { type: "openNode", nodeId: "node-9" },
    ]);
    expect(state.activeNodeId).toBe("node-9");
    expect(state.activeQuizId).toBeNull();
  });

  it("sair da trilha encerra o quiz em andamento", () => {
    // Voltar depois e reencontrar um quiz pela metade, sem contexto, é pior
    // que recomeçar.
    const state = run([
      { type: "navigate", screen: "modulo" },
      { type: "openQuiz", quizId: "quiz-1" },
      { type: "navigate", screen: "biblioteca" },
    ]);
    expect(state.activeQuizId).toBeNull();
  });

  it("continuar dentro da trilha mantém o quiz aberto", () => {
    const state = run([
      { type: "navigate", screen: "modulo" },
      { type: "openQuiz", quizId: "quiz-1" },
      { type: "navigate", screen: "modulo", moduleTab: "quiz" },
    ]);
    expect(state.activeQuizId).toBe("quiz-1");
  });
});

describe("filtros e buscas", () => {
  it("sobrevivem à troca de tela", () => {
    const state = run([
      { type: "setLibrarySearch", value: "docker" },
      { type: "setLibraryFilter", filter: "video" },
      { type: "navigate", screen: "home" },
      { type: "navigate", screen: "biblioteca" },
    ]);
    expect(state.librarySearch).toBe("docker");
    expect(state.libraryFilter).toBe("video");
  });

  it("o idioma do conteúdo é uma preferência só, compartilhada", () => {
    const state = reducer(INITIAL_STATE, { type: "setContentLang", lang: "en" });
    expect(state.contentLang).toBe("en");
  });
});

describe("estado inicial", () => {
  it("não carrega nenhum dado de domínio", () => {
    // A regressão que este teste protege: o reducer voltar a guardar tags,
    // perfil ou quizzes, criando uma segunda fonte de verdade.
    const keys = Object.keys(INITIAL_STATE);
    expect(keys).not.toContain("tags");
    expect(keys).not.toContain("profile");
    expect(keys).not.toContain("notifications");
  });

  it("abre no painel, sem nada selecionado", () => {
    expect(INITIAL_STATE.screen).toBe("home");
    expect(INITIAL_STATE.activeNodeId).toBeNull();
    expect(INITIAL_STATE.activeQuizId).toBeNull();
    expect(INITIAL_STATE.activeResumeId).toBeNull();
  });
});
