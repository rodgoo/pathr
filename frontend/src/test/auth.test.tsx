/**
 * Autenticação: o que o usuário encontra antes de entrar no app.
 *
 * Estes testes existem porque a porta de entrada é onde um erro custa mais —
 * quem não consegue entrar não consegue nem reclamar de dentro do produto.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { aUser, anOverview, mockServer, type MockServer } from "./server";

function renderApp(server: MockServer, path = "/") {
  window.history.pushState({}, "", path);
  return {
    server,
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <AppStateProvider>
          <App />
        </AppStateProvider>
      </AuthProvider>,
    ),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("sessão", () => {
  it("mostra a tela de entrada quando não há sessão", async () => {
    const server = mockServer({ "GET /auth/me": () => ({ status: 401, body: { detail: "x" } }) });
    renderApp(server);
    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });

  it("entra no app quando há sessão viva", async () => {
    const server = mockServer({
      "GET /auth/me": () => ({ body: aUser() }),
      "GET /profile/overview": () => ({ body: anOverview() }),
      "GET /roadmap/current": () => ({ status: 404, body: { detail: "sem plano" } }),
      "GET /english/profile": () => ({ body: { enabled: true, cefr_level: "B1" } }),
    });
    renderApp(server);
    expect(await screen.findByText(/Bem-vindo de volta, Lucas/)).toBeInTheDocument();
  });

  it("uma sessão expirada leva à tela de entrada, não a um app quebrado", async () => {
    const server = mockServer({
      "GET /auth/me": () => ({ status: 401, body: { detail: "Sessão inválida." } }),
      "POST /auth/refresh": () => ({ status: 401, body: { detail: "Sessão inválida." } }),
    });
    renderApp(server);
    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });
});

describe("entrar", () => {
  it("manda e-mail e senha e abre o app", async () => {
    const server = mockServer({
      "GET /auth/me": () => ({ status: 401, body: {} }),
      "POST /auth/login": () => ({ body: { user: aUser(), access_token: "t", expires_in: 1800 } }),
      "GET /profile/overview": () => ({ body: anOverview() }),
      "GET /roadmap/current": () => ({ status: 404, body: {} }),
      "GET /english/profile": () => ({ body: { enabled: false, cefr_level: null } }),
    });
    const { user } = renderApp(server);

    await screen.findByRole("heading", { name: "Entrar" });
    await user.type(screen.getByLabelText("E-mail"), "lucas@exemplo.com");
    await user.type(screen.getByLabelText("Senha"), "senha-forte-123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText(/Bem-vindo de volta/)).toBeInTheDocument();
    const login = server.calls.find((call) => call.url === "/auth/login");
    expect(login?.body).toMatchObject({ email: "lucas@exemplo.com", password: "senha-forte-123" });
  });

  it("mostra o motivo quando a senha está errada", async () => {
    const server = mockServer({
      "GET /auth/me": () => ({ status: 401, body: {} }),
      "POST /auth/login": () => ({ status: 401, body: { detail: "E-mail ou senha incorretos." } }),
    });
    const { user } = renderApp(server);

    await screen.findByRole("heading", { name: "Entrar" });
    await user.type(screen.getByLabelText("E-mail"), "lucas@exemplo.com");
    await user.type(screen.getByLabelText("Senha"), "errada-mesmo-123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
  });

  it("revela o campo do segundo fator sem perder e-mail e senha", async () => {
    // Uma segunda tela obrigaria a repetir o login se o código fosse digitado
    // errado — daí o campo aparecer no mesmo formulário.
    const server = mockServer({
      "GET /auth/me": () => ({ status: 401, body: {} }),
      "POST /auth/login": () => ({
        status: 401,
        body: { detail: "Informe o código do autenticador." },
        headers: { "x-pathr-mfa": "required" },
      }),
    });
    const { user } = renderApp(server);

    await screen.findByRole("heading", { name: "Entrar" });
    await user.type(screen.getByLabelText("E-mail"), "lucas@exemplo.com");
    await user.type(screen.getByLabelText("Senha"), "senha-forte-123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByLabelText("Código do autenticador")).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toHaveValue("lucas@exemplo.com");
  });
});
