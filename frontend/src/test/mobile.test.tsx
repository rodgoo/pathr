/**
 * A moldura do celular.
 *
 * O que estes testes seguram é o que quebrou de verdade enquanto esta versão
 * era feita: a folha "Mais" ficou atrás da barra e escondeu o "Sair", e uma
 * exceção numa tela apagou o app inteiro para uma página em branco. Nenhum
 * dos dois aparece num teste de unidade das telas — só na moldura.
 *
 * jsdom não faz layout, então nada aqui afirma sobre pixels. O que dá para
 * afirmar, e é o que importa, é que os destinos EXISTEM e são alcançáveis.
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/AppShell";
import { INITIAL_STATE, type AppState } from "@/hooks/appState";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { OfflineProvider } from "@/hooks/useOffline";
import { aUser, mockServer, type Handler } from "./server";

const rotasDaMoldura: Record<string, Handler> = {
  "GET /auth/me": () => ({ body: aUser() }),
  "GET /roadmap/current": () => ({ status: 404, body: { detail: "sem plano" } }),
  "GET /languages/profile": () => ({
    body: { enabled: false, cefr_level: null, target_level: "B2", sub_scores: {}, daily_goal_min: 15 },
  }),
};

/**
 * jsdom não implementa `matchMedia`. Sem este dublê o app cai no layout
 * largo, que é o padrão de `useMediaQuery` — e nenhum teste de celular
 * exercitaria o celular.
 */
function fingeLargura(compacto: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches: compacto && query.includes("max-width"),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

function montaMoldura(conteudo = <p>conteúdo da tela</p>, estado: Partial<AppState> = {}) {
  mockServer(rotasDaMoldura);
  return {
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <OfflineProvider>
          <AppStateProvider initialState={{ ...INITIAL_STATE, ...estado }}>
            <AppShell>{conteudo}</AppShell>
          </AppStateProvider>
        </OfflineProvider>
      </AuthProvider>,
    ),
  };
}

beforeEach(() => fingeLargura(true));
afterEach(() => vi.unstubAllGlobals());

describe("moldura do celular", () => {
  it("troca a barra lateral por uma barra inferior", async () => {
    montaMoldura();

    const navegacao = await screen.findByRole("navigation", { name: "Navegação principal" });
    for (const destino of ["Início", "Roadmap", "Trilha", "Mais"]) {
      expect(within(navegacao).getByRole("button", { name: destino })).toBeInTheDocument();
    }
    // A lateral traz o mesmo rótulo de navegação; duas seria ambíguo para
    // quem navega por leitor de tela.
    expect(screen.getAllByRole("navigation")).toHaveLength(1);
  });

  it('mantém a lateral no desktop, sem barra inferior', async () => {
    fingeLargura(false);
    montaMoldura();

    expect(await screen.findByText("pathr.notter.com.br")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mais" })).not.toBeInTheDocument();
  });

  it('alcança o "Sair" pela folha do "Mais"', async () => {
    const { user } = montaMoldura();

    await user.click(await screen.findByRole("button", { name: "Mais" }));

    // Os quatro destinos que não cabem na barra, e a saída. O "Sair" ficava
    // atrás da barra fixa e existia sem dar para tocar.
    const folha = screen.getByRole("dialog", { name: "Mais destinos" });
    for (const destino of ["Cursos", "Vagas", "Treino de idiomas", "Perfil e tags", "Currículo", "Configurações", "Sair"]) {
      expect(within(folha).getByRole("button", { name: destino })).toBeInTheDocument();
    }
  });

  it("fecha a folha ao escolher um destino", async () => {
    const { user } = montaMoldura();

    await user.click(await screen.findByRole("button", { name: "Mais" }));
    await user.click(screen.getByRole("button", { name: "Currículo" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Mais destinos" })).not.toBeInTheDocument(),
    );
  });

  it("uma tela que quebra não leva o app junto", async () => {
    const Quebrada = () => {
      throw new Error("campo veio com outra forma");
    };
    // O limite registra o erro no console; silenciá-lo aqui evita poluir a
    // saída da suíte com um stack que o teste está justamente esperando.
    const consoleErro = vi.spyOn(console, "error").mockImplementation(() => {});

    montaMoldura(<Quebrada />);

    expect(await screen.findByText("Esta tela não abriu")).toBeInTheDocument();
    // O ponto: a navegação continua de pé, então dá para sair da tela quebrada.
    expect(screen.getByRole("button", { name: "Início" })).toBeInTheDocument();
    consoleErro.mockRestore();
  });
});

describe("girar o aparelho", () => {
  it("troca a moldura sem desmontar a tela aberta (o vídeo em tela cheia não fecha)", async () => {
    // Um matchMedia que dá para girar: muda a resposta e avisa quem assinou.
    let compacto = true;
    const ouvintes = new Set<() => void>();
    vi.stubGlobal(
      "matchMedia",
      (query: string) =>
        ({
          get matches() {
            return compacto && query.includes("max-width");
          },
          media: query,
          addEventListener: (_: string, fn: () => void) => ouvintes.add(fn),
          removeEventListener: (_: string, fn: () => void) => ouvintes.delete(fn),
        }) as unknown as MediaQueryList,
    );

    let montagens = 0;
    function TelaComVideo() {
      useEffect(() => {
        montagens += 1;
      }, []);
      return <p>player do vídeo</p>;
    }

    montaMoldura(<TelaComVideo />);
    expect(await screen.findByRole("button", { name: "Mais" })).toBeInTheDocument();
    expect(montagens).toBe(1);

    // Deitou o celular: a largura passa do limite e a moldura vira a larga.
    compacto = false;
    act(() => ouvintes.forEach((fn) => fn()));
    expect(await screen.findByText("pathr.notter.com.br")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mais" })).not.toBeInTheDocument();
    expect(screen.getByText("player do vídeo")).toBeInTheDocument();
    expect(montagens).toBe(1);

    // E voltou a ficar em pé.
    compacto = true;
    act(() => ouvintes.forEach((fn) => fn()));
    expect(await screen.findByRole("button", { name: "Mais" })).toBeInTheDocument();
    expect(montagens).toBe(1);
  });
});
