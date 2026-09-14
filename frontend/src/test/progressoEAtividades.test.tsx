/**
 * A barra de progresso das esperas longas, e a fila de atividades práticas.
 *
 * Barra: anda sozinha mas não chega a 100% antes da resposta; ao terminar
 * mostra 100% e some; e aprende quanto a tarefa costuma demorar.
 *
 * Fila: ao abrir sem atividade aberta, gera uma; a correção vai com o id da
 * atividade; depois dela, "Próxima atividade" gera outra e a feita entra no
 * histórico com a nota.
 */

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RoadmapNode } from "@/api/types";
import { ActivityPanel } from "@/components/quiz/ActivityPanel";
import { ProgressoDaTarefa } from "@/components/ui/ProgressoDaTarefa";
import { duracaoEstimada, estimarPct, etapaDe, lembrarDuracao } from "@/lib/progresso";
import { mockServer } from "./server";

beforeEach(() => window.localStorage.clear());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("progresso estimado", () => {
  it("sobe depressa, desacelera e nunca chega a 100% sozinho", () => {
    expect(estimarPct(0, 10_000)).toBe(0);
    const meio = estimarPct(5_000, 10_000);
    const fim = estimarPct(10_000, 10_000);
    expect(meio).toBeGreaterThan(40);
    expect(fim).toBeGreaterThan(meio);
    expect(estimarPct(600_000, 10_000)).toBeLessThanOrEqual(95);
  });

  it("mostra a etapa da fração em que a barra está", () => {
    const etapas = ["Lendo", "Escrevendo", "Conferindo"];
    expect(etapaDe(0, etapas)).toBe("Lendo");
    expect(etapaDe(50, etapas)).toBe("Escrevendo");
    expect(etapaDe(99, etapas)).toBe("Conferindo");
  });

  it("aprende quanto a tarefa costuma levar", () => {
    expect(duracaoEstimada("quiz", 20_000)).toBe(20_000);
    lembrarDuracao("quiz", 8_000);
    lembrarDuracao("quiz", 12_000);
    expect(duracaoEstimada("quiz", 20_000)).toBe(10_000);
  });

  it("enche até 100% quando termina e some", () => {
    vi.useFakeTimers();
    const { rerender } = render(<ProgressoDaTarefa ativo chave="t" etapas={["Lendo", "Escrevendo"]} duracaoMs={10_000} />);
    act(() => {
      vi.advanceTimersByTime(4_000);
    });
    const valor = Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"));
    expect(valor).toBeGreaterThan(0);
    expect(valor).toBeLessThan(95);

    rerender(<ProgressoDaTarefa ativo={false} chave="t" etapas={["Lendo", "Escrevendo"]} duracaoMs={10_000} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText("Pronto")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});

const node = {
  id: "N1",
  title: "Git e GitHub Actions",
  objectives: ["Configurar repositórios remotos usando Git."],
} as unknown as RoadmapNode;

const atividade = (id: string, enunciado: string, extra = {}) => ({
  id,
  enunciado,
  tipo: "comandos",
  dicas: ["Pense no nome do remoto."],
  criada_em: "2026-09-13T10:00:00+00:00",
  respondida_em: null,
  nota: null,
  ...extra,
});

describe("fila de atividades", () => {
  it("gera ao abrir, corrige pela atividade e segue para a próxima", async () => {
    let proximas = 0;
    const servidor = mockServer({
      "GET /roadmap/nodes/N1/draft": () => ({ body: { content: "", updated_at: null } }),
      "PUT /roadmap/nodes/N1/draft": () => ({ body: { content: "", updated_at: null } }),
      "GET /roadmap/nodes/N1/atividades": () => ({ body: { atual: null, feitas: [], total_feitas: 0 } }),
      "POST /roadmap/nodes/N1/atividades/proxima": () => {
        proximas += 1;
        return {
          status: 201,
          body:
            proximas === 1
              ? atividade("A1", "Publique um repositório local no GitHub.")
              : atividade("A2", "Crie um workflow que rode os testes a cada push."),
        };
      },
      "POST /explanations": () => ({
        status: 201,
        body: { id: "e1", score: 82, feedback: "Boa.", gaps: [], sustenta: ["Usou o remoto certo"], fora_do_tema: false },
      }),
    });
    const user = userEvent.setup();
    render(<ActivityPanel node={node} />);

    expect(await screen.findByText("Publique um repositório local no GitHub.")).toBeInTheDocument();
    expect(screen.getByText("Ver dica")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Sua resposta"));
    await user.paste("git remote add origin URL\ngit push -u origin main  # publica o repositório");
    await user.click(screen.getByRole("button", { name: /Enviar para correção/ }));

    const envio = await vi.waitFor(() => {
      const achado = servidor.calls.find((c) => c.method === "POST" && c.url === "/explanations");
      if (!achado) throw new Error("ainda não enviou");
      return achado;
    });
    expect(envio.body).toMatchObject({ node_id: "N1", modo: "atividade", exercise_id: "A1" });
    expect(await screen.findByText("1 feita neste módulo")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: /Próxima atividade/ }));
    expect(await screen.findByText("Crie um workflow que rode os testes a cada push.")).toBeInTheDocument();
    expect(screen.getByLabelText("Sua resposta")).toHaveValue("");
    expect(screen.getByText("Atividades feitas neste módulo (1)")).toBeInTheDocument();
    expect(proximas).toBe(2);
  });

  it("com uma atividade aberta, mostra ela sem gerar outra", async () => {
    const servidor = mockServer({
      "GET /roadmap/nodes/N1/draft": () => ({ body: { content: "", updated_at: null } }),
      "GET /roadmap/nodes/N1/atividades": () => ({
        body: {
          atual: atividade("A7", "Desfaça o último commit sem perder as mudanças."),
          feitas: [atividade("A6", "Crie um branch novo.", { nota: 90, respondida_em: "2026-09-12T10:00:00+00:00" })],
          total_feitas: 1,
        },
      }),
    });
    render(<ActivityPanel node={node} />);
    expect(await screen.findByText("Desfaça o último commit sem perder as mudanças.")).toBeInTheDocument();
    expect(screen.getByText("1 feita neste módulo")).toBeInTheDocument();
    expect(servidor.calls.some((c) => c.url.endsWith("/atividades/proxima"))).toBe(false);
  });
});
