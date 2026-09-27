/**
 * Todo `href={...}` dinâmico em src/pages passa por `linkExterno`.
 *
 * Um endereço que vem de fora (busca na web, API de vagas, modelo de IA) e
 * entra num `href` sem filtro aceita `javascript:`. Este teste varre o fonte
 * das telas: um `href={expressão}` só é aceito se a expressão chama
 * `linkExterno(...)` ou está na lista abaixo, cada um com o motivo de ser
 * seguro. Um link novo com endereço de fora que esquecer o filtro quebra aqui.
 */

import { expect, it } from "vitest";

const fontes = import.meta.glob("/src/pages/**/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** Expressões de href que NÃO recebem dado externo. */
const PERMITIDAS: { padrao: RegExp; motivo: string }[] = [
  { padrao: /^linkExterno\(/, motivo: "passa pelo filtro" },
  { padrao: /^`#\$\{[^}]+\}`$/, motivo: "âncora interna da mesma página" },
  { padrao: /^`mailto:\$\{EMAIL_CONTATO\}`$/, motivo: "constante nossa" },
  { padrao: /^linkParaLinkedIn\(/, motivo: "monta uma busca em linkedin.com com o nome do curso" },
  { padrao: /^agenda$/, motivo: "https://calendar.google.com/... montado no próprio componente" },
  { padrao: /^href$/, motivo: "constante de lista fixa (/termos, /privacidade, /seguranca)" },
  { padrao: /^path$/, motivo: "rota interna do app" },
];

/** Lê a expressão dentro de `href={ ... }` respeitando chaves aninhadas. */
function expressoes(fonte: string): string[] {
  const achados: string[] = [];
  const re = /href=\{/g;
  while (re.exec(fonte)) {
    let fundo = 1;
    let i = re.lastIndex;
    while (i < fonte.length && fundo > 0) {
      if (fonte[i] === "{") fundo += 1;
      else if (fonte[i] === "}") fundo -= 1;
      i += 1;
    }
    achados.push(fonte.slice(re.lastIndex, i - 1).trim());
  }
  return achados;
}

it("encontra as telas (a varredura não pode passar vazia)", () => {
  expect(Object.keys(fontes).length).toBeGreaterThan(10);
});

it("nenhum href dinâmico em src/pages usa endereço sem linkExterno", () => {
  const sujos: string[] = [];
  for (const [arquivo, fonte] of Object.entries(fontes)) {
    for (const expr of expressoes(fonte)) {
      if (!PERMITIDAS.some((p) => p.padrao.test(expr))) sujos.push(`${arquivo}: href={${expr}}`);
    }
  }
  expect(sujos).toEqual([]);
});
