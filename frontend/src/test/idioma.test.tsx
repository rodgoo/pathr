/**
 * O idioma da interface.
 *
 * O que se segura: o seletor mostra os cinco idiomas pelo nome nativo; trocar
 * troca o texto da tela de verdade e fica guardado no aparelho; o idioma da
 * CONTA vence o do aparelho; e uma chave que ainda não foi traduzida cai no
 * português em vez de sumir da tela.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { SeletorDeIdioma } from "@/components/ui/SeletorDeIdioma";
import { IdiomaProvider, useT, type Idioma } from "@/lib/i18n";

afterEach(() => window.localStorage.clear());

function Tela({ idiomaDaConta }: { idiomaDaConta?: Idioma | null }) {
  return (
    <IdiomaProvider idioma={idiomaDaConta}>
      <SeletorDeIdioma />
      <Texto />
    </IdiomaProvider>
  );
}

function Texto() {
  const t = useT();
  return (
    <>
      <p>{t("nav.vagas")}</p>
      <p>{t("nav.treinoDeIdiomas")}</p>
      <p data-testid="inexistente">{t("chave.que.nao.existe")}</p>
    </>
  );
}

describe("idioma da interface", () => {
  it("oferece os cinco idiomas pelo nome deles mesmos", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("pathr:idioma", "pt");
    render(<Tela />);

    await user.click(screen.getByRole("combobox", { name: /Escolher idioma/ }));
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Português",
      "English",
      "Español",
      "Français",
      "Deutsch",
    ]);
  });

  it("trocar o idioma troca o texto da tela e fica guardado", async () => {
    const user = userEvent.setup();
    // Parte-se do português de propósito: sem escolha guardada, o idioma vem
    // do navegador — e o navegador do teste (jsdom) diz "en-US", o que faria a
    // tela já começar em inglês e o teste não provar nada.
    window.localStorage.setItem("pathr:idioma", "pt");
    // `within` na própria árvore: a lista do seletor é montada fora dela (num
    // portal), e procurar no documento inteiro pegaria a lista de outro teste.
    const { container } = render(<Tela />);
    const nesta = within(container);
    expect(nesta.getByText("Vagas")).toBeInTheDocument();

    await user.click(nesta.getByRole("combobox", { name: /Escolher idioma/ }));
    await user.click(screen.getByRole("option", { name: "English" }));

    expect(await nesta.findByText("Job Openings")).toBeInTheDocument();
    expect(window.localStorage.getItem("pathr:idioma")).toBe("en");
    // A aba de treino mudou de nome, e o nome novo também é traduzido.
    expect(nesta.getByText("Language Training")).toBeInTheDocument();
  });

  it("o idioma da conta vence o que está guardado no aparelho", async () => {
    window.localStorage.setItem("pathr:idioma", "pt");
    render(<Tela idiomaDaConta="es" />);
    expect(await screen.findByText("Ofertas de empleo")).toBeInTheDocument();
  });

  it("chave sem tradução cai no português, não some", () => {
    window.localStorage.setItem("pathr:idioma", "pt");
    render(<Tela />);
    // Sem texto para a chave, aparece a própria chave — feio de propósito, e
    // visível em teste e em uso, para não passar despercebido.
    expect(screen.getByTestId("inexistente")).toHaveTextContent("chave.que.nao.existe");
  });
});
