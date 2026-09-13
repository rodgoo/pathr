/**
 * O material como TELA, não como caixa dentro da lista.
 *
 * Antes o vídeo e o artigo abriam expandindo a própria linha: uma moldura
 * dentro de outra, dentro do painel, dentro da moldura do app. No celular
 * sobravam uns 300px de largura para um player.
 *
 * O que estes testes seguram: abrir leva a uma tela, a tela mostra o
 * progresso, e o voltar devolve para a trilha — a aba de material do módulo,
 * que é de onde o material é alcançado desde que ela absorveu a Biblioteca.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "@/App";
import { INITIAL_STATE, type AppState } from "@/hooks/appState";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { OfflineProvider } from "@/hooks/useOffline";
import { aUser, mockServer, type Handler } from "./server";

const artigo = {
  id: "r-1",
  kind: "article",
  title: "Idempotência em processamento assíncrono",
  url: "https://exemplo.dev/idempotencia",
  provider: "Blog",
  author: null,
  description: null,
  duration_min: 12,
  language: "pt",
  level: null,
  tag_ids: ["t-1"],
  quality_score: 8,
  user_status: "in_progress",
  user_progress_pct: 40,
  user_rating: null,
  user_position_note: null,
  user_position_seconds: null,
};

/** Um plano com um módulo aberto: é por ele que se chega ao material. */
const plano = {
  id: "p-1",
  title: "Plano",
  horizon_weeks: 12,
  weekly_hours: 8,
  progress_pct: 0,
  phases: [
    {
      id: "f-1",
      title: "Fundamentos",
      description: null,
      week_start: 1,
      week_end: 4,
      order_index: 0,
      modules: [
        {
          id: "n-1",
          title: "Processamento assíncrono",
          description: null,
          kind: "skill",
          status: "doing",
          progress_pct: 0,
          level: null,
          estimated_hours: 10,
          week_start: 1,
          week_end: 2,
          tag_ids: ["t-1"],
          objectives: [],
          order_index: 0,
        },
      ],
    },
  ],
};

const shell: Record<string, Handler> = {
  "GET /auth/me": () => ({ body: aUser() }),
  "GET /roadmap/current": () => ({ body: plano }),
  "GET /languages/profile": () => ({
    body: { enabled: false, cefr_level: null, target_level: "B2", sub_scores: {}, daily_goal_min: 15 },
  }),
  "GET /library/r-1/reader": () => ({ status: 404, body: { detail: "sem texto" } }),
  "GET /library": () => ({ body: [artigo] }),
};

function abrirApp(estado: Partial<AppState> = {}) {
  mockServer(shell);
  return {
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <OfflineProvider>
          <AppStateProvider initialState={{ ...INITIAL_STATE, ...estado }}>
            <App />
          </AppStateProvider>
        </OfflineProvider>
      </AuthProvider>,
    ),
  };
}

// Espera de 3s, e não o 1s padrão: estes testes montam o app inteiro (barra
// lateral, plano, biblioteca, convites), e com a suíte toda rodando em
// paralelo a primeira pintura passa de 1s sem nada estar errado.
afterEach(() => vi.unstubAllGlobals());

it("abre o material numa tela, com o progresso no topo", async () => {
  const { user } = abrirApp({ screen: "modulo" });

  await user.click(await screen.findByRole("button", { name: /Idempotência/ }, { timeout: 3000 }));

  // O título vira o assunto da tela — um `h1`, não mais um `h3` dentro de uma
  // linha de lista.
  expect(
    await screen.findByRole("heading", { level: 1, name: /Idempotência/ }),
  ).toBeInTheDocument();
  // E o progresso fica em cima, onde responde "de onde eu retomo?" sem rolar.
  expect(screen.getByText("40% consumido")).toBeInTheDocument();
});

it("o voltar devolve para a trilha", async () => {
  const { user } = abrirApp({ screen: "modulo" });

  await user.click(await screen.findByRole("button", { name: /Idempotência/ }, { timeout: 3000 }));
  await screen.findByRole("heading", { level: 1, name: /Idempotência/ });
  await user.click(screen.getByRole("button", { name: "Voltar para Trilha" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Processamento assíncrono" }),
  ).toBeInTheDocument();
});

it("mantém acesa a aba de onde o material foi aberto", async () => {
  const { user } = abrirApp({ screen: "modulo" });

  await user.click(await screen.findByRole("button", { name: /Idempotência/ }, { timeout: 3000 }));
  await screen.findByRole("heading", { level: 1, name: /Idempotência/ });

  // A tela de material não tem aba própria. Apagar a barra inteira enquanto
  // se lê um artigo tiraria a referência de onde a pessoa está.
  const navegacao = screen.getByRole("navigation", { name: "Navegação principal" });
  expect(within(navegacao).getByRole("button", { name: "Trilha atual" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
