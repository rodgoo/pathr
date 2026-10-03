/**
 * O áudio do listening: uma voz tocando em cima da outra.
 *
 * O relato: ao avançar de pergunta enquanto o áudio neural da pergunta
 * anterior ainda estava sendo preparado, a voz antiga chegava do servidor
 * DEPOIS da troca e tocava por cima do diálogo novo. A causa: o efeito que
 * reage à mudança de `contexto` parava o som ATUAL, mas não avisava um
 * `tocar()` ainda em voo (via `audiosDasFalas`) que devia desistir — só o
 * desmonte do componente fazia isso.
 *
 * Também cobre o aviso de "Preparando o áudio…": antes só existia como
 * `title`/`aria-label` do botão, invisível sem passar o mouse — e a geração
 * de voz neural é lenta o bastante para parecer que o clique não funcionou.
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ListeningPlayer } from "@/components/english/ListeningPlayer";

const audiosDasFalas = vi.fn();
vi.mock("@/lib/vozNeural", () => ({ audiosDasFalas: (...args: unknown[]) => audiosDasFalas(...args) }));

/** Um `<audio>` de mentira, só o bastante para a reprodução em sequência. */
function audioFalso() {
  const el = {
    play: vi.fn(() => Promise.resolve()),
    pause: vi.fn(),
    onended: null as null | (() => void),
  };
  return el as unknown as HTMLAudioElement;
}

beforeEach(() => {
  audiosDasFalas.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("troca de pergunta cancela o áudio que ainda estava sendo preparado, em vez de tocar por cima do novo", async () => {
  let resolverPerguntaA: (audios: HTMLAudioElement[]) => void;
  const esperaA = new Promise<HTMLAudioElement[]>((resolve) => {
    resolverPerguntaA = resolve;
  });
  const audioA = audioFalso();
  const audioB = audioFalso();

  audiosDasFalas.mockReturnValueOnce(esperaA).mockReturnValueOnce(Promise.resolve([audioB]));

  const { rerender } = render(<ListeningPlayer contexto="Ana: First question." idioma="en" />);

  fireEvent.click(screen.getByRole("button", { name: /ouvir o diálogo/i }));
  await screen.findByText("Preparando o áudio…");

  // Avança para a próxima pergunta ENQUANTO o áudio da primeira ainda não
  // chegou — é o que o relato descreve.
  rerender(<ListeningPlayer contexto="Marc: Second question." idioma="en" />);

  // A pergunta nova toca normalmente.
  fireEvent.click(screen.getByRole("button", { name: /ouvir o diálogo/i }));
  await act(async () => {});
  expect(audioB.play).toHaveBeenCalledTimes(1);

  // O áudio da primeira pergunta chega só agora, tarde — e não pode tocar.
  await act(async () => {
    resolverPerguntaA([audioA]);
    await esperaA;
  });
  expect(audioA.play).not.toHaveBeenCalled();
});

it("mostra 'Preparando o áudio…' na tela enquanto a voz neural está sendo gerada, não só no title do botão", async () => {
  let resolver: (audios: HTMLAudioElement[]) => void;
  const espera = new Promise<HTMLAudioElement[]>((resolve) => {
    resolver = resolve;
  });
  audiosDasFalas.mockReturnValueOnce(espera);

  render(<ListeningPlayer contexto="Ana: Where is the station?" idioma="en" />);

  expect(screen.queryByText("Preparando o áudio…")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /ouvir o diálogo/i }));

  expect(await screen.findByText("Preparando o áudio…")).toBeInTheDocument();

  await act(async () => {
    resolver([audioFalso()]);
    await espera;
  });
  expect(screen.queryByText("Preparando o áudio…")).not.toBeInTheDocument();
});
