/**
 * O artigo reabre onde a leitura parou.
 *
 * O jsdom não calcula layout: scrollHeight e clientHeight são zero e o
 * scrollTop não guarda valor. Os três são simulados aqui — o mínimo para a
 * regra poder ser conferida. O que se testa é a conta de rolagem, não o motor
 * do navegador.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import type { ReaderContent } from "@/api/types";
import { ArticleReader } from "@/components/library/ArticleReader";

const conteudo = {
  id: "r1",
  status: "ok",
  html: "<p>texto do artigo</p>",
  url: "https://exemplo.com/a",
  provider: "exemplo.com",
  words: 900,
  error: null,
} as unknown as ReaderContent;

type ComTopo = HTMLElement & { _topo?: number };
const originais: Record<string, PropertyDescriptor | undefined> = {};

beforeEach(() => {
  for (const nome of ["scrollHeight", "clientHeight", "scrollTop"]) {
    originais[nome] = Object.getOwnPropertyDescriptor(HTMLElement.prototype, nome);
  }
  // 2000px de texto numa caixa de 500px: 1500px roláveis.
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", { configurable: true, get: () => 2000 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, get: () => 500 });
  Object.defineProperty(HTMLElement.prototype, "scrollTop", {
    configurable: true,
    get(this: ComTopo) {
      return this._topo ?? 0;
    },
    set(this: ComTopo, valor: number) {
      this._topo = valor;
    },
  });
});

afterEach(() => {
  for (const [nome, descritor] of Object.entries(originais)) {
    if (descritor) Object.defineProperty(HTMLElement.prototype, nome, descritor);
    else delete (HTMLElement.prototype as unknown as Record<string, unknown>)[nome];
  }
});

const caixa = (container: HTMLElement) => container.querySelector(".leitura") as HTMLElement;

it("reabre no ponto onde a leitura parou", () => {
  const { container } = render(
    <ArticleReader conteudo={conteudo} comecarEm={0.6} onProgresso={() => {}} />,
  );
  expect(caixa(container).scrollTop).toBe(900); // 60% de 1500px
  expect(screen.getByText("60% lido")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Retomado de onde você parou (60%)");
});

it("artigo terminado reabre no topo, para reler", () => {
  const { container } = render(
    <ArticleReader conteudo={conteudo} comecarEm={1} onProgresso={() => {}} />,
  );
  expect(caixa(container).scrollTop).toBe(0);
  expect(screen.getByText("100% lido")).toBeInTheDocument();
  expect(screen.queryByText(/Retomado/)).not.toBeInTheDocument();
});

it("artigo nunca aberto começa do início, sem aviso", () => {
  const { container } = render(<ArticleReader conteudo={conteudo} onProgresso={() => {}} />);
  expect(caixa(container).scrollTop).toBe(0);
  expect(screen.queryByText(/Retomado/)).not.toBeInTheDocument();
});

it("voltar ao início leva ao topo e desliga o reposicionamento", () => {
  const { container } = render(
    <ArticleReader conteudo={conteudo} comecarEm={0.6} onProgresso={() => {}} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Voltar ao início" }));
  expect(caixa(container).scrollTop).toBe(0);
  // Uma imagem que termina de carregar depois não pode arrastar de volta.
  fireEvent.load(caixa(container));
  expect(caixa(container).scrollTop).toBe(0);
});

it("depois que a pessoa mexe, imagem carregando não arrasta a posição", () => {
  const { container } = render(
    <ArticleReader conteudo={conteudo} comecarEm={0.6} onProgresso={() => {}} />,
  );
  const elemento = caixa(container);
  fireEvent.wheel(elemento);
  elemento.scrollTop = 100;
  fireEvent.load(elemento);
  expect(elemento.scrollTop).toBe(100);
});
