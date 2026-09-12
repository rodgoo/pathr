/**
 * Passar o mouse sobre um dia diz o que foi estudado nele.
 *
 * Antes o quadrado dizia só "11 de setembro · 4 atividades · 12 min", num
 * `title` nativo. Quatro atividades de quê? O balão lista cada uma com o tipo
 * (artigo, vídeo, nivelamento), o nome e o tempo — e declara quando o tempo é
 * estimado pelo tamanho do texto, em vez de fingir que foi cronometrado.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ConsistencyPanel } from "@/components/dashboard/ConsistencyPanel";
import { nomeDaAtividade, tempoPorExtenso } from "@/components/dashboard/DicaDoDia";
import { INITIAL_STATE } from "@/hooks/appState";
import { AppStateProvider } from "@/hooks/useAppState";
import type { ActivitySummary } from "@/api/types";

const atividade: ActivitySummary = {
  days: [
    {
      date: "2026-09-11",
      minutes: 42,
      count: 3,
      xp: 60,
      items: [
        { kind: "english_assessment", title: "Nivelamento concluído · B1", minutes: 12 },
        {
          kind: "resource_done",
          resource_kind: "article",
          title: "Learn to Use GitHub Actions",
          minutes: 15,
          estimated: true,
        },
        { kind: "resource_done", resource_kind: "video", title: "CI/CD em 20 min", minutes: 15 },
      ],
    },
  ],
  active_days: 1,
  total_minutes: 42,
  total_xp: 60,
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 12, 15, 0));
});
afterEach(() => vi.useRealTimers());

function montar(view: "ano" | "mes" | "semana") {
  render(
    <AppStateProvider initialState={{ ...INITIAL_STATE, constancyView: view }}>
      <ConsistencyPanel activity={atividade} />
    </AppStateProvider>,
  );
}

it.each(["ano", "mes", "semana"] as const)(
  "no recorte %s, o dia mostra o que foi feito e quanto tempo",
  (view) => {
    montar(view);
    const dia =
      view === "semana"
        ? screen.getByLabelText(/^Sex ·/)
        : screen.getByLabelText(/^11 de setembro/);

    fireEvent.mouseEnter(dia);

    const balao = screen.getByRole("tooltip");
    expect(within(balao).getByText("Sexta, 11 de setembro")).toBeInTheDocument();
    expect(within(balao).getByText("Artigo")).toBeInTheDocument();
    expect(within(balao).getByText("Learn to Use GitHub Actions")).toBeInTheDocument();
    expect(within(balao).getByText("Vídeo")).toBeInTheDocument();
    expect(within(balao).getByText("Nivelamento de idioma")).toBeInTheDocument();
    expect(within(balao).getByText("≈ 42 minutos")).toBeInTheDocument();
    expect(within(balao).getByText(/estimado pelo tamanho do texto/)).toBeInTheDocument();

    fireEvent.mouseLeave(dia);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  },
);

it("escreve o tempo por extenso, em horas ou minutos", () => {
  expect(tempoPorExtenso(1)).toBe("1 minuto");
  expect(tempoPorExtenso(42)).toBe("42 minutos");
  expect(tempoPorExtenso(60)).toBe("1 hora");
  expect(tempoPorExtenso(125)).toBe("2 horas e 5 minutos");
});

it("dá nome a material pelo tipo, e a atividade desconhecida não quebra", () => {
  expect(nomeDaAtividade({ kind: "resource_done", resource_kind: "doc", title: "", minutes: 0 })).toBe(
    "Documentação",
  );
  expect(nomeDaAtividade({ kind: "resource_done", title: "", minutes: 0 })).toBe("Material");
  expect(nomeDaAtividade({ kind: "algo_novo", title: "", minutes: 0 })).toBe("Atividade");
});
