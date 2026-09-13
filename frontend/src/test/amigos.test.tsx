/**
 * O @ de cada conta e a aba de amigos.
 *
 * O que estes testes seguram é o que a pessoa vê ANTES de agir: qual @ ela
 * vai ganhar se deixar o campo em branco, quais alternativas existem quando o
 * nome está ocupado, e qual é o único botão de cada cartão.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { PessoaCartao } from "@/api/types";
import { CampoUsername } from "@/components/social/CampoUsername";
import { CartaoPessoa } from "@/components/social/CartaoPessoa";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const pessoa = (campos: Partial<PessoaCartao> = {}): PessoaCartao => ({
  username: "brunolima",
  name: "Bruno Lima",
  has_avatar: false,
  city: "Vitória",
  state: "ES",
  objetivo: "Backend Java",
  cargo: "Desenvolvedor",
  senioridade: "pleno",
  stack: ["Java", "Spring Boot"],
  relacao: "nenhuma",
  friendship_id: null,
  ...campos,
});

it("com o campo vazio, diz qual @ a pessoa vai ganhar", async () => {
  mockServer({
    "GET /social/username/disponivel": () => ({
      body: { username: "", disponivel: false, problema: null, sugestoes: ["rodrigocarvalho"] },
    }),
  });
  render(<CampoUsername id="u" value="" onChange={() => {}} nome="Rodrigo Carvalho" />);
  expect(await screen.findByText("@rodrigocarvalho", {}, { timeout: 2000 })).toBeInTheDocument();
  expect(screen.getByText(/Se deixar em branco, você será/)).toBeInTheDocument();
});

it("nome ocupado mostra o motivo e sugestões que preenchem o campo", async () => {
  mockServer({
    "GET /social/username/disponivel": () => ({
      body: {
        username: "rodgoo",
        disponivel: false,
        problema: "Este nome de usuário já está em uso.",
        sugestoes: ["rodgoo_", "rodgoo1"],
      },
    }),
  });
  const escolhido = vi.fn();
  render(<CampoUsername id="u" value="rodgoo" onChange={escolhido} nome="Rodrigo" />);

  expect(await screen.findByText("Este nome de usuário já está em uso.", {}, { timeout: 2000 })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "@rodgoo_" }));
  expect(escolhido).toHaveBeenCalledWith("rodgoo_");
});

it("o próprio @ atual não é tratado como ocupado", async () => {
  const servidor = mockServer({});
  render(<CampoUsername id="u" value="rodgoo_" onChange={() => {}} atual="rodgoo_" />);
  expect(screen.getByText("Este é o seu @ atual.")).toBeInTheDocument();
  await new Promise((r) => setTimeout(r, 500));
  expect(servidor.calls).toHaveLength(0);
});

it("cartão mostra nome, @, lugar, objetivo e stack — e nunca e-mail", () => {
  render(<CartaoPessoa pessoa={pessoa()} onMudou={() => {}} />);
  const cartao = screen.getByRole("article", { name: "Bruno Lima, @brunolima" });
  expect(within(cartao).getByText("Vitória · ES")).toBeInTheDocument();
  expect(within(cartao).getByText("Backend Java")).toBeInTheDocument();
  expect(within(cartao).getByText("Spring Boot")).toBeInTheDocument();
  expect(cartao.textContent).not.toMatch(/@exemplo|\.com/);
});

it("sem relação, Adicionar manda o convite para o @ do cartão", async () => {
  const servidor = mockServer({ "POST /social/amigos/brunolima": () => ({ body: { relacao: "enviado" } }) });
  const mudou = vi.fn();
  render(<CartaoPessoa pessoa={pessoa()} onMudou={mudou} />);

  await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));

  await waitFor(() => expect(mudou).toHaveBeenCalled());
  expect(servidor.calls.some((c) => c.method === "POST" && c.url === "/social/amigos/brunolima")).toBe(true);
});

it("convite recebido oferece aceitar e recusar, e nada de Adicionar", () => {
  render(<CartaoPessoa pessoa={pessoa({ relacao: "recebido", friendship_id: "f-1" })} onMudou={() => {}} />);
  expect(screen.getByRole("button", { name: "Aceitar" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Recusar" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Adicionar" })).not.toBeInTheDocument();
});

it("desfazer amizade pede confirmação antes de apagar", async () => {
  const servidor = mockServer({ "DELETE /social/convites/f-9": () => ({ status: 204 }) });
  render(<CartaoPessoa pessoa={pessoa({ relacao: "amigos", friendship_id: "f-9" })} onMudou={() => {}} />);

  await userEvent.click(screen.getByRole("button", { name: "Desfazer amizade" }));
  expect(servidor.calls).toHaveLength(0);
  await userEvent.click(screen.getByRole("button", { name: "Desfazer" }));
  await waitFor(() => expect(servidor.calls.some((c) => c.method === "DELETE")).toBe(true));
});
