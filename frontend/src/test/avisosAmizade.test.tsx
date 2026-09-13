/**
 * O pop-up de amizade.
 *
 * O que se segura: o convite aparece com nome e stack e já é marcado como
 * visto (não reaparece em outro aparelho); aceitar resolve ali mesmo; o aviso
 * some sozinho; e nada na navegação pisca.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { NovidadeDeAmizade, PessoaCartao } from "@/api/types";
import { AvisosDeAmizade } from "@/components/social/AvisosDeAmizade";
import { AppStateProvider } from "@/hooks/useAppState";
import { mockServer } from "./server";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const ana: PessoaCartao = {
  username: "anasouza",
  name: "Ana Souza",
  has_avatar: false,
  city: "Vitória",
  state: "ES",
  objetivo: null,
  cargo: null,
  senioridade: null,
  stack: ["Java", "React"],
  relacao: "recebido",
  friendship_id: "f1",
};

const convite: NovidadeDeAmizade = { tipo: "convite", friendship_id: "f1", quando: null, pessoa: ana };

function monta(novidades: NovidadeDeAmizade[], duracaoMs?: number) {
  const servidor = mockServer({
    "GET /social/novidades": () => ({ body: novidades }),
    "POST /social/novidades/vistas": () => ({ status: 204 }),
    "POST /social/convites/f1/aceitar": () => ({ body: { relacao: "amigos" } }),
  });
  render(
    <AppStateProvider>
      <AvisosDeAmizade duracaoMs={duracaoMs} />
    </AppStateProvider>,
  );
  return servidor;
}

describe("pop-up de amizade", () => {
  it("mostra o convite com nome e stack, marca como visto e não pisca nada", async () => {
    const servidor = monta([convite]);
    const aviso = await screen.findByRole("alertdialog", { name: "Ana Souza te mandou um convite de amizade" });
    expect(aviso).toHaveTextContent("Ana te mandou um convite de amizade");
    expect(screen.getByText("Java")).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(servidor.calls.find((c) => c.url === "/social/novidades/vistas")?.body).toEqual({
        itens: [{ friendship_id: "f1", tipo: "convite" }],
      }),
    );
    expect(document.querySelector(".pathr-piscando")).toBeNull();
  });

  it("aceitar resolve ali mesmo e fecha o aviso", async () => {
    const servidor = monta([convite]);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Aceitar" }));
    expect(servidor.calls.some((c) => c.method === "POST" && c.url === "/social/convites/f1/aceitar")).toBe(true);
    await vi.waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  });

  it("some sozinho depois do tempo de exibição", async () => {
    // 300 ms no teste; na tela, 5 segundos (o padrão do componente).
    monta([convite], 300);
    await screen.findByRole("alertdialog");
    await vi.waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument(), { timeout: 2000 });
  });

  it("o aviso de aceite diz quem aceitou", async () => {
    monta([{ tipo: "aceito", friendship_id: "f2", quando: null, pessoa: { ...ana, relacao: "amigos" } }]);
    expect(await screen.findByRole("status", { name: "Ana Souza aceitou seu convite" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver amigos" })).toBeInTheDocument();
  });
});
