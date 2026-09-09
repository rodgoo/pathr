/**
 * As derivações do painel, agora sobre atividade real.
 *
 * Antes elas geravam séries a partir de uma semente; agora recebem as linhas
 * do servidor. O que continua valendo teste é a aritmética: bucketização do
 * heatmap, alinhamento do calendário e os agregados que a tela mostra.
 */

import { describe, expect, it } from "vitest";
import {
  heatLevel,
  humanMinutes,
  monthGrid,
  rangeSummary,
  streakDays,
  weekBars,
  yearHeat,
} from "@/lib/dashboard";
import type { ActivitySummary } from "@/api/types";

function activity(days: { date: string; minutes: number; count?: number }[]): ActivitySummary {
  return {
    days: days.map((day) => ({ ...day, count: day.count ?? 1, xp: 10 })),
    active_days: days.length,
    total_minutes: days.reduce((sum, day) => sum + day.minutes, 0),
    total_xp: days.length * 10,
  };
}

// Uma quarta-feira, para os testes de alinhamento não dependerem de "hoje".
const WEDNESDAY = new Date(2026, 8, 9);

describe("degraus do heatmap", () => {
  it("usa escala fixa, não relativa ao próprio histórico", () => {
    // Escala relativa faria o mapa de quem estuda 20 min/dia parecer igual ao
    // de quem estuda 2h — e a pergunta que o mapa responde é "quanto".
    expect(heatLevel(0)).toBe(0);
    expect(heatLevel(1)).toBe(1);
    expect(heatLevel(19)).toBe(1);
    expect(heatLevel(20)).toBe(2);
    expect(heatLevel(44)).toBe(2);
    expect(heatLevel(45)).toBe(3);
    expect(heatLevel(90)).toBe(4);
    expect(heatLevel(600)).toBe(4);
  });
});

describe("mapa do ano", () => {
  it("cobre 53 semanas cheias", () => {
    expect(yearHeat(activity([]), WEDNESDAY)).toHaveLength(371);
  });

  it("preenche os dias sem estudo em vez de omiti-los", () => {
    // É o buraco que mostra a quebra de constância.
    const cells = yearHeat(activity([]), WEDNESDAY);
    expect(cells.every((cell) => cell.minutes === 0)).toBe(true);
    expect(cells[0].title).toContain("nenhuma atividade");
  });

  it("casa o dia com a atividade daquela data", () => {
    const cells = yearHeat(activity([{ date: "2026-09-09", minutes: 45, count: 2 }]), WEDNESDAY);
    const day = cells.find((cell) => cell.date === "2026-09-09");
    expect(day?.minutes).toBe(45);
    expect(day?.title).toContain("2 atividades");
    expect(day?.title).toContain("9 de setembro");
  });
});

describe("calendário do mês", () => {
  const cells = monthGrid(activity([{ date: "2026-09-09", minutes: 60 }]), WEDNESDAY);

  it("alinha na segunda-feira e cobre semanas inteiras", () => {
    expect(cells.length % 7).toBe(0);
  });

  it("marca dias fora do mês como buraco, não como dia sem estudo", () => {
    // Setembro de 2026 começa numa terça: a primeira célula é vazia.
    expect(cells[0].outside).toBe(true);
    expect(cells[0].day).toBe("");
    expect(cells[1].day).toBe("1");
  });

  it("mostra os minutos do dia com atividade", () => {
    const day = cells.find((cell) => cell.day === "9");
    expect(day?.minutesLabel).toBe("60m");
  });
});

describe("barras da semana", () => {
  const bars = weekBars(activity([{ date: "2026-09-09", minutes: 90 }]), WEDNESDAY);

  it("tem os sete dias, começando na segunda", () => {
    expect(bars).toHaveLength(7);
    expect(bars[0].label).toBe("Seg");
  });

  it("marca hoje", () => {
    expect(bars[2].today).toBe(true);
    expect(bars[2].minutes).toBe(90);
  });

  it("dá um piso visível ao dia zerado para o eixo continuar legível", () => {
    expect(bars[6].height).toBe(2);
    expect(bars[6].value).toBe("—");
  });
});

describe("resumo do recorte", () => {
  const data = activity([
    { date: "2026-09-07", minutes: 30 },
    { date: "2026-09-09", minutes: 90 },
  ]);

  it("conta dias ativos e tempo a partir dos mesmos dias que o gráfico desenha", () => {
    const summary = rangeSummary(data, "semana", WEDNESDAY);
    expect(summary.stats[0].value).toBe("2");
    expect(summary.stats[1].value).toBe("2h");
    expect(summary.stats[2].value).toBe("60 min");
  });

  it("nomeia o período de cada recorte", () => {
    expect(rangeSummary(data, "ano", WEDNESDAY).title).toContain("2026");
    expect(rangeSummary(data, "mes", WEDNESDAY).title).toContain("Setembro");
    expect(rangeSummary(data, "semana", WEDNESDAY).title).toBe("Esta semana");
  });

  it("não inventa média quando não houve estudo", () => {
    const summary = rangeSummary(activity([]), "semana", WEDNESDAY);
    expect(summary.stats[2].value).toBe("—");
  });
});

describe("formatação de tempo", () => {
  it("escolhe a unidade que cabe", () => {
    expect(humanMinutes(0)).toBe("0 min");
    expect(humanMinutes(45)).toBe("45 min");
    expect(humanMinutes(60)).toBe("1h");
    expect(humanMinutes(340)).toBe("5h40");
  });
});

describe("faixa da sequência", () => {
  it("marca o dia estudado e o dia de hoje", () => {
    const days = streakDays(activity([{ date: "2026-09-09", minutes: 20 }]), WEDNESDAY);
    expect(days[2]).toMatchObject({ label: "Qua", done: true, today: true });
    expect(days[0].done).toBe(false);
  });
});
