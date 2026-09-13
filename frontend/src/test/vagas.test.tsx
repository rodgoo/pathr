/**
 * A tela de vagas.
 *
 * O que se segura é o contrato com quem procura emprego: a fonte aparece em
 * cada vaga, a nota só existe quando o anúncio foi lido, "o que falta" mostra
 * as lacunas com curso, e marcar uma lacuna como meta não zera o nível de quem
 * já estava começando naquela tecnologia.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Job, JobAnalysis, JobList } from "@/api/types";
import { AppStateProvider } from "@/hooks/useAppState";
import { JobsPage } from "@/pages/JobsPage";
import { mockServer, type Handler } from "./server";

afterEach(() => vi.unstubAllGlobals());

const vaga = (id: string, extra: Partial<Job> = {}): Job => ({
  id,
  titulo: "Desenvolvedor Java Pleno",
  empresa: "ACME",
  url: `https://acme.gupy.io/job/${id}`,
  fonte: "Gupy",
  local: "Remoto",
  remota: true,
  publicada_ha_dias: 2,
  nivel: "pleno",
  na_sua_regiao: false,
  so_link: false,
  so_trecho: false,
  internacional: false,
  ingles: { exigido: null, seu: "B2", situacao: null },
  resumo: "Java e AWS",
  compatibilidade: { nota: 67, tem: ["Java"], parcial: [], falta: ["AWS"] },
  ...extra,
});

const lista: JobList = {
  termos: ["Java"],
  fontes: { gupy: "ok", remotive: "ok", adzuna: "sem_chave", busca: "erro" },
  sem_perfil: false,
  vagas: [
    vaga("gupy:1"),
    vaga("busca:2", {
      fonte: "LinkedIn",
      so_link: true,
      empresa: null,
      compatibilidade: { nota: null, tem: [], parcial: [], falta: [] },
    }),
  ],
};

const analise: JobAnalysis = {
  titulo: "Desenvolvedor Java Pleno",
  empresa: "ACME",
  senioridade: "pleno",
  resumo: "Construir APIs.",
  url: "https://acme.gupy.io/job/1",
  usou_ia: true,
  nota: 50,
  requisitos: [
    { nome: "Java", obrigatorio: true, situacao: "tem", tag_id: "t1", user_tag_id: "u1", e_meta: false },
    { nome: "AWS", obrigatorio: true, situacao: "falta", tag_id: "t2", user_tag_id: null, e_meta: false },
    { nome: "Docker", obrigatorio: false, situacao: "parcial", tag_id: "t3", user_tag_id: "u3", e_meta: false },
  ],
  ingles: { exigido: null, seu: "B2", situacao: null },
  lacunas: [
    {
      nome: "AWS", obrigatorio: true, situacao: "falta", tag_id: "t2", user_tag_id: null, e_meta: false,
      no_roadmap: false,
      cursos: [{ id: "aws", titulo: "AWS Cloud Practitioner Essentials", emissor: "AWS Skill Builder", url: "https://skillbuilder.aws/", gratuito: true }],
    },
    {
      nome: "Docker", obrigatorio: false, situacao: "parcial", tag_id: "t3", user_tag_id: "u3", e_meta: false,
      no_roadmap: false, cursos: [],
    },
  ],
};

function monta(extra: Record<string, Handler> = {}) {
  const servidor = mockServer({
    "GET /vagas": () => ({ body: lista }),
    "POST /vagas/analise": () => ({ body: analise }),
    ...extra,
  });
  return {
    servidor,
    user: userEvent.setup(),
    ...render(
      <AppStateProvider>
        <JobsPage />
      </AppStateProvider>,
    ),
  };
}

describe("vagas", () => {
  it("mostra a fonte de cada vaga e o estado das fontes", async () => {
    monta();
    expect(await screen.findByText(/via Gupy/)).toBeInTheDocument();
    expect(screen.getByText(/via LinkedIn/)).toBeInTheDocument();
    expect(screen.getByText("(sem chave configurada)")).toBeInTheDocument();
    expect(screen.getByText("(fora do ar agora)")).toBeInTheDocument();
  });

  it("dá nota só à vaga cujo anúncio foi lido", async () => {
    monta();
    const notas = await screen.findAllByRole("meter", { name: "Compatibilidade com o seu perfil" });
    expect(notas).toHaveLength(1);
    expect(notas[0]).toHaveAttribute("aria-valuenow", "67");
    expect(screen.getByText("anúncio não lido")).toBeInTheDocument();
  });

  it("o que falta traz a lacuna com curso gratuito", async () => {
    const { user, servidor } = monta();
    const [primeira] = await screen.findAllByRole("button", { name: "O que falta para esta vaga" });
    await user.click(primeira);

    const secao = await screen.findByRole("region", { name: "O que falta para a vaga" });
    expect(within(secao).getByText("AWS Cloud Practitioner Essentials")).toBeInTheDocument();
    expect(within(secao).getByText(/certificado gratuito/)).toBeInTheDocument();
    expect(servidor.calls.find((c) => c.url === "/vagas/analise")?.body).toEqual({ vaga_id: "gupy:1" });
  });

  it("marcar como meta cria a tag nova e não zera o nível de quem já começou", async () => {
    const { user, servidor } = monta({
      "POST /tags/mine": () => ({ body: { id: "u2", tag_id: "t2", is_target: true, proficiency: 0 } }),
      "PATCH /tags/mine/u3": () => ({ body: { id: "u3", tag_id: "t3", is_target: true, proficiency: 1 } }),
    });
    const [primeira] = await screen.findAllByRole("button", { name: "O que falta para esta vaga" });
    await user.click(primeira);

    const marcar = await screen.findAllByRole("button", { name: "Marcar como meta" });
    await user.click(marcar[0]);
    await user.click(marcar[1]);

    expect(await screen.findAllByText("meta marcada")).toHaveLength(2);
    expect(servidor.calls.find((c) => c.method === "POST" && c.url === "/tags/mine")?.body).toEqual({
      tag_id: "t2", proficiency: 0, is_target: true,
    });
    // Docker já existia com nível 1: só vira meta, sem mandar proficiência.
    expect(servidor.calls.find((c) => c.method === "PATCH")?.body).toEqual({ is_target: true });
  });

  it("analisa uma vaga colada pelo link", async () => {
    const { user, servidor } = monta();
    await user.type(await screen.findByLabelText("Link ou texto da vaga"), "https://www.vagas.com.br/vagas/v123");
    await user.click(screen.getByRole("button", { name: "Ver o que falta" }));

    expect(await screen.findByRole("region", { name: "O que falta para a vaga" })).toBeInTheDocument();
    expect(servidor.calls.find((c) => c.url === "/vagas/analise")?.body).toEqual({
      url: "https://www.vagas.com.br/vagas/v123",
    });
  });

  it("filtra internacionais e mostra o inglês pedido contra o seu nível", async () => {
    const { user, servidor } = monta({
      "GET /vagas": () => ({
        body: {
          ...lista,
          nivel_ingles: "B1",
          vagas: [
            vaga("remotive:1", {
              titulo: "Backend Engineer",
              fonte: "Remotive",
              internacional: true,
              ingles: { exigido: "C1", seu: "B1", situacao: "falta" },
            }),
          ],
        },
      }),
    });

    expect(await screen.findByText("Inglês C1 pedido · você B1")).toBeInTheDocument();
    expect(screen.getByText(/Internacional ·/)).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Internacionais" }));
    await screen.findByText("Inglês C1 pedido · você B1");
    expect(servidor.calls.some((c) => c.url.includes("alcance=internacionais"))).toBe(true);
  });

  it("sem nivelamento, oferece fazer o teste de inglês", async () => {
    monta({ "GET /vagas": () => ({ body: { ...lista, nivel_ingles: null } }) });
    expect(await screen.findByRole("button", { name: "sem nivelamento — fazer agora" })).toBeInTheDocument();
  });

  it("sem perfil, manda cadastrar tecnologias", async () => {
    monta({ "GET /vagas": () => ({ body: { termos: [], vagas: [], fontes: {}, sem_perfil: true } }) });
    expect(await screen.findByText("Diga o que você faz ou quer fazer")).toBeInTheDocument();
  });
});
