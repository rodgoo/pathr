/**
 * ObjectiveTab: `contextoSalvo` tem que refletir o que foi REALMENTE enviado.
 *
 * O bug: ao clicar num atalho, o botão chama `setContexto(proximo)` e then
 * `salvar({ goals: metas(proximo) })` — mas a instância de `salvar` criada
 * neste render ainda fecha sobre o `contexto` ANTES do clique (React só
 * aplica `setContexto` depois). A linha que gravava `contextoSalvo` lia esse
 * `contexto` antigo da closure em vez do `mudanca.goals` efetivamente
 * enviado, então `contextoSalvo` ficava atrasado mesmo depois do PUT ter
 * tido sucesso. Isso fazia o PRÓXIMO blur do textarea (sem nenhuma edição
 * nova) disparar um PUT redundante, porque a comparação com `contextoSalvo`
 * falhava à toa.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ObjectiveTab } from "@/components/profile/ObjectiveTab";
import { mockServer } from "./server";

const perfil = {
  user_id: "user-1",
  headline: null,
  current_role: null,
  target_role: null,
  seniority: null,
  years_experience: null,
  weekly_hours: 8,
  learning_style: null,
  goals: [],
  bio: null,
  linkedin_url: null,
  github_url: null,
};

afterEach(() => vi.unstubAllGlobals());

function montar() {
  const server = mockServer({
    "GET /profile": () => ({ body: perfil }),
    "PATCH /profile": () => ({ body: perfil }),
  });
  return { server, user: userEvent.setup(), ...render(<ObjectiveTab />) };
}

describe("ObjectiveTab: contextoSalvo depois de um atalho", () => {
  it("não dispara um PUT redundante no blur depois de um clique num atalho", async () => {
    const { server, user } = montar();

    const atalho = await screen.findByRole("button", { name: "Tenho 8h por semana" });
    await user.click(atalho);

    // Espera o PUT do clique terminar.
    await screen.findByText("Salvo!", { exact: false }).catch(() => undefined);
    const putsAposClique = server.calls.filter(
      (call) => call.method === "PATCH" && call.url === "/profile",
    ).length;
    expect(putsAposClique).toBe(1);

    // Sai do campo sem editar mais nada: se `contextoSalvo` estiver correto,
    // isto não deve bater outro PUT.
    const textarea = screen.getByLabelText(/Contexto para a geração do plano/i);
    textarea.focus();
    textarea.blur();

    const putsAposBlur = server.calls.filter(
      (call) => call.method === "PATCH" && call.url === "/profile",
    ).length;
    expect(putsAposBlur).toBe(1);
  });
});
