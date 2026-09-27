/**
 * Três filtros pequenos que decidem o que passa por confiável:
 * o escape do gerador de SEO, o reconhecimento de URL do YouTube e a
 * normalização de acentos da busca de cidade.
 */

import { describe, expect, it } from "vitest";
import { normaliza } from "@/components/auth/CidadeDoCadastro";
import { idDoYoutube } from "@/components/library/VideoPlayer";
import { esc, jsonSeguro } from "../../scripts/escape-html.mjs";

describe("esc() do gerador de SEO", () => {
  it("escapa aspas para não quebrar o atributo content=\"...\"", () => {
    const html = `<meta name="description" content="${esc('Aprenda "Java" e o\'s do Spring')}" />`;
    expect(html).toBe(
      '<meta name="description" content="Aprenda &quot;Java&quot; e o&#39;s do Spring" />',
    );
  });

  it("continua escapando &, < e >", () => {
    expect(esc("a & b <c>")).toBe("a &amp; b &lt;c&gt;");
  });
});

describe("JSON-LD do gerador de SEO", () => {
  it("um </script> no texto não encerra o bloco", () => {
    const bloco = jsonSeguro({ text: "veja </script><script>alert(1)</script>" });
    expect(bloco).not.toContain("</script>");
    expect(bloco).not.toContain("<");
    // E continua sendo o mesmo JSON para quem lê.
    expect(JSON.parse(bloco).text).toBe("veja </script><script>alert(1)</script>");
  });

  it("preserva a estrutura e escapa & e separadores de linha do JavaScript", () => {
    const separador = String.fromCharCode(0x2028);
    const valor = { a: ["x & y", `linha${separador}nova`], n: 1 };
    const bloco = jsonSeguro(valor);
    expect(bloco.includes("&")).toBe(false);
    expect(bloco.includes(separador)).toBe(false);
    expect(JSON.parse(bloco)).toEqual(valor);
  });
});

describe("idDoYoutube", () => {
  it.each([
    ["https://www.youtube.com/watch?v=abc123", "abc123"],
    ["https://youtube.com/watch?v=abc123", "abc123"],
    ["https://m.youtube.com/watch?v=abc123", "abc123"],
    ["https://music.youtube.com/watch?v=abc123", "abc123"],
    ["https://www.youtube.com/embed/abc123", "abc123"],
    ["https://www.youtube.com/shorts/abc123", "abc123"],
    ["https://youtu.be/abc123", "abc123"],
  ])("reconhece %s", (url, id) => {
    expect(idDoYoutube(url)).toBe(id);
  });

  it.each([
    "https://fake-youtube.com/watch?v=abc123",
    "https://notyoutube.com/watch?v=abc123",
    "https://youtube.com.evil.example/watch?v=abc123",
    "https://evil.example/youtube.com/watch?v=abc123",
    "não é url",
  ])("recusa %s", (url) => {
    expect(idDoYoutube(url)).toBeNull();
  });
});

describe("normaliza() da busca de cidade", () => {
  it("tira acentos, caixa e pontuação", () => {
    expect(normaliza("São Paulo")).toBe("sao paulo");
    expect(normaliza("  Vitória-ES ")).toBe("vitoria es");
    expect(normaliza("Ç ã é ü")).toBe("c a e u");
  });
});
