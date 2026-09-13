/**
 * O texto que vai para a síntese de voz.
 *
 * A voz lê literalmente. O que se segura aqui é que a pessoa ouve a frase, e
 * não os símbolos que a tela usa para lacuna e destaque.
 */

import { describe, expect, test } from "vitest";
import { textoParaFala, vozesDoIdioma } from "@/lib/fala";

const voz = (name: string, lang: string) => ({ name, lang }) as SpeechSynthesisVoice;

describe("textoParaFala", () => {
  test("lacuna vira pausa, não 'underscore underscore'", () => {
    expect(textoParaFala("I __ push it after lunch.")).not.toContain("_");
  });

  test("destaque perde os colchetes e fica a palavra", () => {
    expect(textoParaFala("Can you [[clean up]] this?")).toBe("Can you clean up this?");
  });

  test("pronome em minúscula e apóstrofo tipográfico", () => {
    expect(textoParaFala("i’ll push it, and i think i'm done")).toBe("I'll push it, and I think I'm done");
  });

  test("não mexe no 'i' de outras línguas", () => {
    expect(textoParaFala("i ragazzi", "it")).toBe("i ragazzi");
  });
});

describe("vozesDoIdioma", () => {
  test("só vozes do idioma, as neurais primeiro", () => {
    const todas = [
      voz("Microsoft Maria", "pt-BR"),
      voz("Microsoft David", "en-US"),
      voz("Microsoft Aria Online (Natural)", "en-US"),
      voz("Google UK English", "en-GB"),
    ];
    expect(vozesDoIdioma(todas, "en").map((v) => v.name)).toEqual([
      "Microsoft Aria Online (Natural)",
      "Google UK English",
      "Microsoft David",
    ]);
  });

  test("sem voz do idioma, lista vazia — nunca a voz portuguesa lendo inglês", () => {
    expect(vozesDoIdioma([voz("Microsoft Maria", "pt-BR")], "en")).toEqual([]);
  });
});
