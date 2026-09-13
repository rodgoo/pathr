/**
 * A tela de vagas.
 *
 * O que se segura é o contrato com quem procura emprego: a fonte aparece em
 * cada vaga, a de cima é a que mais combina, "o que falta" aparece sozinho com
 * curso, voltar à tela não busca tudo de novo, e marcar uma lacuna como meta
 * não zera o nível de quem já estava começando naquela tecnologia.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Job, JobAnalysis, JobList } from "@/api/types";
import { AppStateProvider } from "@/hooks/useAppState";
import { esquecerVagas } from "@/lib/vagasGuardadas";
import { JobsPage } from "@/pages/JobsPage";
import { mockServer, type Handler } from "./server";

afterEach(() => {
  vi.unstubAllGlobals();
  esquecerVagas();
});

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
  compatibilidade: { nota: 67, tem: ["Java"], parcial: ["Docker"], falta: ["AWS"] },
  combina: 72,
  distancia_km: null,
  sobre: {
    apresentacao: "Somos uma fintech que cresce rápido.",
    faz: ["Construir APIs em Java"],
    pede: ["Experiência com Java", "AWS"],
    diferenciais: ["Docker"],
  },
  lacunas: [
    { nome: "AWS", slug: "aws", obrigatorio: true, situacao: "falta", tag_id: "t2", user_tag_id: null, e_meta: false, no_roadmap: false },
    { nome: "Docker", slug: "docker", obrigatorio: false, situacao: "parcial", tag_id: "t3", user_tag_id: "u3", e_meta: false, no_roadmap: false },
  ],
  ...extra,
});

const lista: JobList = {
  termos: ["Java"],
  fontes: { gupy: "ok", remotive: "ok", adzuna: "sem_chave", busca: "erro" },
  sem_perfil: false,
  regiao: { cidade: "Vitória", uf: "ES", raio_km: 50 },
  buscado_em: new Date().toISOString(),
  cursos: {
    aws: [{ id: "aws", titulo: "AWS Cloud Practitioner Essentials", emissor: "AWS Skill Builder", url: "https://skillbuilder.aws/", gratuito: true }],
    docker: [],
  },
  vagas: [
    vaga("gupy:1"),
    vaga("busca:2", {
      fonte: "LinkedIn",
      so_link: true,
      empresa: null,
      combina: 31,
      sobre: null,
      lacunas: [],
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
  ],
  ingles: { exigido: null, seu: "B2", situacao: null },
  lacunas: [
    {
      nome: "AWS", obrigatorio: true, situacao: "falta", tag_id: "t2", user_tag_id: null, e_meta: false,
      no_roadmap: false,
      cursos: [{ id: "aws", titulo: "AWS Cloud Practitioner Essentials", emissor: "AWS Skill Builder", url: "https://skillbuilder.aws/", gratuito: true }],
    },
  ],
};

function monta(extra: Record<string, Handler> = {}) {
  const servidor = mockServer({
    "GET /vagas": () => ({ body: lista }),
    "POST /vagas/analise": () => ({ body: analise }),
    ...extra,
  });
  const arvore = () => (
    <AppStateProvider>
      <JobsPage />
    </AppStateProvider>
  );
  return { servidor, user: userEvent.setup(), arvore, ...render(arvore()) };
}

describe("vagas", () => {
  it("mostra a fonte de cada vaga, o estado das fontes e a região", async () => {
    monta();
    expect(await screen.findByText(/via Gupy/)).toBeInTheDocument();
    expect(screen.getByText(/via LinkedIn/)).toBeInTheDocument();
    expect(screen.getByText("(sem chave configurada)")).toBeInTheDocument();
    expect(screen.getByText("(fora do ar agora)")).toBeInTheDocument();
    expect(screen.getByText(/até 50 km de Vitória - ES · remotas de qualquer lugar/)).toBeInTheDocument();
  });

  it("a nota do cartão é a de afinidade, e a de anúncio não lido é estimada", async () => {
    monta();
    const notas = await screen.findAllByRole("meter", { name: "Compatibilidade com o seu perfil" });
    expect(notas.map((n) => n.getAttribute("aria-valuenow"))).toEqual(["72", "31"]);
    expect(screen.getByText("estimado pelo título")).toBeInTheDocument();
  });

  it("o que falta aparece sozinho, com curso gratuito, sem chamar a análise", async () => {
    const { servidor } = monta();
    const [secao] = await screen.findAllByRole("region", { name: "O que falta para a vaga" });
    expect(within(secao).getByText("AWS")).toBeInTheDocument();
    expect(within(secao).getByText("AWS Cloud Practitioner Essentials")).toBeInTheDocument();
    expect(within(secao).getByText("diferencial", { exact: false })).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.url === "/vagas/analise")).toBe(false);
  });

  it("mostra o que é a vaga e abre a descrição sem ir ao servidor", async () => {
    const { user, servidor } = monta();
    expect(await screen.findByText("Somos uma fintech que cresce rápido.")).toBeInTheDocument();
    expect(screen.getByText(/nível Pleno, com Java, Docker e AWS/)).toBeInTheDocument();
    const antes = servidor.calls.length;
    await user.click(screen.getByRole("button", { name: "Ver descrição da vaga" }));
    expect(screen.getByText("Construir APIs em Java")).toBeInTheDocument();
    expect(servidor.calls.length).toBe(antes);
  });

  it("marcar como meta cria a tag nova e não zera o nível de quem já começou", async () => {
    const { user, servidor } = monta({
      "POST /tags/mine": () => ({ body: { id: "u2", tag_id: "t2", is_target: true, proficiency: 0 } }),
      "PATCH /tags/mine/u3": () => ({ body: { id: "u3", tag_id: "t3", is_target: true, proficiency: 1 } }),
    });
    const [secao] = await screen.findAllByRole("region", { name: "O que falta para a vaga" });
    const marcar = within(secao).getAllByRole("button", { name: "Marcar como meta" });
    await user.click(marcar[0]);
    await user.click(marcar[1]);

    expect(await within(secao).findAllByText("meta marcada")).toHaveLength(2);
    expect(servidor.calls.find((c) => c.method === "POST" && c.url === "/tags/mine")?.body).toEqual({
      tag_id: "t2", proficiency: 0, is_target: true,
    });
    // Docker já existia com nível 1: só vira meta, sem mandar proficiência.
    expect(servidor.calls.find((c) => c.method === "PATCH")?.body).toEqual({ is_target: true });
  });

  it("voltar à tela não busca de novo; Atualizar busca", async () => {
    const { servidor, user, arvore, unmount } = monta();
    await screen.findByText(/via Gupy/);
    unmount();
    render(arvore());
    await screen.findByText(/via Gupy/);
    expect(servidor.calls.filter((c) => c.url.startsWith("/vagas?")).length).toBe(1);

    await user.click(screen.getByRole("button", { name: "Atualizar" }));
    await screen.findByText(/via Gupy/);
    expect(servidor.calls.some((c) => c.url.includes("atualizar=true"))).toBe(true);
  });

  it("vaga de buscador oferece ler o anúncio completo pela IA", async () => {
    const { user, servidor } = monta();
    await user.click(await screen.findByRole("button", { name: "Ler o anúncio completo" }));
    expect(await screen.findByRole("region", { name: "Análise completa da vaga" })).toBeInTheDocument();
    expect(servidor.calls.find((c) => c.url === "/vagas/analise")?.body).toEqual({ vaga_id: "busca:2" });
  });

  it("analisa uma vaga colada pelo link", async () => {
    const { user, servidor } = monta();
    await user.type(await screen.findByLabelText("Link ou texto da vaga"), "https://www.vagas.com.br/vagas/v123");
    await user.click(screen.getByRole("button", { name: "Ver o que falta" }));

    expect(await screen.findByRole("region", { name: "Análise completa da vaga" })).toBeInTheDocument();
    expect(servidor.calls.find((c) => c.url === "/vagas/analise")?.body).toEqual({
      url: "https://www.vagas.com.br/vagas/v123",
    });
  });

  it("filtra internacionais na lista que já está aqui e mostra o inglês contra o seu nível", async () => {
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
            vaga("gupy:9", { titulo: "Dev Java Nacional" }),
          ],
        },
      }),
    });

    expect(await screen.findByText("Inglês C1 pedido · você B1")).toBeInTheDocument();
    expect(screen.getByText(/Internacional ·/)).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Internacionais" }));
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Dev Java Nacional")).not.toBeInTheDocument();
    expect(servidor.calls.filter((c) => c.url.startsWith("/vagas?")).length).toBe(1);
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
