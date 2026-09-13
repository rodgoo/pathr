/**
 * A página de apresentação, para quem ainda não tem conta.
 *
 * O que ela precisa garantir: aparece em / para visitante, leva a criar conta
 * e a entrar, e as telas de exemplo são inertes — um clique numa prévia não
 * pode chamar a API em nome de ninguém.
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

it("as telas de exemplo respondem ao visitante sem chamar a API", async () => {
  const servidor = abrir("/");
  await screen.findByRole("heading", { level: 1 });
  const figura = screen.getByRole("figure", { name: /Cartões de pessoas sugeridas/ });

  // Adicionar no cartão de exemplo muda a tela — e não manda convite nenhum.
  await userEvent.click(within(figura).getByRole("button", { name: "Adicionar" }));
  expect(await within(figura).findByText("Convite enviado")).toBeInTheDocument();

  // Marcar um módulo na trilha de exemplo sobe o progresso.
  const barra = screen.getByRole("progressbar", { name: "Progresso da trilha de exemplo" });
  const antes = Number(barra.getAttribute("aria-valuenow"));
  const trilha = screen.getByRole("figure", { name: /Módulos da fase atual/ });
  await userEvent.click(within(trilha).getAllByRole("button", { pressed: false })[0]);
  expect(Number(barra.getAttribute("aria-valuenow"))).toBeGreaterThan(antes);

  await new Promise((r) => setTimeout(r, 50));
  expect(servidor.calls.filter((c) => c.url.startsWith("/social"))).toHaveLength(0);
});

it("rodapé leva aos termos, à privacidade e à segurança", async () => {
  abrir("/");
  const rodape = await screen.findByRole("navigation", { name: "Termos e políticas" });
  for (const nome of ["Termos de uso", "Privacidade", "Segurança"]) {
    expect(within(rodape).getByRole("link", { name: nome })).toBeInTheDocument();
  }
});
