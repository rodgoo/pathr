/**
 * O select do app.
 *
 * O nativo foi trocado por uma lista desenhada aqui, e o que ele dava de graça
 * precisou ser refeito. Estes testes seguram exatamente essa parte: sem ela o
 * select fica bonito e passa a ser inalcançável para quem usa teclado ou
 * leitor de tela — ou deixa de impedir o envio de um formulário incompleto.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import { Select } from "@/components/ui/Select";

const UFS = ["AC", "BA", "ES", "SC", "SE", "SP"].map((uf) => ({ value: uf, label: uf }));

function Campo({ inicial = "", required = false }: { inicial?: string; required?: boolean }) {
  const [valor, setValor] = useState(inicial);
  return (
    <>
      <label htmlFor="uf">UF</label>
      <Select id="uf" options={UFS} value={valor} onChange={setValor} required={required} name="uf" />
      <output>escolhida: {valor || "nenhuma"}</output>
    </>
  );
}

const gatilho = () => screen.getByRole("combobox", { name: "UF" });

it("o rótulo nomeia o campo e a lista começa fechada", () => {
  render(<Campo />);
  expect(gatilho()).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("clicar abre, clicar numa opção escolhe e fecha", async () => {
  const user = userEvent.setup();
  render(<Campo />);

  await user.click(gatilho());
  await user.click(screen.getByRole("option", { name: "ES" }));

  expect(screen.getByText("escolhida: ES")).toBeInTheDocument();
  expect(gatilho()).toHaveAttribute("aria-expanded", "false");
  expect(gatilho()).toHaveTextContent("ES");
});

/**
 * O foco FICA no gatilho, e a opção ativa é anunciada por
 * `aria-activedescendant`. Mover o foco para dentro da lista faria o leitor de
 * tela perder o nome do campo a cada seta.
 */
it("setas movem a opção ativa sem tirar o foco do campo, Enter escolhe", async () => {
  const user = userEvent.setup();
  render(<Campo inicial="BA" />);
  gatilho().focus();

  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("listbox")).toBeInTheDocument();
  // Abre na escolha atual, não no topo da lista.
  expect(screen.getByRole("option", { name: "BA" })).toHaveAttribute("aria-selected", "true");

  await user.keyboard("{ArrowDown}{ArrowDown}");
  const ativa = gatilho().getAttribute("aria-activedescendant");
  expect(document.getElementById(ativa ?? "")).toHaveTextContent("SC");
  expect(gatilho()).toHaveFocus();

  await user.keyboard("{Enter}");
  expect(screen.getByText("escolhida: SC")).toBeInTheDocument();
});

it("Esc fecha sem mudar a escolha", async () => {
  const user = userEvent.setup();
  render(<Campo inicial="BA" />);
  gatilho().focus();

  await user.keyboard("{ArrowDown}{ArrowDown}{Escape}");

  expect(gatilho()).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByText("escolhida: BA")).toBeInTheDocument();
});

/** Numa lista de 27 UFs, digitar é como se chega a "SP" sem rolar. */
it("digitar letras com a lista fechada escolhe direto, como o nativo", async () => {
  const user = userEvent.setup();
  render(<Campo />);
  gatilho().focus();

  await user.keyboard("sp");

  expect(screen.getByText("escolhida: SP")).toBeInTheDocument();
});

it("clicar fora fecha", async () => {
  const user = userEvent.setup();
  render(
    <>
      <Campo />
      <button type="button">outro</button>
    </>,
  );

  await user.click(gatilho());
  await user.click(screen.getByRole("button", { name: "outro" }));

  expect(gatilho()).toHaveAttribute("aria-expanded", "false");
});

/**
 * Um select obrigatório vazio precisa continuar barrando o envio. Sem o campo
 * que carrega o valor, o formulário do cadastro sairia sem UF.
 */
it("obrigatório e vazio, impede o formulário de ser enviado", () => {
  const enviar = vi.fn((evento: { preventDefault: () => void }) => evento.preventDefault());
  const { container } = render(
    <form onSubmit={enviar}>
      <Campo required />
      <button type="submit">enviar</button>
    </form>,
  );
  const formulario = container.querySelector("form") as HTMLFormElement;

  expect(formulario.checkValidity()).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "enviar" }));
  expect(enviar).not.toHaveBeenCalled();
});

it("leva o valor escolhido para o formulário pelo nome", async () => {
  const user = userEvent.setup();
  const { container } = render(
    <form>
      <Campo required />
    </form>,
  );

  await user.click(gatilho());
  await user.click(screen.getByRole("option", { name: "SC" }));

  const dados = new FormData(container.querySelector("form") as HTMLFormElement);
  expect(dados.get("uf")).toBe("SC");
  expect((container.querySelector("form") as HTMLFormElement).checkValidity()).toBe(true);
});
