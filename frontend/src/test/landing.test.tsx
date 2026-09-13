/**
 * A página de apresentação, para quem ainda não tem conta.
 *
 * O que ela precisa garantir: aparece em / para visitante, leva a criar conta
 * e a entrar, e as telas de exemplo são inertes — um clique numa prévia não
 * pode chamar a API em nome de ninguém.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "@/App";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { OfflineProvider } from "@/hooks/useOffline";
import { mockServer } from "./server";

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

function abrir(path: string) {
  window.history.pushState({}, "", path);
  const servidor = mockServer({ "GET /auth/me": () => ({ status: 401, body: { detail: "Não autenticado." } }) });
  render(
    <AuthProvider>
      <OfflineProvider>
        <AppStateProvider>
          <App />
        </AppStateProvider>
      </OfflineProvider>
    </AuthProvider>,
  );
  return servidor;
}

it("visitante sem conta vê a apresentação em /", async () => {
  abrir("/");
  expect(await screen.findByRole("heading", { level: 1, name: /se corrige toda semana/ })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /Criar conta/ }).length).toBeGreaterThan(0);
});

it("Entrar leva à tela de login", async () => {
  abrir("/");
  await userEvent.click(await screen.findByRole("link", { name: "Entrar" }));
  expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
});

it("as telas de exemplo são inertes e não chamam a API", async () => {
  const servidor = abrir("/");
  await screen.findByRole("heading", { level: 1 });
  const figura = screen.getByRole("figure", { name: /Cartões de pessoas sugeridas/ });
  expect(figura.querySelector("[inert]")).not.toBeNull();
  // Mesmo forçando o clique por fora do `inert` (o jsdom nem o implementa),
  // o cartão de exemplo não manda convite. O único POST da página é a tentativa
  // de renovar a sessão, que o app faz ao receber 401 — não é da prévia.
  figura.querySelector("button")?.click();
  await new Promise((r) => setTimeout(r, 50));
  expect(servidor.calls.filter((c) => c.url.startsWith("/social"))).toHaveLength(0);
});
