/**
 * As páginas legais: termos, privacidade e segurança.
 *
 * O que precisam garantir: abrem pelo endereço, para visitante e para quem já
 * entrou; têm o título, o resumo e o sumário com âncoras; as abas levam de uma
 * a outra; e são só texto — nenhuma chamada à API além da checagem de sessão
 * que o app faz ao abrir.
 */

import { render, screen, within } from "@testing-library/react";
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

const PAGINAS = [
  ["/termos", "Termos de uso"],
  ["/privacidade", "Política de privacidade"],
  ["/seguranca", "Como protegemos sua conta"],
] as const;

it.each(PAGINAS)("%s abre com o título e não chama a API", async (path, titulo) => {
  const servidor = abrir(path);
  expect(await screen.findByRole("heading", { level: 1, name: titulo })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Em resumo" })).toBeInTheDocument();
  expect(screen.getByText(/13 de setembro de 2026/)).toBeInTheDocument();

  // Sumário com âncoras que apontam para seções que existem.
  const sumario = screen.getAllByRole("navigation", { name: /Nesta página/ })[0];
  const ancoras = within(sumario).getAllByRole("link");
  expect(ancoras.length).toBeGreaterThan(3);
  for (const ancora of ancoras) {
    const id = ancora.getAttribute("href")!.slice(1);
    expect(document.getElementById(id)).not.toBeNull();
  }

  await new Promise((r) => setTimeout(r, 50));
  // A checagem (e a tentativa de renovar) da sessão é do app, não da página.
  expect(servidor.calls.filter((c) => !c.url.startsWith("/auth"))).toHaveLength(0);
});

it("as abas levam de um documento ao outro e marcam o atual", async () => {
  abrir("/termos");
  const abas = await screen.findByRole("navigation", { name: "Documentos legais" });
  expect(within(abas).getByRole("link", { name: "Termos de uso" })).toHaveAttribute("aria-current", "page");

  await userEvent.click(within(abas).getByRole("link", { name: "Privacidade" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Política de privacidade" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/privacidade");
});

it("abre também para quem está logado, sem passar pelo app", async () => {
  window.history.pushState({}, "", "/seguranca");
  const servidor = mockServer({
    "GET /auth/me": () => ({
      body: { id: "u1", name: "Ana", email: "ana@exemplo.com", email_verified: true, onboarding_completed: true },
    }),
  });
  render(
    <AuthProvider>
      <OfflineProvider>
        <AppStateProvider>
          <App />
        </AppStateProvider>
      </OfflineProvider>
    </AuthProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: "Como protegemos sua conta" })).toBeInTheDocument();
  await new Promise((r) => setTimeout(r, 50));
  expect(servidor.calls.filter((c) => !c.url.startsWith("/auth"))).toHaveLength(0);
});

it("Voltar ao PathR leva à raiz", async () => {
  abrir("/privacidade");
  await userEvent.click(await screen.findByRole("link", { name: /Voltar ao PathR/ }));
  expect(window.location.pathname).toBe("/");
  await vi.waitFor(() =>
    expect(screen.queryByRole("heading", { level: 1, name: "Política de privacidade" })).not.toBeInTheDocument(),
  );
});
