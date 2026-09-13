/**
 * A lista de contas da moderação, e banir com a chave de acesso.
 *
 * A cerimônia com o aparelho é do navegador — aqui ela é simulada. O que se
 * segura: a lista mostra nome, @, e-mail e situação; a própria conta e a de
 * admin não têm botão de banir; banir só vai ao servidor DEPOIS da chave, com
 * o desafio e a credencial; e cancelar no aparelho não bane ninguém.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as webauthn from "@simplewebauthn/browser";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { UsuarioAdmin } from "@/api/types";
import { ModeracaoUsuarios } from "@/components/moderacao/ModeracaoUsuarios";
import { mockServer } from "./server";

vi.mock("@simplewebauthn/browser", () => ({
  browserSupportsWebAuthn: () => true,
  startAuthentication: vi.fn(async () => ({ id: "cred-admin", rawId: "cred-admin", type: "public-key", response: {} })),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(webauthn.startAuthentication).mockClear();
});

const conta = (id: string, extra: Partial<UsuarioAdmin> = {}): UsuarioAdmin => ({
  id,
  name: "Ana Souza",
  username: "anasouza",
  email: "ana@exemplo.com",
  has_avatar: false,
  created_at: "2026-09-10T12:00:00+00:00",
  email_verified: true,
  banned_at: null,
  banned_reason: null,
  is_super_admin: false,
  voce: false,
  ...extra,
});

const lista = {
  limite: 300,
  usuarios: [
    conta("u-ana"),
    conta("u-eu", { name: "Chefe", username: "chefe", email: "chefe@exemplo.com", voce: true, is_super_admin: true }),
    conta("u-bia", { name: "Bia Lima", username: "bialima", email: "bia@exemplo.com", banned_at: "2026-09-12T00:00:00+00:00", banned_reason: "spam" }),
  ],
};

function monta(extra: Record<string, () => { status?: number; body?: unknown }> = {}) {
  const servidor = mockServer({
    "GET /admin/usuarios": () => ({ body: lista }),
    "POST /admin/confirmacao": () => ({ body: { challenge_id: "c1", options: { challenge: "abc" } } }),
    "POST /admin/usuarios/u-ana/banir": () => ({ body: conta("u-ana", { banned_at: "2026-09-13T00:00:00+00:00" }) }),
    ...extra,
  });
  render(<ModeracaoUsuarios />);
  return { servidor, user: userEvent.setup() };
}

const linha = async (nome: string) => (await screen.findByText(nome)).closest("li") as HTMLElement;

describe("moderação de contas", () => {
  it("lista nome, @, e-mail e situação, sem banir a si nem outro admin", async () => {
    monta();
    const ana = await linha("Ana Souza");
    expect(within(ana).getByText("ana@exemplo.com")).toBeInTheDocument();
    expect(within(ana).getByText("@anasouza")).toBeInTheDocument();
    expect(within(ana).getByRole("button", { name: "Banir" })).toBeInTheDocument();

    const eu = await linha("Chefe");
    expect(within(eu).getByText("você")).toBeInTheDocument();
    expect(within(eu).queryByRole("button", { name: /Banir/ })).not.toBeInTheDocument();

    const bia = await linha("Bia Lima");
    expect(within(bia).getByText("banido")).toBeInTheDocument();
    expect(within(bia).getByText("Motivo: spam")).toBeInTheDocument();
    expect(within(bia).getByRole("button", { name: "Desbanir" })).toBeInTheDocument();
  });

  it("banir pede o motivo e a chave de acesso antes de ir ao servidor", async () => {
    const { servidor, user } = monta();
    const ana = await linha("Ana Souza");
    await user.click(within(ana).getByRole("button", { name: "Banir" }));

    const confirmar = within(ana).getByRole("button", { name: "Confirmar com chave de acesso" });
    expect(confirmar).toBeDisabled(); // sem motivo, não confirma
    await user.type(within(ana).getByLabelText("Motivo (fica registrado)"), "Spam em convites");
    await user.click(confirmar);

    await vi.waitFor(() => expect(servidor.calls.some((c) => c.url === "/admin/usuarios/u-ana/banir")).toBe(true));
    expect(webauthn.startAuthentication).toHaveBeenCalledTimes(1);
    const ordem = servidor.calls.map((c) => c.url);
    expect(ordem.indexOf("/admin/confirmacao")).toBeLessThan(ordem.indexOf("/admin/usuarios/u-ana/banir"));
    const envio = servidor.calls.find((c) => c.url === "/admin/usuarios/u-ana/banir");
    expect(envio?.body).toMatchObject({ motivo: "Spam em convites", challenge_id: "c1", credential: { id: "cred-admin" } });
  });

  it("cancelar no aparelho não bane ninguém", async () => {
    vi.mocked(webauthn.startAuthentication).mockRejectedValueOnce(
      Object.assign(new Error("not allowed"), { name: "NotAllowedError" }),
    );
    const { servidor, user } = monta();
    const ana = await linha("Ana Souza");
    await user.click(within(ana).getByRole("button", { name: "Banir" }));
    await user.type(within(ana).getByLabelText("Motivo (fica registrado)"), "Spam");
    await user.click(within(ana).getByRole("button", { name: "Confirmar com chave de acesso" }));

    expect(await within(ana).findByRole("alert")).toHaveTextContent("Confirmação cancelada. Nada foi alterado.");
    expect(servidor.calls.some((c) => c.url.endsWith("/banir"))).toBe(false);
  });

  it("sem chave cadastrada, diz o que fazer", async () => {
    const { servidor, user } = monta({
      "POST /admin/confirmacao": () => ({
        status: 409,
        body: { detail: "Cadastre uma chave de acesso em Configurações › Conta para confirmar esta ação." },
      }),
    });
    const ana = await linha("Ana Souza");
    await user.click(within(ana).getByRole("button", { name: "Banir" }));
    await user.type(within(ana).getByLabelText("Motivo (fica registrado)"), "Spam");
    await user.click(within(ana).getByRole("button", { name: "Confirmar com chave de acesso" }));
    expect(await within(ana).findByRole("alert")).toHaveTextContent("Cadastre uma chave de acesso");
    expect(webauthn.startAuthentication).not.toHaveBeenCalled();
    expect(servidor.calls.some((c) => c.url.endsWith("/banir"))).toBe(false);
  });
});
