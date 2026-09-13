/**
 * Sequência de estudos em dupla e o card de conquista.
 *
 * O que se segura: os marcos (7, 30, 60, 90 e depois de 30 em 30), o cartão do
 * amigo dizendo quem falta estudar hoje, e o botão do card só a partir do
 * primeiro marco.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PessoaCartao } from "@/api/types";
import { CartaoPessoa } from "@/components/social/CartaoPessoa";
import { AuthProvider } from "@/hooks/useAuth";
import { fraseAleatoria, marcoAtingido, proximoMarco, TOTAL_DE_FRASES } from "@/lib/conquista";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const amigo = (sequencia: PessoaCartao["sequencia"]): PessoaCartao => ({
  username: "brunolima",
  name: "Bruno Lima",
  has_avatar: false,
  city: "Vitória",
  state: "ES",
  objetivo: null,
  cargo: null,
  senioridade: null,
  stack: ["Java"],
  relacao: "amigos",
  friendship_id: "f1",
  sequencia,
});

describe("marcos da sequência", () => {
  it("7, 30, 60, 90 e depois a cada 30", () => {
    expect(marcoAtingido(6)).toBeNull();
    expect(marcoAtingido(7)).toBe(7);
    expect(marcoAtingido(29)).toBe(7);
    expect(marcoAtingido(45)).toBe(30);
    expect(marcoAtingido(90)).toBe(90);
    expect(marcoAtingido(119)).toBe(90);
    expect(marcoAtingido(120)).toBe(120);
    expect(marcoAtingido(155)).toBe(150);
    expect(proximoMarco(3)).toBe(7);
    expect(proximoMarco(90)).toBe(120);
  });

  it("a frase é sorteada entre várias", () => {
    const frases = new Set(Array.from({ length: TOTAL_DE_FRASES }, (_, i) => fraseAleatoria(() => i / TOTAL_DE_FRASES)));
    expect(frases.size).toBe(TOTAL_DE_FRASES);
  });
});

describe("cartão do amigo com a sequência", () => {
  it("mostra os dias juntos, quem falta hoje e quanto falta para o card", () => {
    mockServer({});
    render(<CartaoPessoa pessoa={amigo({ atual: 5, recorde: 5, hoje_voce: true, hoje_amigo: false })} onMudou={() => undefined} />);
    expect(screen.getByText(/dias estudando juntos/)).toHaveTextContent("5 dias estudando juntos");
    expect(screen.getByText(/Falta Bruno estudar hoje\. Faltam 2 para o card de 7 dias\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Card de/ })).not.toBeInTheDocument();
  });

  it("no marco, o botão abre o card de conquista", async () => {
    mockServer({
      "GET /tags/mine": () => ({ body: [] }),
      "GET /auth/me": () => ({ body: { id: "u1", name: "Ana Souza", username: "anasouza", has_avatar: false } }),
    });
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <CartaoPessoa pessoa={amigo({ atual: 31, recorde: 31, hoje_voce: true, hoje_amigo: true })} onMudou={() => undefined} />
      </AuthProvider>,
    );
    expect(screen.getByText("Vocês dois já estudaram hoje.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Card de 30 dias" }));
    expect(screen.getByRole("dialog", { name: "Conquista: 30 dias de sequência com Bruno Lima" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sem sequência ainda, convida a estudar no mesmo dia", () => {
    mockServer({});
    render(<CartaoPessoa pessoa={amigo({ atual: 0, recorde: 0, hoje_voce: false, hoje_amigo: false })} onMudou={() => undefined} />);
    expect(screen.getByText("Estudem no mesmo dia para começar uma sequência.")).toBeInTheDocument();
  });
});
