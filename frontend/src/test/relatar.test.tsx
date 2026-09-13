/**
 * Configurações › Relatar.
 *
 * A caixa de moderação só aparece para quem modera — mas o que protege os
 * relatos é o servidor; estes testes seguram o que a TELA faz: mandar a foto
 * como arquivo, recusar o que não é imagem antes do envio e mostrar ao autor
 * em que pé está o relato.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import * as auth from "@/hooks/useAuth";
import { RelatarTab } from "@/components/relatos/RelatarTab";
import { aUser, mockServer } from "./server";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function comoUsuario(campos = {}) {
  vi.spyOn(auth, "useAuth").mockReturnValue({ user: aUser(campos) } as unknown as ReturnType<typeof auth.useAuth>);
}

const relato = {
  id: "r1", kind: "reclamacao", message: "O botão salvar não responde.", page: "config",
  has_attachment: false, status: "em_analise", moderator_note: "Estamos vendo.",
  created_at: "2026-09-13T10:00:00Z", updated_at: null,
};

it("envia a mensagem com a foto como arquivo, e não como endereço", async () => {
  const servidor = mockServer({
    "GET /relatos/meus": () => ({ body: [] }),
    "POST /relatos": () => ({ status: 201, body: { ...relato, status: "aberto", moderator_note: null } }),
  });
  comoUsuario();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:previa", revokeObjectURL: () => {} }));
  const user = userEvent.setup();
  render(<RelatarTab />);

  await user.type(screen.getByLabelText("O que aconteceu?"), "O botão salvar não responde.");
  const png = new File([new Uint8Array([137, 80, 78, 71])], "print.png", { type: "image/png" });
  await user.upload(screen.getByLabelText("Anexar foto"), png);
  await user.click(screen.getByRole("button", { name: "Enviar relato" }));

  expect(await screen.findByText(/Relato enviado/)).toBeInTheDocument();
  const envio = servidor.calls.find((c) => c.method === "POST" && c.url === "/relatos");
  expect(envio).toBeTruthy();
});

it("recusa arquivo que não é imagem antes de enviar", async () => {
  const servidor = mockServer({ "GET /relatos/meus": () => ({ body: [] }) });
  comoUsuario();
  const user = userEvent.setup({ applyAccept: false });
  render(<RelatarTab />);

  const html = new File(["<script>alert(1)</script>"], "print.html", { type: "text/html" });
  await user.upload(screen.getByLabelText("Anexar foto"), html);

  expect(screen.getByRole("alert")).toHaveTextContent("JPG, PNG ou WebP");
  expect(servidor.calls.some((c) => c.method === "POST")).toBe(false);
});

it("mostra ao autor o status e a resposta da moderação", async () => {
  mockServer({ "GET /relatos/meus": () => ({ body: [relato] }) });
  comoUsuario();
  render(<RelatarTab />);
  expect(await screen.findByText("Em análise")).toBeInTheDocument();
  expect(screen.getByText("Estamos vendo.")).toBeInTheDocument();
});

it("a caixa de moderação só aparece para a conta moderadora", async () => {
  mockServer({
    "GET /relatos/meus": () => ({ body: [] }),
    "GET /relatos/moderacao": () => ({
      body: [{ ...relato, author: { name: "Ana", username: "anasouza", email: "ana@exemplo.com" } }],
    }),
  });
  comoUsuario({ is_moderator: false });
  const { unmount } = render(<RelatarTab />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Enviar relato" })).toBeInTheDocument());
  expect(screen.queryByText("Moderação")).not.toBeInTheDocument();
  unmount();

  comoUsuario({ is_moderator: true });
  render(<RelatarTab />);
  expect(await screen.findByText("Moderação")).toBeInTheDocument();
  expect(await screen.findByText(/@anasouza/)).toBeInTheDocument();
});
