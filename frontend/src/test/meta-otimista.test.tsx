/**
 * Alternar uma meta no Perfil ou ligar o módulo de idioma é otimista: a tela
 * muda na hora. Se o servidor recusar, o controle volta ao que estava e o erro
 * aparece — antes o botão ficava marcado como salvo com a escrita rejeitada.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { EnglishPage } from "@/pages/EnglishPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { aUser, anOverview, mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const tag = {
  id: "ut1",
  tag_id: "t1",
  slug: "java",
  name: "Java",
  category: "language",
  color: null,
  proficiency: 3,
  confidence: 0.9,
  is_target: false,
  source: "manual",
  last_assessed_at: null,
};

it("Perfil: se o servidor recusa a meta, o botão volta e o erro aparece", async () => {
  const user = userEvent.setup();
  mockServer({
    "GET /auth/me": () => ({ body: aUser() }),
    "GET /profile/overview": () => ({ body: anOverview() }),
    "GET /tags/mine": () => ({ body: [tag] }),
    "GET /courses": () => ({ body: [] }),
    "PATCH /tags/mine/ut1": () => ({ status: 500, body: { detail: "Banco indisponível." } }),
  });
  render(
    <AuthProvider>
      <AppStateProvider>
        <ProfilePage />
      </AppStateProvider>
    </AuthProvider>,
  );

  const botao = await screen.findByRole("button", { name: /Java/ });
  expect(botao).toHaveAttribute("aria-pressed", "false");
  await user.click(botao);

  expect(await screen.findByText("Banco indisponível.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Java/ })).toHaveAttribute("aria-pressed", "false");
});

it("Idiomas: se o servidor recusa o interruptor, ele volta e o erro aparece", async () => {
  const user = userEvent.setup();
  const perfil = {
    user_id: "u1",
    language: "en",
    enabled: true,
    cefr_level: "B1",
    target_level: "B2",
    sub_scores: {},
    focus_areas: [],
    daily_goal_min: 15,
    last_assessment_at: null,
  };
  mockServer({
    "GET /languages/profiles": () => ({ body: [perfil] }),
    "GET /languages/profile": () => ({ body: perfil }),
    "GET /languages/assessment/active": () => ({ body: null }),
    "PATCH /languages/profile": () => ({ status: 500, body: { detail: "Servidor recusou." } }),
  });
  render(
    <AppStateProvider>
      <EnglishPage />
    </AppStateProvider>,
  );

  const interruptor = await screen.findByRole("checkbox");
  expect(interruptor).toBeChecked();
  await user.click(interruptor);

  expect(await screen.findByText("Servidor recusou.")).toBeInTheDocument();
  expect(screen.getByRole("checkbox")).toBeChecked();
});
