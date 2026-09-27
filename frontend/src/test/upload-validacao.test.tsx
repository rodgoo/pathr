/**
 * Arquivo recusado no cliente, antes de subir.
 *
 * O `accept` do <input> só filtra o seletor nativo: um arquivo solto por
 * arraste (currículo) ou escolhido em "todos os arquivos" (foto) chega de
 * qualquer tipo e tamanho. Sem a checagem aqui, ele sobe inteiro e só então o
 * servidor diz não.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Avatar } from "@/components/profile/Avatar";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { CvPage } from "@/pages/CvPage";
import { aUser, mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

function arquivo(nome: string, tipo: string, bytes = 1000): File {
  const f = new File(["x"], nome, { type: tipo });
  Object.defineProperty(f, "size", { value: bytes });
  return f;
}

describe("currículo solto por arraste", () => {
  function monta() {
    const servidor = mockServer({ "GET /resumes": () => ({ body: [] }) });
    render(
      <AppStateProvider>
        <CvPage />
      </AppStateProvider>,
    );
    return servidor;
  }
  const soltar = async (f: File) => {
    const area = (await screen.findByText(/Arraste o arquivo aqui/)).closest("label") as HTMLElement;
    fireEvent.drop(area, { dataTransfer: { files: [f] } });
  };

  it("recusa um tipo que o servidor não aceita, sem enviar", async () => {
    const servidor = monta();
    await soltar(arquivo("foto.png", "image/png"));
    expect(await screen.findByText(/Formato não aceito/)).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.method === "POST" && c.url === "/resumes")).toBe(false);
  });

  it("recusa um arquivo acima de 10 MB, sem enviar", async () => {
    const servidor = monta();
    await soltar(arquivo("cv.pdf", "application/pdf", 11 * 1024 * 1024));
    expect(await screen.findByText("O arquivo passa de 10 MB.")).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.method === "POST" && c.url === "/resumes")).toBe(false);
  });

  it("um arquivo válido segue para o servidor", async () => {
    const servidor = mockServer({
      "GET /resumes": () => ({ body: [] }),
      "POST /resumes": () => ({ status: 500, body: { detail: "falhou de propósito" } }),
    });
    render(
      <AppStateProvider>
        <CvPage />
      </AppStateProvider>,
    );
    await soltar(arquivo("cv.docx", "application/octet-stream"));
    expect(await screen.findByText("falhou de propósito")).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.method === "POST" && c.url === "/resumes")).toBe(true);
  });
});

describe("foto de perfil", () => {
  function monta() {
    const servidor = mockServer({ "GET /auth/me": () => ({ body: aUser() }) });
    const { container } = render(
      <AuthProvider>
        <Avatar nome="Lucas Martins" editavel />
      </AuthProvider>,
    );
    return { servidor, entrada: container.querySelector("input[type=file]") as HTMLInputElement };
  }

  it("recusa um tipo de imagem não aceito, sem enviar", async () => {
    const { servidor, entrada } = monta();
    await userEvent.setup({ applyAccept: false }).upload(entrada, arquivo("a.gif", "image/gif"));
    expect(await screen.findByRole("alert")).toHaveTextContent("JPG, PNG ou WebP");
    expect(servidor.calls.some((c) => c.url === "/profile/avatar")).toBe(false);
  });

  it("recusa uma foto acima de 5 MB, sem enviar", async () => {
    const { servidor, entrada } = monta();
    await userEvent.setup({ applyAccept: false }).upload(entrada, arquivo("a.png", "image/png", 6 * 1024 * 1024));
    expect(await screen.findByRole("alert")).toHaveTextContent("passa de 5 MB");
    expect(servidor.calls.some((c) => c.url === "/profile/avatar")).toBe(false);
  });
});
