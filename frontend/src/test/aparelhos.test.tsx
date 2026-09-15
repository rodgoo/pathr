/**
 * Aparelhos conectados: a lista mostra onde a conta está aberta e encerra um
 * aparelho sem derrubar este.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { Sessions } from "@/components/profile/AccountTab";
import { AuthProvider } from "@/hooks/useAuth";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const agora = new Date().toISOString();
const SESSOES = [
  { id: "f-pc", aparelho: "Chrome no Windows", navegador: "Chrome", sistema: "Windows", celular: false,
    ip: "189.40.12.…", ultimo_uso: agora, entrou_em: agora, este_aparelho: true },
  { id: "f-cel", aparelho: "Safari no iPhone", navegador: "Safari", sistema: "iPhone", celular: true,
    ip: null, ultimo_uso: agora, entrou_em: agora, este_aparelho: false },
];

it("lista os aparelhos, marca este e encerra outro sem sair daqui", async () => {
  const servidor = mockServer({
    "GET /auth/me": () => ({ body: { id: "u", email: "a@x.com", name: "Ana", email_verified: true } }),
    "GET /auth/sessoes": () => ({ body: SESSOES }),
    "DELETE /auth/sessoes/f-cel": () => ({ status: 204 }),
  });
  render(
    <AuthProvider>
      <Sessions />
    </AuthProvider>,
  );

  const lista = await screen.findByRole("list", { name: "Aparelhos conectados" });
  expect(within(lista).getByText("este aparelho")).toBeInTheDocument();
  expect(within(lista).getByText("Safari no iPhone")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Encerrar Safari no iPhone" }));
  await waitFor(() => expect(within(lista).queryByText("Safari no iPhone")).not.toBeInTheDocument());
  expect(servidor.calls.some((c) => c.method === "DELETE" && c.url === "/auth/sessoes/f-cel")).toBe(true);
  expect(servidor.calls.some((c) => c.url === "/auth/logout")).toBe(false);
});
