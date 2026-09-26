import { describe, expect, it } from "vitest";

import { formatarMeta } from "@/lib/formatarMeta";

describe("formatarMeta", () => {
  it("o exemplo do relato: iniciais em maiúscula, grafia certa e um resumo curto", () => {
    const meta = formatarMeta("fullstack Java, Typescript, React, tudo de java, testes, Scrum");
    expect(meta.texto).toBe("Fullstack Java · TypeScript · React +3");
    expect(meta.completo).toBe("Fullstack Java, TypeScript, React, Tudo de Java, Testes, Scrum");
  });

  it("cada palavra começa em maiúscula, menos as de ligação no meio do item", () => {
    expect(formatarMeta("engenheiro de software para a nuvem").texto).toBe("Engenheiro de Software para a Nuvem");
  });

  it("a primeira palavra é sempre maiúscula, mesmo sendo de ligação", () => {
    expect(formatarMeta("de frontend a fullstack").texto).toBe("De Frontend a Fullstack");
  });

  it("tecnologias e siglas mantêm a grafia própria", () => {
    expect(formatarMeta("javascript, aws, ci/cd, github, postgresql, node.js").completo).toBe(
      "JavaScript, AWS, CI/CD, GitHub, PostgreSQL, Node.js",
    );
  });

  it("respeita a maiúscula no meio que a pessoa já digitou", () => {
    expect(formatarMeta("OAuth, iPhone").completo).toBe("OAuth, iPhone");
  });

  it("não repete o mesmo item com caixa diferente", () => {
    expect(formatarMeta("java, Java, JAVA, react").completo).toBe("Java, React");
  });

  it("até o limite mostra tudo, sem '+N'", () => {
    expect(formatarMeta("java, react, scrum").texto).toBe("Java · React · Scrum");
  });

  it("aceita ponto e vírgula e quebra de linha como separador", () => {
    expect(formatarMeta("java; react\nscrum").completo).toBe("Java, React, Scrum");
  });

  it("vazio, nulo e só separadores não geram texto", () => {
    expect(formatarMeta("").texto).toBe("");
    expect(formatarMeta(null).texto).toBe("");
    expect(formatarMeta(undefined).texto).toBe("");
    expect(formatarMeta(" , ; ,").texto).toBe("");
  });

  it("uma meta de um item só só é capitalizada", () => {
    expect(formatarMeta("desenvolvedor backend").texto).toBe("Desenvolvedor Backend");
  });
});
