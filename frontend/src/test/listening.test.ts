/**
 * A separacao das falas do dialogo.
 *
 * E o que transforma o texto guardado em audio: cada fala vira uma locucao,
 * com voz propria por interlocutor. Errar aqui faz o dialogo sair na voz
 * errada, ou sair como um paragrafo unico e monotono.
 */

import { describe, expect, test } from "vitest";
import { separarFalas } from "@/components/english/ListeningPlayer";

describe("separarFalas", () => {
  test("separa cada linha em quem fala e o que diz", () => {
    const falas = separarFalas("Ana: I'll push it after lunch.\nMarc: Thanks, I'll review it.");

    expect(falas).toEqual([
      { quem: "Ana", texto: "I'll push it after lunch." },
      { quem: "Marc", texto: "Thanks, I'll review it." },
    ]);
  });

  test("linha sem nome continua a fala anterior", () => {
    // Dialogo real quebra frase em duas linhas. Ler a segunda como fala nova
    // trocaria a voz no meio da frase.
    const falas = separarFalas("Ana: I'll push it after lunch,\nright after the standup.");

    expect(falas).toHaveLength(1);
    expect(falas[0].texto).toBe("I'll push it after lunch, right after the standup.");
  });

  test("ignora linhas em branco", () => {
    expect(separarFalas("Ana: Oi.\n\n\nMarc: Oi.")).toHaveLength(2);
  });

  test("texto sem marcacao de quem fala nao vira dialogo", () => {
    // E a descricao de cena que motivou toda a guarda no servidor: sem falas,
    // nao ha o que reproduzir.
    expect(separarFalas("Daily stand-up meeting on Zoom.")).toEqual([]);
  });

  test("dois-pontos dentro da fala nao quebra a linha", () => {
    const falas = separarFalas("Ana: The rule is simple: never push on Friday.");

    expect(falas).toHaveLength(1);
    expect(falas[0].quem).toBe("Ana");
    expect(falas[0].texto).toBe("The rule is simple: never push on Friday.");
  });
});
