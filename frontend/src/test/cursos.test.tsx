/**
 * A tela de cursos com certificado.
 *
 * O que se segura é o que a tela promete a quem vai pôr o certificado no
 * LinkedIn: o gratuito aparece antes do pago, o selo diz qual é qual, a barra
 * de chama tem rótulo em texto, e o vazio diz o que fazer.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Course, CourseList } from "@/api/types";
import { AppStateProvider } from "@/hooks/useAppState";
import { CoursesPage, linkParaLinkedIn } from "@/pages/CoursesPage";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const curso = (id: string, titulo: string, extra: Partial<Course> = {}): Course => ({
  id,
  titulo,
  emissor: "Emissor",
  url: `https://exemplo.org/${id}`,
  tags: ["AWS"],
  nivel: "iniciante",
  idioma: "en",
  horas: 6,
  certificado: { gratuito: true, detalhe: "Curso e certificado gratuitos." },
  demanda: { nota: 90, faixa: "pegando_fogo", rotulo: "Pegando fogo", motivo: "Cloud é requisito." },
  motivos: [{ tipo: "meta", tag: "AWS" }],
  relevancia: 3,
  ...extra,
});

function monta(resposta: CourseList) {
  mockServer({ "GET /courses": () => ({ body: resposta }) });
  return {
    user: userEvent.setup(),
    ...render(
      <AppStateProvider>
        <CoursesPage />
      </AppStateProvider>,
    ),
  };
}

const lista: CourseList = {
  conferido_em: "2026-05",
  tem_pedido: true,
  cursos: [
    curso("gratis", "AWS Cloud Practitioner Essentials"),
    curso("pago", "AWS Certified Cloud Practitioner", {
      certificado: { gratuito: false, detalhe: "Prova paga (cerca de US$ 100)." },
      demanda: { nota: 30, faixa: "basico", rotulo: "Chama apagada", motivo: null },
    }),
  ],
};

describe("cursos com certificado", () => {
  it("mostra o bloco gratuito antes do pago, cada um com seu selo", async () => {
    monta(lista);

    const gratuito = await screen.findByRole("region", { name: "Certificado gratuito" });
    const pago = screen.getByRole("region", { name: "Certificado pago" });
    // O gratuito vem antes no documento.
    expect(gratuito.compareDocumentPosition(pago) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(within(gratuito).getByText("AWS Cloud Practitioner Essentials")).toBeInTheDocument();
    expect(within(pago).getByText("Prova paga (cerca de US$ 100).")).toBeInTheDocument();
  });

  it("a barra de chama diz em texto quanto o conteúdo é procurado", async () => {
    monta(lista);

    const barras = await screen.findAllByRole("meter", { name: "Procura no mercado" });
    expect(barras.map((barra) => barra.getAttribute("aria-valuetext"))).toEqual([
      "Pegando fogo",
      "Chama apagada",
    ]);
    expect(screen.getByText("Pegando fogo")).toBeInTheDocument();
  });

  it("diz qual configuração trouxe o curso", async () => {
    monta(lista);
    expect((await screen.findAllByText("Sua meta: AWS")).length).toBe(2);
  });

  it("filtra só os gratuitos", async () => {
    const { user } = monta(lista);

    await user.click(await screen.findByRole("radio", { name: "Gratuitos" }));

    expect(screen.getByRole("region", { name: "Certificado gratuito" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Certificado pago" })).not.toBeInTheDocument();
  });

  it("sem objetivo, manda definir o que quer aprender", async () => {
    monta({ cursos: [], conferido_em: "2026-05", tem_pedido: false });
    expect(await screen.findByText("Diga o que você quer aprender")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Definir objetivo" })).toBeInTheDocument();
  });

  it("com pedido e sem curso, explica que falta certificação séria", async () => {
    monta({ cursos: [], conferido_em: "2026-05", tem_pedido: true });
    expect(
      await screen.findByText("Ainda não há certificação séria para o que você pediu"),
    ).toBeInTheDocument();
  });

  it("abre o formulário de certificação do LinkedIn já preenchido", () => {
    const url = new URL(linkParaLinkedIn(curso("x", "Intro to SQL", { emissor: "Kaggle Learn" }), new Date(2026, 8, 12)));
    expect(url.origin + url.pathname).toBe("https://www.linkedin.com/profile/add");
    expect(url.searchParams.get("startTask")).toBe("CERTIFICATION_NAME");
    expect(url.searchParams.get("name")).toBe("Intro to SQL");
    expect(url.searchParams.get("organizationName")).toBe("Kaggle Learn");
    expect(url.searchParams.get("issueYear")).toBe("2026");
    expect(url.searchParams.get("issueMonth")).toBe("9");
  });
});
