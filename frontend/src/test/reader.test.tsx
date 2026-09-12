/**
 * O artigo reabre onde a leitura parou.
 *
 * O artigo FLUI na página: não tem caixa de rolagem própria, e quem rola é a
 * janela. Então a régua do progresso é quanto do texto já passou pela borda
 * de baixo da tela, e retomar é levar a janela ao ponto em que essa conta dá
 * a fração guardada.
 *
 * O jsdom não calcula layout nem rola nada: altura, posição e rolagem são
 * simuladas aqui, o mínimo para a conta poder ser conferida. O que se testa é
 * a conta, não o motor do navegador.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
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

/** 2000px de texto numa janela de 500px, começando no topo da página. */
const ALTURA = 2000;
const JANELA = 500;

let rolagem = 0;
const original = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetHeight");

beforeEach(() => {
  rolagem = 0;
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    get: () => ALTURA,
  });
  // O artigo começa em y=0 da página, então o topo visível é o negativo da
  // rolagem — é assim que o navegador reporta.
  HTMLElement.prototype.getBoundingClientRect = function () {
    return { top: -rolagem, bottom: ALTURA - rolagem, height: ALTURA } as DOMRect;
  };
  window.innerHeight = JANELA;
  vi.stubGlobal("scrollTo", (opcoes: { top: number }) => {
    rolagem = opcoes.top;
    window.dispatchEvent(new Event("scroll"));
  });
  Object.defineProperty(window, "scrollY", { configurable: true, get: () => rolagem });
});

afterEach(() => {
  if (original) Object.defineProperty(HTMLElement.prototype, "offsetHeight", original);
  vi.unstubAllGlobals();
});

it("reabre no ponto onde a leitura parou", () => {
  render(<ArticleReader conteudo={conteudo} comecarEm={0.6} onProgresso={() => {}} />);
  // 60% de 2000px já passaram pela borda de baixo: 1200 - 500 de janela.
  expect(rolagem).toBe(700);
  expect(screen.getByText("60% lido")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Retomado de onde você parou (60%)");
});

it("artigo terminado reabre no topo, para reler", () => {
  render(<ArticleReader conteudo={conteudo} comecarEm={1} onProgresso={() => {}} />);
  expect(rolagem).toBe(0);
  expect(screen.getByText("100% lido")).toBeInTheDocument();
  expect(screen.queryByText(/Retomado/)).not.toBeInTheDocument();
});

it("artigo nunca aberto começa do início, sem aviso", () => {
  render(<ArticleReader conteudo={conteudo} onProgresso={() => {}} />);
  expect(rolagem).toBe(0);
  expect(screen.queryByText(/Retomado/)).not.toBeInTheDocument();
});

it("voltar ao início leva ao topo e desliga o reposicionamento", () => {
  const { container } = render(
    <ArticleReader conteudo={conteudo} comecarEm={0.6} onProgresso={() => {}} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Voltar ao início" }));
  expect(rolagem).toBe(0);
  // Uma imagem que termina de carregar depois não pode arrastar de volta.
  fireEvent.load(container.querySelector(".leitura") as HTMLElement);
  expect(rolagem).toBe(0);
});

it("depois que a pessoa mexe, imagem carregando não arrasta a posição", () => {
  const { container } = render(
    <ArticleReader conteudo={conteudo} comecarEm={0.6} onProgresso={() => {}} />,
  );
  const elemento = container.querySelector(".leitura") as HTMLElement;
  fireEvent.wheel(elemento);
  rolagem = 100;
  fireEvent.load(elemento);
  expect(rolagem).toBe(100);
});

/**
 * O texto não fica preso numa janelinha.
 *
 * Rolagem dentro de rolagem cortava a última linha visível pela metade — o
 * que se lê como conteúdo colidindo com o que vem depois — e no computador
 * desperdiçava a tela para ler num visor estreito.
 */
it("o artigo não cria uma segunda rolagem dentro da página", () => {
  const { container } = render(<ArticleReader conteudo={conteudo} onProgresso={() => {}} />);
  const elemento = container.querySelector(".leitura") as HTMLElement;
  expect(elemento.style.overflowY).toBe("");
  expect(elemento.style.maxHeight).toBe("");
});
