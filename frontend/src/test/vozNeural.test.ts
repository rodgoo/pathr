/**
 * Os áudios de um diálogo, vindos do servidor.
 *
 * Nasceu de um defeito real: o app pedia TODAS as falas de uma vez, o TTS do
 * Gemini recusa pedido simultâneo com 429 mesmo dentro da cota, e uma fala que
 * falha derruba o diálogo inteiro (é tudo ou nada, para o timbre não trocar no
 * meio). Na tela isso virava "apertei ouvir e não saiu som".
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const narrar = vi.fn();
vi.mock("@/api/endpoints", () => ({ languages: { narrar: (...args: unknown[]) => narrar(...args) } }));

let audiosDasFalas: typeof import("@/lib/vozNeural").audiosDasFalas;

/** Quantos pedidos estavam no ar ao mesmo tempo, no pico. */
let simultaneos = 0;
let pico = 0;

beforeEach(async () => {
  vi.resetModules(); // o módulo guarda os áudios já baixados, entre testes
  ({ audiosDasFalas } = await import("@/lib/vozNeural"));
  narrar.mockReset();
  simultaneos = 0;
  pico = 0;
  // `Audio` e `createObjectURL` não existem no jsdom.
  globalThis.URL.createObjectURL = vi.fn(() => "blob:audio");
  vi.stubGlobal("Audio", class {});
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function respondeDevagar() {
  narrar.mockImplementation(async () => {
    simultaneos += 1;
    pico = Math.max(pico, simultaneos);
    await new Promise((resolve) => setTimeout(resolve, 5));
    simultaneos -= 1;
    return new Blob(["audio"]);
  });
}

const FALAS = [
  { texto: "Where is the station?", voz: 0 },
  { texto: "Two blocks from here.", voz: 1 },
  { texto: "Is it far?", voz: 0 },
  { texto: "Five minutes walking.", voz: 1 },
];

describe("áudios do diálogo", () => {
  it("não pede todas as falas de uma vez", async () => {
    respondeDevagar();

    const audios = await audiosDasFalas(FALAS, "en");

    expect(audios).toHaveLength(4);
    expect(narrar).toHaveBeenCalledTimes(4);
    // O pico é o que importa: com as quatro juntas, o provedor recusa uma.
    expect(pico).toBeLessThanOrEqual(2);
  });

  it("uma fala que falha derruba o diálogo — e para de pedir o resto", async () => {
    // A segunda falha; a terceira e a quarta não devem nem ser pedidas, senão
    // o servidor trabalha para um resultado que já será descartado.
    narrar
      .mockResolvedValueOnce(new Blob(["a"]))
      .mockRejectedValueOnce(new Error("503"))
      .mockResolvedValue(new Blob(["c"]));

    expect(await audiosDasFalas(FALAS, "en")).toBeNull();
    expect(narrar).toHaveBeenCalledTimes(2);
  });

  it("o mesmo texto não é baixado duas vezes", async () => {
    narrar.mockResolvedValue(new Blob(["a"]));

    await audiosDasFalas([FALAS[0]], "en");
    await audiosDasFalas([FALAS[0]], "en");

    // Material de escuta se ouve várias vezes; sem o cache, cada clique
    // gastaria uma geração.
    expect(narrar).toHaveBeenCalledTimes(1);
  });

  it("sem falas, não chama o servidor", async () => {
    expect(await audiosDasFalas([], "en")).toBeNull();
    expect(narrar).not.toHaveBeenCalled();
  });
});
