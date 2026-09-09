/**
 * O botão de procurar material.
 *
 * O que importa aqui não é o botão chamar a rota — é o que a tela diz DEPOIS.
 * A busca pode voltar vazia por três motivos completamente diferentes (a
 * carência de 14 dias, nenhum link aprovado na verificação, nenhuma fonte
 * configurada no servidor), e cada um pede uma reação diferente de quem está
 * olhando. Uma tela que responde "nada encontrado" aos três esconde a única
 * informação útil.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { CurateButton } from "@/components/library/CurateButton";
import { mockServer, type Handler } from "./server";

afterEach(() => vi.unstubAllGlobals());

function comResposta(handler: Handler) {
  return mockServer({ "POST /library/curate": handler });
}

it("diz quantos materiais entraram e manda a lista recarregar", async () => {
  comResposta(() => ({ body: { novos: 6, tags_buscadas: ["Docker"], motivo: null } }));
  const recarrega = vi.fn();

  render(<CurateButton onFound={recarrega} />);
  await userEvent.click(screen.getByRole("button", { name: "Procurar material" }));

  expect(await screen.findByRole("status")).toHaveTextContent("6 materiais novos.");
  expect(recarrega).toHaveBeenCalledTimes(1);
});

it("concorda em número quando veio um só", async () => {
  comResposta(() => ({ body: { novos: 1, tags_buscadas: ["Redis"], motivo: null } }));

  render(<CurateButton onFound={vi.fn()} />);
  await userEvent.click(screen.getByRole("button"));

  expect(await screen.findByRole("status")).toHaveTextContent("1 material novo.");
});

it("repete o motivo do servidor em vez de inventar um 'nada encontrado'", async () => {
  comResposta(() => ({
    body: {
      novos: 0,
      tags_buscadas: [],
      motivo: "Essas tecnologias foram buscadas há pouco. A curadoria repete a cada 14 dias.",
    },
  }));
  const recarrega = vi.fn();

  render(<CurateButton onFound={recarrega} />);
  await userEvent.click(screen.getByRole("button"));

  expect(await screen.findByRole("status")).toHaveTextContent("buscadas há pouco");
  // Nada entrou: recarregar a lista seria uma requisição para receber
  // exatamente o que já está na tela.
  expect(recarrega).not.toHaveBeenCalled();
});

it("passa o módulo quando está dentro de uma trilha", async () => {
  const server = comResposta(() => ({ body: { novos: 2, tags_buscadas: ["Kafka"], motivo: null } }));

  render(<CurateButton nodeId="node-42" onFound={vi.fn()} />);
  await userEvent.click(screen.getByRole("button"));

  await screen.findByRole("status");
  expect(server.calls.at(-1)?.url).toContain("node_id=node-42");
});

it("mostra o erro quando a busca falha, sem sumir com o botão", async () => {
  comResposta(() => ({ status: 500, body: { detail: "Provedor de busca indisponível." } }));

  render(<CurateButton onFound={vi.fn()} />);
  await userEvent.click(screen.getByRole("button"));

  expect(await screen.findByRole("status")).toHaveTextContent("indisponível");
  // O botão volta a aceitar clique: uma falha de rede costuma ser passageira,
  // e uma tela que se desabilita sozinha obriga a recarregar a página.
  expect(screen.getByRole("button")).toBeEnabled();
});
