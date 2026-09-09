/**
 * O que outro aparelho gravou aparece aqui.
 *
 * Todo dado de conta do PathR mora no servidor — nada fica só no navegador —
 * então quem ABRE uma tela agora já vê o estado certo. O buraco é a tela que
 * já estava aberta: marcar um módulo no celular não mexe no notebook que
 * ficou no ar a manhã inteira.
 *
 * Estes testes seguram o fechamento desse buraco, e o limite dele: reconferir
 * ao voltar ao app, mas não a cada troca rápida de janela.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useQuery } from "@/hooks/useApi";
import { AuthProvider } from "@/hooks/useAuth";
import { OfflineProvider } from "@/hooks/useOffline";
import { profile as profileApi } from "@/api/endpoints";
import { aUser, mockServer, type MockServer } from "./server";

/** Uma tela mínima que só lê do servidor — o alvo da reconferência. */
function Tela() {
  const perfil = useQuery(() => profileApi.get(), []);
  return <span>cargo: {(perfil.data as { current_role?: string } | null)?.current_role ?? "…"}</span>;
}

function montar(servidor: MockServer) {
  render(
    <AuthProvider>
      <OfflineProvider>
        <Tela />
      </OfflineProvider>
    </AuthProvider>,
  );
  return servidor;
}

const contaPerfil = (servidor: MockServer) =>
  servidor.calls.filter((c) => c.method === "GET" && c.url.startsWith("/profile")).length;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("reconferência entre dispositivos", () => {
  it("volta a perguntar ao servidor quando o app volta ao primeiro plano", async () => {
    let cargo = "Desenvolvedor pleno";
    const servidor = mockServer({
      "GET /auth/me": () => ({ body: aUser() }),
      "GET /profile": () => ({ body: { current_role: cargo } }),
    });
    montar(servidor);
    expect(await screen.findByText("cargo: Desenvolvedor pleno")).toBeInTheDocument();

    // Outro aparelho mudou o cargo, e o relógio andou o bastante para valer a
    // pena reconferir.
    cargo = "Backend sênior";
    const agora = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(agora + 60_000);
    window.dispatchEvent(new Event("focus"));

    expect(await screen.findByText("cargo: Backend sênior")).toBeInTheDocument();
  });

  it("não repergunta numa troca rápida de janela", async () => {
    const servidor = mockServer({
      "GET /auth/me": () => ({ body: aUser() }),
      "GET /profile": () => ({ body: { current_role: "Desenvolvedor pleno" } }),
    });
    montar(servidor);
    await screen.findByText("cargo: Desenvolvedor pleno");
    const antes = contaPerfil(servidor);

    // Sem avançar o relógio: a resposta na tela tem segundos de vida. Refazer
    // tudo a cada alt-tab só gastaria bateria.
    window.dispatchEvent(new Event("focus"));
    window.dispatchEvent(new Event("focus"));

    await waitFor(() => expect(contaPerfil(servidor)).toBe(antes));
  });
});
