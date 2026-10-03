/**
 * AccountTab não deve fazer uma chamada morta a GET /auth/me ao salvar.
 *
 * O bug: salvar a conta chamava `authApi.me()` e descartava o resultado —
 * uma requisição extra, sem efeito nenhum, em todo clique de "Salvar
 * alterações". O teste conta quantas vezes `GET /auth/me` é chamado durante
 * o fluxo de salvar: só a montagem do AuthProvider e o `refresh()` do fim do
 * salvamento devem chamá-la — nunca o próprio `save`.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountTab } from "@/components/profile/AccountTab";
import { AuthProvider } from "@/hooks/useAuth";
import { aUser, mockServer } from "./server";

const profile = {
  user_id: "user-1",
  headline: null,
  current_role: "Desenvolvedor frontend",
  target_role: null,
  seniority: "pleno",
  years_experience: 3,
  weekly_hours: 8,
  learning_style: null,
  goals: [],
  bio: null,
  linkedin_url: null,
  github_url: null,
};

afterEach(() => vi.unstubAllGlobals());

function montar() {
  const server = mockServer({
    "GET /auth/me": () => ({ body: aUser() }),
    "GET /features": () => ({ body: {} }),
    "GET /profile": () => ({ body: profile }),
    "PATCH /profile/account": () => ({ body: aUser() }),
    "PATCH /profile": () => ({ body: profile }),
    "GET /auth/sessoes": () => ({ body: [] }),
    "GET /auth/passkeys": () => ({ body: [] }),
  });
  return {
    server,
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <AccountTab />
      </AuthProvider>,
    ),
  };
}

describe("AccountTab: salvar a conta", () => {
  it("não chama GET /auth/me por conta própria ao salvar", async () => {
    const { server, user } = montar();

    await screen.findByText("Lucas Martins", { exact: false, selector: "input" }).catch(() => undefined);
    const botao = await screen.findByRole("button", { name: /Salvar alterações/ });

    const meAntesDeSalvar = server.calls.filter(
      (call) => call.method === "GET" && call.url === "/auth/me",
    ).length;
    // Só a montagem do AuthProvider chamou /auth/me até aqui.
    expect(meAntesDeSalvar).toBe(1);

    await user.click(botao);
    await screen.findByText("Salvo!", { exact: false }).catch(() => undefined);

    const meDepoisDeSalvar = server.calls.filter(
      (call) => call.method === "GET" && call.url === "/auth/me",
    ).length;
    // `refresh()` ao final do salvamento chama /auth/me de novo — mas só essa
    // vez. Antes do fix, `save` chamava uma vez extra, e o total seria 3.
    expect(meDepoisDeSalvar).toBe(2);
  });
});
