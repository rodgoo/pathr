/**
 * Região das vagas nas Configurações: a cidade sai de uma sugestão (o nome
 * que o servidor sabe localizar), e o raio grava o número escolhido.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { profile as profileApi } from "@/api/endpoints";
import type { Profile } from "@/api/types";
import { RegiaoDasVagas } from "@/components/profile/RegiaoDasVagas";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

function Painel({ inicial }: { inicial: Partial<Profile> }) {
  const [perfil, setPerfil] = useState({ user_id: "u", weekly_hours: 8, goals: [], ...inicial } as Profile);
  return (
    <RegiaoDasVagas
      perfil={perfil}
      salvar={(mudanca) => {
        setPerfil((atual) => ({ ...atual, ...mudanca }));
        void profileApi.update(mudanca);
      }}
    />
  );
}

describe("região das vagas", () => {
  it("sugere cidades pelo começo do nome e grava a escolhida", async () => {
    const servidor = mockServer({
      "GET /geo/cidades": () => ({
        body: [
          { ibge: "3205309", nome: "Vitória", uf: "ES", capital: true },
          { ibge: "4128807", nome: "Vitorino", uf: "PR", capital: false },
        ],
      }),
      "PATCH /profile": ({ body }) => ({ body }),
    });
    const user = userEvent.setup();
    render(<Painel inicial={{}} />);

    await user.type(screen.getByRole("combobox", { name: "Cidade onde você mora" }), "Vit");
    const opcao = await screen.findByRole("option", { name: /Vitória/ });
    expect(screen.getByRole("option", { name: /Vitorino/ })).toBeInTheDocument();
    await user.click(opcao);

    expect(servidor.calls.some((c) => c.url === "/geo/cidades?q=Vit")).toBe(true);
    expect(servidor.calls.find((c) => c.method === "PATCH")?.body).toEqual({ city: "Vitória", state: "ES" });
    expect(screen.getByRole("combobox", { name: "Cidade onde você mora" })).toHaveValue("Vitória - ES");
    expect(screen.getByText(/até 50 km de Vitória - ES/)).toBeInTheDocument();
  });

  it("o raio grava o número, e 'Só remotas' grava zero", async () => {
    const servidor = mockServer({ "PATCH /profile": ({ body }) => ({ body }) });
    const user = userEvent.setup();
    render(<Painel inicial={{ city: "Vitória", state: "ES" }} />);

    expect(screen.getByRole("radio", { name: "50 km" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("radio", { name: "100 km" }));
    await user.click(screen.getByRole("radio", { name: "Só remotas" }));

    const enviados = servidor.calls.filter((c) => c.method === "PATCH").map((c) => c.body);
    expect(enviados).toEqual([{ job_radius_km: 100 }, { job_radius_km: 0 }]);
    expect(screen.getByText("Só vagas remotas vão aparecer.")).toBeInTheDocument();
  });
});
