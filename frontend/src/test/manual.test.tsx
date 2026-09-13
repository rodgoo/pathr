/**
 * Manual de bordo, tutorial dos níveis e a transição entre telas.
 *
 * O que se segura: o tutorial explica cada nível e pode ser pulado inteiro de
 * qualquer passo (e reaberto); os primeiros passos marcam o que os dados
 * mostram que já foi feito e apontam o próximo; e a transição nunca atrasa
 * nem esconde a tela nova quando o navegador não tem a API.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TutorialDeNiveis } from "@/components/profile/TutorialDeNiveis";
import { PrimeirosPassos } from "@/components/manual/PrimeirosPassos";
import { AppStateProvider } from "@/hooks/useAppState";
import { comTransicao } from "@/lib/transicao";
import { mockServer } from "./server";

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("tutorial dos níveis", () => {
  it("percorre os níveis e pode ser pulado de qualquer passo", async () => {
    const user = userEvent.setup();
    render(<TutorialDeNiveis />);
    expect(screen.getByRole("region", { name: "Como funcionam os níveis" })).toBeInTheDocument();
    expect(screen.getByText("Ainda não usei, mas quero aprender.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Próximo/ }));
    expect(screen.getByText("Já vi em tutorial ou num projeto de estudo.")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /N3/ }));
    expect(screen.getByText(/Dominado: o roadmap não ensina de novo/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pular tutorial" }));
    expect(screen.queryByRole("region", { name: "Como funcionam os níveis" })).not.toBeInTheDocument();
    // Fechado continua fechado ao voltar à tela, e dá para reabrir.
    await user.click(screen.getByRole("button", { name: "Como funcionam os níveis?" }));
    expect(screen.getByRole("region", { name: "Como funcionam os níveis" })).toBeInTheDocument();
  });
});

describe("primeiros passos", () => {
  function monta(compacto = false) {
    mockServer({
      "GET /profile": () => ({ body: { user_id: "u", city: "Vitória", target_role: "Fullstack Java", goals: [] } }),
      "GET /tags/mine": () => ({ body: [] }),
      "GET /resumes": () => ({ body: [] }),
      "GET /roadmap/current": () => ({ status: 404, body: { detail: "Sem plano" } }),
      "GET /languages/profile": () => ({ body: { cefr_level: null } }),
      "GET /social/amigos": () => ({ body: { amigos: [], recebidos: [], enviados: [] } }),
    });
    render(
      <AppStateProvider>
        <PrimeirosPassos compacto={compacto} />
      </AppStateProvider>,
    );
  }

  it("marca o que já foi feito e aponta o próximo passo", async () => {
    monta();
    expect(await screen.findByText("2 de 4 essenciais feitos")).toBeInTheDocument();
    expect(screen.getByText(/Próximo passo:/)).toHaveTextContent("Marque suas skills e os níveis");
    expect(screen.getByRole("button", { name: "Ir para: Marque suas skills e os níveis" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ir para: Diga onde você mora" })).not.toBeInTheDocument();
  });

  it("no Início, pular esconde o card", async () => {
    const user = userEvent.setup();
    monta(true);
    await user.click(await screen.findByRole("button", { name: /Pular/ }));
    expect(screen.queryByRole("region", { name: "Primeiros passos" })).not.toBeInTheDocument();
  });
});

describe("transição entre telas", () => {
  it("sem a API do navegador, troca na hora", () => {
    const atualizar = vi.fn();
    comTransicao(atualizar);
    expect(atualizar).toHaveBeenCalledTimes(1);
  });

  it("com a API, a troca acontece dentro da transição", () => {
    const iniciar = vi.fn((callback: () => void) => callback());
    Object.defineProperty(document, "startViewTransition", { value: iniciar, configurable: true });
    const atualizar = vi.fn();
    try {
      comTransicao(atualizar);
    } finally {
      delete (document as { startViewTransition?: unknown }).startViewTransition;
    }
    expect(iniciar).toHaveBeenCalledTimes(1);
    expect(atualizar).toHaveBeenCalledTimes(1);
  });
});
