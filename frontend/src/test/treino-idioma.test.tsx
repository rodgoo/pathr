/**
 * O treino diário de idioma na tela.
 *
 * O que estes testes seguram é o que a pessoa faz com as mãos em cada formato
 * — e o que a tela NÃO pode fazer: mostrar o texto do ditado antes da
 * correção, contar como erro a fala de quem estava sem microfone, e desenhar
 * porcentagem como se fosse nível.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import type { PracticeAnswerResult, PracticeItem, PracticeSession, SkillBoard } from "@/api/types";
import { QuadroDeHabilidades } from "@/components/english/QuadroDeHabilidades";
import { TreinoDoDia } from "@/components/english/treino/TreinoDoDia";
import { mockServer } from "./server";

function sessao(items: PracticeItem[], extra: Partial<PracticeSession> = {}): PracticeSession {
  return {
    id: "s1",
    language: "en",
    practice_day: "2026-09-12",
    status: "active",
    total: items.length,
    answered: 0,
    correct: 0,
    generating: false,
    items,
    summary: null,
    ...extra,
  };
}

function item(
  type: PracticeItem["type"],
  payload: PracticeItem["payload"],
  extra: Partial<PracticeItem> = {},
): PracticeItem {
  return {
    id: `i-${type}`,
    type,
    skill: "grammar",
    topic: "preposições",
    band: "B1",
    origin: "novo",
    payload,
    ...extra,
  };
}

function resultado(
  extra: Partial<PracticeAnswerResult>,
  proxima: PracticeSession,
): PracticeAnswerResult {
  return {
    is_correct: true,
    skipped: false,
    correct_answer: null,
    detail: null,
    explanation: "Porque discuss não leva about.",
    improvement: null,
    session: proxima,
    ...extra,
  };
}

const semNada = () => {};

it("montar a frase envia as palavras na ordem tocada, e só quando completa", async () => {
  const usuario = userEvent.setup();
  const montar = item("reorder", {
    enunciado: "Monte a frase",
    pecas: ["later", "I", "call"],
    traducao: "Eu ligo depois",
  });
  const servidor = mockServer({
    "POST /languages/practice/s1/answer": () => ({
      body: resultado({}, sessao([], { answered: 1, total: 1 })),
    }),
  });
  render(<TreinoDoDia inicial={sessao([montar])} idioma="en" onSair={semNada} />);

  const conferir = screen.getByRole("button", { name: "Conferir" });
  expect(conferir).toBeDisabled();
  await usuario.click(screen.getByRole("button", { name: "I" }));
  await usuario.click(screen.getByRole("button", { name: "call" }));
  await usuario.click(screen.getByRole("button", { name: "later" }));
  expect(conferir).toBeEnabled();
  await usuario.click(conferir);

  const envio = servidor.calls.find((c) => c.method === "POST");
  expect(envio?.body).toEqual({ item_id: "i-reorder", answer: { tokens: ["I", "call", "later"] } });
});

it("associar pares envia qual termo foi ligado a qual tradução", async () => {
  const usuario = userEvent.setup();
  const pares = item("match", {
    enunciado: "Associe",
    esquerda: ["meeting", "deadline"],
    direita: ["prazo", "reunião"],
  });
  const servidor = mockServer({
    "POST /languages/practice/s1/answer": () => ({ body: resultado({}, sessao([], { answered: 1 })) }),
  });
  render(<TreinoDoDia inicial={sessao([pares])} idioma="en" onSair={semNada} />);

  await usuario.click(screen.getByRole("button", { name: "meeting" }));
  await usuario.click(screen.getByRole("button", { name: "reunião" }));
  await usuario.click(screen.getByRole("button", { name: "deadline" }));
  await usuario.click(screen.getByRole("button", { name: "prazo" }));
  await usuario.click(screen.getByRole("button", { name: "Conferir" }));

  const envio = servidor.calls.find((c) => c.method === "POST");
  expect(envio?.body).toEqual({ item_id: "i-match", answer: { pares: { "0": 1, "1": 0 } } });
});

it("o ditado não mostra o texto antes da correção", async () => {
  const usuario = userEvent.setup();
  const ditado = item(
    "dictation",
    { enunciado: "Escreva o que ouvir", audio: "The deploy finished five minutes ago" },
    { skill: "listening" },
  );
  mockServer({
    "POST /languages/practice/s1/answer": () => ({
      body: resultado(
        {
          is_correct: false,
          correct_answer: "The deploy finished five minutes ago",
          detail: { semelhanca: 0.5, faltaram: ["finished", "five"] },
          improvement: "novo_ponto",
        },
        sessao([], { answered: 1 }),
      ),
    }),
  });
  render(<TreinoDoDia inicial={sessao([ditado])} idioma="en" onSair={semNada} />);

  expect(screen.queryByText(/The deploy finished/)).not.toBeInTheDocument();
  await usuario.type(screen.getByLabelText("O que você ouviu"), "The deploy is done");
  await usuario.click(screen.getByRole("button", { name: "Conferir" }));

  expect(await screen.findByText("The deploy finished five minutes ago")).toBeInTheDocument();
  expect(screen.getByText("finished")).toBeInTheDocument();
  // A reciclagem é dita, não escondida.
  expect(screen.getByText(/volta nos próximos treinos, com outras palavras/)).toBeInTheDocument();
});

it("fala sem microfone é pulo, não erro", async () => {
  const usuario = userEvent.setup();
  const fala = item(
    "speaking",
    { enunciado: "Leia em voz alta", texto: "I will send the report tomorrow" },
    { skill: "speaking" },
  );
  const servidor = mockServer({
    "POST /languages/practice/s1/answer": () => ({
      body: resultado({ is_correct: false, skipped: true }, sessao([], { answered: 1 })),
    }),
  });
  render(<TreinoDoDia inicial={sessao([fala])} idioma="en" onSair={semNada} />);

  await usuario.click(screen.getByRole("button", { name: "Não posso falar agora" }));
  expect(servidor.calls.find((c) => c.method === "POST")?.body).toEqual({
    item_id: "i-speaking",
    answer: { texto: "" },
  });
  expect(await screen.findByText(/Pulado — não conta como erro/)).toBeInTheDocument();
  expect(screen.queryByText("Ainda não.")).not.toBeInTheDocument();
});

it("mostra a imagem, a origem da revisão e a explicação da correção", async () => {
  const usuario = userEvent.setup();
  const imagem = item(
    "image",
    {
      enunciado: "Qual é a palavra?",
      emoji: "🧳",
      alternativas: ["backpack", "suitcase", "locker", "handbag"],
    },
    { origin: "revisao", skill: "vocabulary", topic: "viagens e deslocamento" },
  );
  const seguinte = item("mcq", { enunciado: "Choose", alternativas: ["a", "b", "c", "d"] }, { id: "i-2" });
  mockServer({
    "POST /languages/practice/s1/answer": () => ({
      body: resultado(
        { correct_answer: "suitcase", improvement: "subiu" },
        sessao([seguinte], { answered: 1, total: 2 }),
      ),
    }),
  });
  render(<TreinoDoDia inicial={sessao([imagem, seguinte], { total: 2 })} idioma="en" onSair={semNada} />);

  expect(screen.getByRole("img", { name: "Imagem do exercício" })).toHaveTextContent("🧳");
  expect(screen.getByText("Revisão do que você errou")).toBeInTheDocument();
  await usuario.click(screen.getByRole("button", { name: /suitcase/ }));

  expect(await screen.findByText("Porque discuss não leva about.")).toBeInTheDocument();
  expect(screen.getByText(/num formato mais exigente/)).toBeInTheDocument();
  await usuario.click(screen.getByRole("button", { name: "Continuar" }));
  expect(await screen.findByText("Choose")).toBeInTheDocument();
  expect(screen.getByText("1 de 2")).toBeInTheDocument();
});

it("ao terminar, mostra o resumo com os pontos recuperados e cada tópico", () => {
  const feito = sessao([], {
    status: "done",
    answered: 3,
    total: 3,
    summary: {
      correct: 2,
      answered: 3,
      reviewed: 2,
      recovered: 1,
      levels: [{ skill: "listening", before: "A2", after: "B1", delta: 0.6 }],
      topics: [
        { skill: "grammar", topic: "preposições", answered: 2, correct: 1 },
        { skill: "listening", topic: "números e datas", answered: 1, correct: 1 },
      ],
    },
  });
  mockServer({});
  render(<TreinoDoDia inicial={feito} idioma="en" onSair={semNada} />);

  expect(screen.getByText("2/3")).toBeInTheDocument();
  expect(screen.getByText(/recuperou 1 de 2 pontos de melhora/)).toBeInTheDocument();
  expect(screen.getByText("B1")).toBeInTheDocument();
  expect(screen.getByText("preposições")).toBeInTheDocument();
  expect(screen.getByText("1 de 2")).toBeInTheDocument();
});

// --- o quadro por habilidade ----------------------------------------------------

const quadro: SkillBoard = {
  overall: {
    level: "B1",
    theta: 2.6,
    progress_in_band: 0.6,
    uncertainty: 0.4,
    confidence: "media",
    answered: 24,
  },
  skills: [
    {
      skill: "business",
      level: "B1",
      theta: 2.4,
      progress_in_band: 0.4,
      uncertainty: 0.9,
      confidence: "inicial",
      answered: 2,
      topics: [
        { topic: "negociação", answered: 2, correct: 2, score: 75, status: "progredindo", last_seen: null },
      ],
    },
    {
      skill: "grammar",
      level: "B1",
      theta: 2.3,
      progress_in_band: 0.3,
      uncertainty: 0.5,
      confidence: "media",
      answered: 9,
      topics: [
        { topic: "preposições", answered: 4, correct: 1, score: 33, status: "reforcar", last_seen: null },
        { topic: "tempos do passado", answered: 5, correct: 5, score: 86, status: "dominado", last_seen: null },
      ],
    },
    {
      skill: "speaking",
      level: null,
      theta: 2.5,
      progress_in_band: 0.5,
      uncertainty: 1.6,
      confidence: "sem_dados",
      answered: 0,
      topics: [],
    },
  ],
};

it("o quadro mostra nível e confiança, nunca porcentagem de acerto", () => {
  render(<QuadroDeHabilidades quadro={quadro} />);
  // O caso real: duas perguntas certas viravam "Corporativo: 100%".
  expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  const corporativo = screen.getByRole("button", { name: /Corporativo/ });
  expect(within(corporativo).getByText("B1")).toBeInTheDocument();
  expect(within(corporativo).getByText(/estimativa inicial/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Fala/ })).toHaveTextContent("sem respostas ainda");
});

it("abrir uma habilidade mostra cada tópico com acertos e situação", async () => {
  const usuario = userEvent.setup();
  render(<QuadroDeHabilidades quadro={quadro} />);
  const gramatica = screen.getByRole("button", { name: /Gramática/ });
  expect(gramatica).toHaveTextContent("1 tópico a reforçar");

  await usuario.click(gramatica);
  expect(screen.getByText("preposições")).toBeInTheDocument();
  expect(screen.getByText("a reforçar")).toBeInTheDocument();
  expect(screen.getByText("1 de 4")).toBeInTheDocument();
  expect(screen.getByText("dominado")).toBeInTheDocument();
});
