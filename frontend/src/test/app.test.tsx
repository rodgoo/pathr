/**
 * As telas do produto, contra um servidor de mentira.
 *
 * O foco é o que a interface faz com a RESPOSTA: o vazio quando não há plano,
 * o erro quando a chamada falha, o fluxo do currículo. Aritmética de gráfico
 * é testada em dashboard.test.ts, sem montar componente.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import { INITIAL_STATE, type AppState } from "@/hooks/appState";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { aUser, anOverview, mockServer, type Handler } from "./server";

/** As rotas que a barra lateral pede em qualquer tela. */
const shell: Record<string, Handler> = {
  "GET /auth/me": () => ({ body: aUser() }),
  "GET /roadmap/current": () => ({ status: 404, body: { detail: "sem plano" } }),
  "GET /languages/profile": () => ({ body: { enabled: false, cefr_level: null, target_level: "B2", sub_scores: {}, daily_goal_min: 15 } }),
};

function renderApp(routes: Record<string, Handler>, state: Partial<AppState> = {}) {
  const server = mockServer({ ...shell, ...routes });
  return {
    server,
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <AppStateProvider initialState={{ ...INITIAL_STATE, ...state }}>
          <App />
        </AppStateProvider>
      </AuthProvider>,
    ),
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("painel", () => {
  it("convida ao onboarding quando ainda não há plano", async () => {
    renderApp({ "GET /profile/overview": () => ({ body: anOverview() }) });
    expect(await screen.findByText("Seu plano ainda não existe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar currículo" })).toBeInTheDocument();
  });

  it("mostra os números reais quando há plano", async () => {
    renderApp({
      "GET /profile/overview": () => ({
        body: anOverview({
          roadmap: {
            id: "r1",
            title: "De frontend a fullstack Java",
            horizon_weeks: 26,
            weekly_hours: 8,
            status: "active",
            total_nodes: 13,
            done_nodes: 4,
            progress_pct: 31,
            current_node: null,
          },
        }),
      }),
    });
    expect((await screen.findAllByText("31%")).length).toBeGreaterThan(0);
    expect(screen.getByText("3 dias")).toBeInTheDocument();
  });

  it("oferece tentar de novo quando a chamada falha", async () => {
    renderApp({
      "GET /profile/overview": () => ({ status: 500, body: { detail: "Banco indisponível." } }),
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Banco indisponível.");
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });
});

describe("barra lateral", () => {
  it("marca a tela atual", async () => {
    renderApp({ "GET /profile/overview": () => ({ body: anOverview() }) });
    const nav = within(await screen.findByRole("navigation", { name: "Navegação principal" }));
    expect(nav.getByRole("button", { name: /Início/ })).toHaveAttribute("aria-current", "page");
  });

  it("mostra off nos idiomas quando o módulo está desligado", async () => {
    renderApp({ "GET /profile/overview": () => ({ body: anOverview() }) });
    const nav = within(await screen.findByRole("navigation", { name: "Navegação principal" }));
    await waitFor(() =>
      expect(nav.getByRole("button", { name: /Idiomas/ })).toHaveTextContent("off"),
    );
  });

  it("navega entre telas", async () => {
    const { user } = renderApp({
      "GET /profile/overview": () => ({ body: anOverview() }),
      "GET /library": () => ({ body: [] }),
    });
    const nav = within(await screen.findByRole("navigation", { name: "Navegação principal" }));
    await user.click(nav.getByRole("button", { name: /Biblioteca/ }));
    expect(await screen.findByRole("heading", { level: 1, name: "Biblioteca" })).toBeInTheDocument();
  });
});
