/**
 * Chave de acesso na tela: entrar, cancelar sem culpa, criar e remover.
 *
 * A cerimônia com o aparelho é do navegador — aqui ela é simulada. O que se
 * confere é o que a tela faz com o resultado.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as webauthn from "@simplewebauthn/browser";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { PasskeysPanel } from "@/components/profile/PasskeysPanel";
import { AuthProvider } from "@/hooks/useAuth";
import { LoginPage } from "@/pages/auth/LoginPage";
import { aUser, mockServer } from "./server";

vi.mock("@simplewebauthn/browser", () => ({
  browserSupportsWebAuthn: () => true,
  startAuthentication: vi.fn(async () => ({ id: "cred-1", rawId: "cred-1", type: "public-key", response: {} })),
  startRegistration: vi.fn(async () => ({ id: "cred-2", rawId: "cred-2", type: "public-key", response: { transports: ["internal"] } })),
}));

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const opcoes = { challenge_id: "c1", options: { challenge: "abc" } };

it("entrar com a chave usa o desafio do servidor e lembra do aparelho", async () => {
  const server = mockServer({
    "POST /auth/passkeys/login/options": () => ({ body: opcoes }),
    "POST /auth/passkeys/login/verify": () => ({ body: { user: aUser(), access_token: "t", expires_in: 900 } }),
  });
  render(<AuthProvider><LoginPage onNavigate={() => {}} /></AuthProvider>);
  await userEvent.click(await screen.findByRole("button", { name: "Entrar com chave de acesso" }));
  const verificacao = server.calls.find((c) => c.url.includes("/login/verify"));
  expect(verificacao?.body).toMatchObject({ challenge_id: "c1", credential: { id: "cred-1" } });
  expect(window.localStorage.getItem("pathr.passkey")).toBe("1");
});

it("cancelar o pedido do aparelho não mostra erro", async () => {
  mockServer({ "POST /auth/passkeys/login/options": () => ({ body: opcoes }) });
  vi.mocked(webauthn.startAuthentication).mockRejectedValueOnce(
    Object.assign(new Error("The operation either timed out or was not allowed."), { name: "NotAllowedError" }),
  );
  render(<AuthProvider><LoginPage onNavigate={() => {}} /></AuthProvider>);
  await userEvent.click(await screen.findByRole("button", { name: "Entrar com chave de acesso" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("quem já usou a chave neste aparelho a vê primeiro", async () => {
  window.localStorage.setItem("pathr.passkey", "1");
  mockServer({});
  render(<AuthProvider><LoginPage onNavigate={() => {}} /></AuthProvider>);
  expect(await screen.findByText("ou entre com a senha")).toBeInTheDocument();
});

it("criar chave cadastra e avisa; remover a última esquece o aparelho", async () => {
  window.localStorage.setItem("pathr.passkey", "1");
  const chave = { id: "p1", name: "Chrome no Windows", created_at: "2026-09-01T10:00:00Z", last_used_at: null, backed_up: true };
  const server = mockServer({
    "GET /auth/passkeys": () => ({ body: [chave] }),
    "POST /auth/passkeys/register/options": () => ({ body: opcoes }),
    "POST /auth/passkeys/register/verify": () => ({ status: 201, body: chave }),
    "DELETE /auth/passkeys": () => ({ status: 204 }),
  });
  render(<PasskeysPanel />);
  expect(await screen.findByText("Chrome no Windows")).toBeInTheDocument();
  expect(screen.getByText(/sincronizada entre aparelhos/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Criar chave de acesso neste aparelho" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Chave de acesso criada");
  expect(server.calls.some((c) => c.url.includes("/register/verify"))).toBe(true);

  await userEvent.click(screen.getByRole("button", { name: "Remover" }));
  await vi.waitFor(() => expect(server.calls.some((c) => c.method === "DELETE")).toBe(true));
  expect(window.localStorage.getItem("pathr.passkey")).toBeNull();
});
