/**
 * As regras novas da porta de entrada.
 *
 * Três mudanças de comportamento, cada uma com um jeito próprio de falhar
 * silenciosamente — daí os testes:
 *
 * 1. A confirmação de e-mail só pode ser tentada UMA vez por token. O token é
 *    de uso único, e uma segunda chamada recebe "link inválido" sobre o token
 *    que ela mesma acabou de gastar: o e-mail é confirmado e a tela diz que
 *    não. Foi exatamente o defeito relatado.
 * 2. O cadastro não loga mais ninguém, e pergunta nascimento e residência.
 * 3. Quem não confirmou recebe 403 e precisa de um caminho de volta.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { OfflineProvider } from "@/hooks/useOffline";
import { mockServer, type MockServer } from "./server";

// A tela de entrada mora em /entrar desde que a raiz passou a apresentar o app.
function renderApp(server: MockServer, path = "/entrar") {
  window.history.pushState({}, "", path);
  return {
    server,
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <OfflineProvider>
          <AppStateProvider>
            <App />
          </AppStateProvider>
        </OfflineProvider>
      </AuthProvider>,
    ),
  };
}

const semSessao = () => ({ status: 401, body: { detail: "sem sessão" } });

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("confirmação de e-mail", () => {
  it("chama a rota uma única vez, mesmo com a sessão mudando de estado", async () => {
    // `status` sai de "checking" para "anonymous" logo após a montagem. Antes
    // da correção, isso reexecutava o efeito e queimava o token duas vezes.
    const server = mockServer({
      "GET /auth/me": semSessao,
      "POST /auth/verify-email": () => ({ body: { detail: "E-mail confirmado." } }),
    });
    renderApp(server, "/confirmar-email?token=abc123");

    expect(await screen.findByRole("heading", { name: "E-mail confirmado" })).toBeInTheDocument();

    const tentativas = server.calls.filter((c) => c.url === "/auth/verify-email");
    expect(tentativas).toHaveLength(1);
  });

  it("mostra a falha quando o token realmente não serve", async () => {
    const server = mockServer({
      "GET /auth/me": semSessao,
      "POST /auth/verify-email": () => ({
        status: 400,
        body: { detail: "Link inválido ou expirado. Peça um novo e-mail de confirmação." },
      }),
    });
    renderApp(server, "/confirmar-email?token=velho");

    expect(await screen.findByText(/Link inválido ou expirado/)).toBeInTheDocument();
  });
});

describe("cadastro", () => {
  // O formulário é digitado campo a campo, e o @ consulta o servidor a cada
  // pausa. Com a suíte inteira em paralelo, os 5s padrão ficam no limite.
  vi.setConfig({ testTimeout: 15_000 });

  it("exige nascimento e residência antes de deixar enviar", async () => {
    const server = mockServer({ "GET /auth/me": semSessao });
    const { user } = renderApp(server, "/cadastro");

    await screen.findByRole("heading", { name: "Criar conta" });
    await user.type(screen.getByLabelText("Como quer ser chamado"), "Rodrigo");
    await user.type(screen.getByLabelText("E-mail"), "pessoa@exemplo.com");
    await user.type(screen.getByLabelText("Senha"), "Senha-Longa-9");

    // Nome, e-mail e senha completos, mas ainda falta onde mora e quando
    // nasceu: o botão continua desabilitado.
    expect(screen.getByRole("button", { name: "Criar conta" })).toBeDisabled();

    await user.type(screen.getByLabelText("Data de nascimento"), "1998-04-12");
    await user.type(screen.getByLabelText("Cidade onde mora"), "Vitória");
    // A UF é o select do app, não o nativo: escolhe-se como uma pessoa faz.
    await user.click(screen.getByRole("combobox", { name: "UF" }));
    await user.click(screen.getByRole("option", { name: "ES" }));

    expect(screen.getByRole("button", { name: "Criar conta" })).toBeEnabled();
  });

  it("manda os campos novos e termina pedindo a confirmação, sem logar", async () => {
    const server = mockServer({
      "GET /auth/me": semSessao,
      "POST /auth/signup": () => ({
        status: 201,
        body: { detail: "Conta criada. Confirme seu e-mail pelo link que enviamos para entrar." },
      }),
    });
    const { user } = renderApp(server, "/cadastro");

    await screen.findByRole("heading", { name: "Criar conta" });
    await user.type(screen.getByLabelText("Como quer ser chamado"), "Rodrigo");
    await user.type(screen.getByLabelText("E-mail"), "pessoa@exemplo.com");
    await user.type(screen.getByLabelText("Data de nascimento"), "1998-04-12");
    await user.type(screen.getByLabelText("Cidade onde mora"), "Vitória");
    // A UF é o select do app, não o nativo: escolhe-se como uma pessoa faz.
    await user.click(screen.getByRole("combobox", { name: "UF" }));
    await user.click(screen.getByRole("option", { name: "ES" }));
    await user.type(screen.getByLabelText("Senha"), "Senha-Longa-9");
    await user.click(screen.getByRole("button", { name: "Criar conta" }));

    // A tela seguinte é "confirme seu e-mail", não o app.
    expect(await screen.findByRole("heading", { name: "Confirme seu e-mail" })).toBeInTheDocument();

    const enviado = server.calls.find((c) => c.url === "/auth/signup")?.body as Record<string, unknown>;
    expect(enviado.birth_date).toBe("1998-04-12");
    expect(enviado.city).toBe("Vitória");
    expect(enviado.state).toBe("ES");
  });
});

describe("entrada com e-mail não confirmado", () => {
  it("oferece reenviar o link em vez de culpar a senha", async () => {
    const server = mockServer({
      "GET /auth/me": semSessao,
      "POST /auth/login": () => ({
        status: 403,
        body: { detail: "Confirme seu e-mail para entrar." },
        headers: { "X-Pathr-Unverified": "1" },
      }),
      "POST /auth/resend-verification-public": () => ({
        body: { detail: "Se houver uma conta com este e-mail aguardando confirmação, enviamos um novo link." },
      }),
    });
    const { user } = renderApp(server);

    await screen.findByRole("heading", { name: "Entrar" });
    await user.type(screen.getByLabelText("E-mail"), "pessoa@exemplo.com");
    await user.type(screen.getByLabelText("Senha"), "Senha-Longa-9");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    const reenviar = await screen.findByRole("button", { name: "Reenviar confirmação" });
    await user.click(reenviar);

    expect(await screen.findByText(/enviamos um novo link/)).toBeInTheDocument();
    expect(server.calls.some((c) => c.url === "/auth/resend-verification-public")).toBe(true);
  });
});

describe("campo de senha", () => {
  it("alterna entre oculto e visível sem perder o que foi digitado", async () => {
    const server = mockServer({ "GET /auth/me": semSessao });
    const { user } = renderApp(server);

    await screen.findByRole("heading", { name: "Entrar" });
    const campo = screen.getByLabelText("Senha") as HTMLInputElement;
    await user.type(campo, "Senha-Longa-9");
    expect(campo.type).toBe("password");

    const botao = screen.getByRole("button", { name: "Mostrar senha" });
    expect(botao).toHaveAttribute("aria-pressed", "false");

    await user.click(botao);
    expect(campo.type).toBe("text");
    expect(campo.value).toBe("Senha-Longa-9");
    // O rótulo acompanha o estado: um ícone que muda de desenho não diz nada
    // a quem usa leitor de tela.
    expect(screen.getByRole("button", { name: "Ocultar senha" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(campo.type).toBe("password");
  });
});
