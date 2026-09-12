/**
 * Tocar numa palavra que não se sabe.
 *
 * No nivelamento, travar numa palavra faz o item medir vocabulário quando
 * queria medir compreensão — e a saída de quem não sabe é chutar, o que
 * estraga a medição dos dois lados.
 *
 * O que estes testes seguram é que consultar RESPONDE e REGISTRA: a tradução
 * e os sinônimos aparecem embaixo da palavra, e a mesma ação diz ao servidor
 * que aquela palavra ainda não está sabida.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TextoConsultavel } from "@/components/english/TextoConsultavel";
import { mockServer } from "./server";

afterEach(() => {
  vi.unstubAllGlobals();
});

const significado = {
  term: "deploy",
  translation: "implantar",
  synonyms: ["release", "ship", "roll out"],
  definition: "Colocar uma versão do software no ar.",
  example: "We deploy every Friday.",
  phonetic: "/dɪˈplɔɪ/",
  cefr_band: "B2",
  card: { id: "v1", due_at: "2026-09-11T00:00:00Z" },
};

it("mostra tradução e sinônimos ao tocar na palavra", async () => {
  mockServer({ "POST /languages/lookup": () => ({ body: significado }) });
  render(<TextoConsultavel texto="We deploy on Friday." />);

  fireEvent.click(screen.getByRole("button", { name: 'Consultar "deploy"' }));

  expect(await screen.findByText("implantar")).toBeInTheDocument();
  expect(screen.getByText("sinônimos: release, ship, roll out")).toBeInTheDocument();
  expect(screen.getByText("Colocar uma versão do software no ar.")).toBeInTheDocument();
});

it("manda a frase junto, para a acepção ser a que cabe ali", async () => {
  const servidor = mockServer({ "POST /languages/lookup": () => ({ body: significado }) });
  render(<TextoConsultavel texto="We deploy on Friday." idioma="en" />);

  fireEvent.click(screen.getByRole("button", { name: 'Consultar "deploy"' }));

  await waitFor(() => expect(servidor.calls.length).toBeGreaterThan(0));
  expect(servidor.calls[0].body).toEqual({
    term: "deploy",
    language: "en",
    context: "We deploy on Friday.",
  });
});

/**
 * A consulta é evidência: é a única vez em que a pessoa diz, sem ser
 * perguntada, "esta eu não tenho". A tela precisa deixar isso visível — senão
 * olhar uma palavra parece um dicionário à parte, e não o app aprendendo.
 */
it("diz que a palavra entrou na revisão", async () => {
  mockServer({ "POST /languages/lookup": () => ({ body: significado }) });
  render(<TextoConsultavel texto="We deploy on Friday." />);

  fireEvent.click(screen.getByRole("button", { name: 'Consultar "deploy"' }));

  expect(
    await screen.findByText("Entrou na sua revisão de vocabulário para hoje."),
  ).toBeInTheDocument();
});

it("uma consulta que falha não trava o item", async () => {
  mockServer({
    "POST /languages/lookup": () => ({ status: 503, body: { detail: "Não consegui consultar esta palavra agora." } }),
  });
  render(<TextoConsultavel texto="We deploy on Friday." />);

  fireEvent.click(screen.getByRole("button", { name: 'Consultar "deploy"' }));

  expect(await screen.findByText("Não consegui consultar esta palavra agora.")).toBeInTheDocument();
  // A palavra continua lá, e o resto do enunciado também.
  expect(screen.getByRole("button", { name: 'Consultar "Friday"' })).toBeInTheDocument();
});

it("tocar na mesma palavra de novo fecha a consulta", async () => {
  mockServer({ "POST /languages/lookup": () => ({ body: significado }) });
  render(<TextoConsultavel texto="We deploy on Friday." />);
  const palavra = screen.getByRole("button", { name: 'Consultar "deploy"' });

  fireEvent.click(palavra);
  expect(await screen.findByText("implantar")).toBeInTheDocument();

  fireEvent.click(palavra);
  await waitFor(() => expect(screen.queryByText("implantar")).not.toBeInTheDocument());
});
