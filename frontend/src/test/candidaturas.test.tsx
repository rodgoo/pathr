/**
 * A aba de Candidaturas.
 *
 * O que se segura: sem currículo, a tela manda enviar o currículo antes; com
 * currículo, a fila do dia aparece; a vaga traz o LINK para abrir e responder
 * as perguntas do site; a carta é escrita e fica editável; e "Já me candidatei"
 * registra sem mandar e-mail nenhum.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Candidatura } from "@/api/types";
import { AppStateProvider } from "@/hooks/useAppState";
import { CandidaturasPage } from "@/pages/CandidaturasPage";
import { mockServer } from "./server";

const HOJE = "2026-09-15";

const vaga: Candidatura = {
  id: "c1",
  day: HOJE,
  source: "gupy",
  title: "Pessoa Desenvolvedora Java",
  company: "Empresa Boa",
  url: "https://empresaboa.gupy.io/jobs/123",
  location: "São Paulo, SP",
  remote: false,
  score: 82,
  snippet: "Java, Spring Boot e PostgreSQL no time de produto.",
  letter: null,
  answers: [],
  subject: null,
  to_email: null,
  status: "sugerida",
  sent_at: null,
  created_at: null,
};

function monta(comCurriculo = true, automatico = false) {
  let perfil = {
    user_id: "u1",
    notifications: { candidatura_automatica: automatico },
    salary_expectation: null,
    availability: null,
  };
  const servidor = mockServer({
    "GET /profile": () => ({ body: perfil }),
    "PATCH /profile": (pedido) => {
      perfil = { ...perfil, ...(pedido.body as object) };
      return { body: perfil };
    },
    "POST /candidaturas/c1/respostas": () => ({
      body: {
        ...vaga,
        answers: [{ pergunta: "Pretensão salarial", resposta: "R$ 9.000, aberto a conversar." }],
      },
    }),
    "GET /resumes": () => ({ body: comCurriculo ? [{ id: "r1", status: "parsed" }] : [] }),
    "GET /candidaturas": () => ({
      body: { hoje: HOJE, por_dia: 5, enviadas: 0, candidaturas: comCurriculo ? [vaga] : [] },
    }),
    "POST /candidaturas/c1/carta": () => ({
      body: { ...vaga, letter: "Trabalho com Java há três anos...", subject: "Candidatura — Dev Java" },
    }),
    "POST /candidaturas/c1/enviar": () => ({ body: { ...vaga, status: "enviada", sent_at: "2026-09-15T12:00:00Z" } }),
  });
  return {
    servidor,
    user: userEvent.setup(),
    ...render(
      <AppStateProvider>
        <CandidaturasPage />
      </AppStateProvider>,
    ),
  };
}

describe("candidaturas", () => {
  it("sem currículo analisado, manda enviar o currículo primeiro", async () => {
    monta(false);
    expect(await screen.findByText("Comece pelo seu currículo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Enviar meu currículo/ })).toBeInTheDocument();
  });

  it("mostra a vaga do dia com o link para responder as perguntas no site", async () => {
    monta();
    expect(await screen.findByText("Pessoa Desenvolvedora Java")).toBeInTheDocument();
    expect(screen.getByText("1 vaga separada para você")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Abrir vaga e responder/ });
    expect(link).toHaveAttribute("href", vaga.url);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("liga o envio automático, e ele fica registrado no perfil", async () => {
    const { user, servidor } = monta();
    const botao = await screen.findByRole("button", { name: "Enviar sozinho todo dia" });
    expect(botao).toHaveAttribute("aria-pressed", "false");

    await user.click(botao);

    const salvo = servidor.calls.find((c) => c.method === "PATCH" && c.url === "/profile");
    expect(salvo?.body).toEqual({ notifications: { candidatura_automatica: true } });
    expect(await screen.findByRole("button", { name: "Enviando sozinho" })).toHaveAttribute("aria-pressed", "true");
  });

  it("prepara as respostas do formulário para conferir e colar", async () => {
    const { user } = monta();
    await user.click(await screen.findByRole("button", { name: /Respostas do formulário/ }));

    // "Pretensão salarial" também é o rótulo do campo do perfil acima: a
    // pergunta que interessa é a que está junto da resposta.
    const resposta = await screen.findByText("R$ 9.000, aberto a conversar.");
    const bloco = resposta.closest("li") as HTMLElement;
    expect(within(bloco).getByText("Pretensão salarial")).toBeInTheDocument();
    expect(within(bloco).getByRole("button", { name: "Copiar" })).toBeInTheDocument();
  });

  it("escreve a carta, deixa editar e registra a candidatura feita no site", async () => {
    const { user, servidor } = monta();
    await user.click(await screen.findByRole("button", { name: /Escrever carta/ }));

    const campo = await screen.findByLabelText(/Carta de apresentação/);
    expect(campo).toHaveValue("Trabalho com Java há três anos...");
    await user.type(campo, " Sigo à disposição.");
    expect(campo).toHaveValue("Trabalho com Java há três anos... Sigo à disposição.");

    await user.click(screen.getByRole("button", { name: /Já me candidatei/ }));
    const envio = servidor.calls.find((c) => c.url === "/candidaturas/c1/enviar");
    // Sem e-mail: nada é mandado para ninguém, só fica registrado.
    expect(envio?.body).toEqual({});
  });
});
