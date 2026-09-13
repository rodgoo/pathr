/**
 * Uma URL de fora só vira link se for http ou https.
 *
 * Endereço de artigo, vaga e curso vem de busca na web, de API de vagas e de
 * resposta de IA. O React 18 ainda renderiza `href="javascript:..."`: sem
 * este filtro, uma vaga maliciosa executaria código no PathR no clique.
 */

import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { linkExterno } from "@/lib/linkExterno";

it.each([
  ["https://docs.github.com/actions", "https://docs.github.com/actions"],
  ["http://exemplo.com/a", "http://exemplo.com/a"],
  ["  https://exemplo.com/  ", "https://exemplo.com/"],
])("aceita %s", (entrada, esperado) => {
  expect(linkExterno(entrada)).toBe(esperado);
});

it.each([
  "javascript:alert(document.cookie)",
  "JavaScript:alert(1)",
  " javascript:alert(1)",
  "data:text/html,<script>alert(1)</script>",
  "vbscript:msgbox(1)",
  "file:///etc/passwd",
  "//evil.example.com",
  "nao é url",
  "",
  null,
  undefined,
])("recusa %s", (entrada) => {
  expect(linkExterno(entrada as string | null | undefined)).toBeUndefined();
});

it("um link com URL recusada é texto inerte, sem href", () => {
  render(
    <a href={linkExterno("javascript:alert(1)")} target="_blank" rel="noreferrer noopener">
      Ver vaga
    </a>,
  );
  expect(screen.getByText("Ver vaga").closest("a")?.hasAttribute("href")).toBe(false);
});
