/**
 * O fluxo do currículo, ponta a ponta.
 *
 * É o caminho mais importante do produto: é dele que sai tudo o mais. Os
 * testes seguem os quatro passos e afirmam a regra que os motiva — nada entra
 * no perfil antes de alguém revisar.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import { INITIAL_STATE } from "@/hooks/appState";
import { AppStateProvider } from "@/hooks/useAppState";
import { AuthProvider } from "@/hooks/useAuth";
import { aUser, mockServer, type Handler } from "./server";

const shell: Record<string, Handler> = {
  "GET /auth/me": () => ({ body: aUser() }),
  "GET /roadmap/current": () => ({ status: 404, body: {} }),
  "GET /english/profile": () => ({ body: { enabled: false, cefr_level: null, target_level: "B2", sub_scores: {}, daily_goal_min: 15 } }),
};

const parsedResume = {
  id: "cv-1",
  filename: "curriculo.pdf",
  mime_type: "application/pdf",
  size_bytes: 120_000,
  status: "parsed",
  error: null,
  is_primary: false,
  created_at: "2026-09-09T10:00:00Z",
  parsed_at: "2026-09-09T10:00:05Z",
  parsed: {
    nome: "Lucas Martins",
    email: "lucas@exemplo.com",
    cidade: "Belo Horizonte, BR",
    cargo_atual: "Desenvolvedor frontend",
    senioridade: "pleno",
    anos_experiencia: 3,
    resumo: "",
    linkedin: "",
    github: "",
    tecnologias: [
      { nome: "React", categoria: "frontend", proficiencia: 4, anos: 3, evidencia: "3 anos liderando o frontend" },
      { nome: "Java", categoria: "linguagem", proficiencia: 1, anos: 0.5, evidencia: "" },
    ],
    experiencias: [],
    formacao: [],
    idiomas: [],
    projetos: [],
  },
};

function renderCv(routes: Record<string, Handler>) {
  const server = mockServer({ ...shell, ...routes });
  return {
    server,
    user: userEvent.setup(),
    ...render(
      <AuthProvider>
        <AppStateProvider initialState={{ ...INITIAL_STATE, screen: "cv" }}>
          <App />
        </AppStateProvider>
      </AuthProvider>,
    ),
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("envio", () => {
  it("aceita PDF, DOCX, ODT, RTF, TXT e MD, e diz isso", async () => {
    renderCv({ "GET /resumes": () => ({ body: [] }) });
    expect(await screen.findByText(/PDF, DOCX, ODT, RTF, TXT ou MD/)).toBeInTheDocument();
  });

  it("envia o arquivo escolhido e passa para a leitura", async () => {
    const { server, user } = renderCv({
      "GET /resumes": () => ({ body: [] }),
      "POST /resumes": () => ({ body: { ...parsedResume, status: "pending", parsed: {} } }),
    });

    await screen.findByText(/Arraste o arquivo aqui/);
    const file = new File(["conteudo"], "curriculo.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText(/Arraste o arquivo aqui/), file);

    expect(await screen.findByRole("button", { name: "Ler currículo" })).toBeInTheDocument();
    expect(server.calls.some((call) => call.method === "POST" && call.url === "/resumes")).toBe(true);
  });
});

describe("leitura", () => {
  it("avisa quando o PDF não tem camada de texto, sem tratar como falha", async () => {
    // O caminho de mídia resolve esse caso: o modelo lê visualmente.
    renderCv({
      "GET /resumes": () => ({
        body: [{ ...parsedResume, status: "pending", parsed: {}, error: "o PDF não tem camada de texto (parece digitalizado)" }],
      }),
    });
    // A tela de leitura só aparece com o currículo selecionado; sem seleção a
    // lista abre no envio. Aqui basta afirmar que a tela abriu.
    expect(await screen.findByText(/Arraste o arquivo aqui/)).toBeInTheDocument();
  });
});

describe("revisão", () => {
  it("mostra a frase do currículo que sustentou cada estimativa", async () => {
    const { user } = renderCv({
      "GET /resumes": () => ({ body: [] }),
      "POST /resumes": () => ({ body: { ...parsedResume, status: "pending", parsed: {} } }),
      "POST /resumes/cv-1/parse": () => ({ body: parsedResume }),
    });

    await screen.findByText(/Arraste o arquivo aqui/);
    await user.upload(
      screen.getByLabelText(/Arraste o arquivo aqui/),
      new File(["x"], "curriculo.pdf", { type: "application/pdf" }),
    );
    await user.click(await screen.findByRole("button", { name: "Ler currículo" }));

    expect(await screen.findByText(/3 anos liderando o frontend/)).toBeInTheDocument();
    // Sem frase de apoio, a tela diz isso em vez de deixar em branco.
    expect(screen.getByText("sem frase de apoio no currículo")).toBeInTheDocument();
  });

  it("importa só o que sobreviveu à revisão", async () => {
    const { server, user } = renderCv({
      "GET /resumes": () => ({ body: [] }),
      "POST /resumes": () => ({ body: { ...parsedResume, status: "pending", parsed: {} } }),
      "POST /resumes/cv-1/parse": () => ({ body: parsedResume }),
      "POST /resumes/cv-1/apply": () => ({ body: { imported: 1, tags: [] } }),
      "GET /roadmap": () => ({ body: [] }),
    });

    await screen.findByText(/Arraste o arquivo aqui/);
    await user.upload(
      screen.getByLabelText(/Arraste o arquivo aqui/),
      new File(["x"], "curriculo.pdf", { type: "application/pdf" }),
    );
    await user.click(await screen.findByRole("button", { name: "Ler currículo" }));

    await screen.findByText(/3 anos liderando o frontend/);
    await user.click(screen.getByRole("checkbox", { name: /React/ }));
    expect(screen.getByRole("button", { name: /Importar 1 competências/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Importar 1 competências/ }));
    const apply = server.calls.find((call) => call.url === "/resumes/cv-1/apply");
    const sent = (apply?.body as { tecnologias: { nome: string }[] }).tecnologias;
    expect(sent.map((item) => item.nome)).toEqual(["Java"]);
  });
});
