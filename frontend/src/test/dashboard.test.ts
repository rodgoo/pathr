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
  isoLocal,
  monthGrid,
  rangeSummary,
  recentDays,
  streakDays,
  weekBars,
  yearHeat,
  yearMonths,
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
  it("é o ano civil, em semanas inteiras começando na segunda", () => {
    const cells = yearHeat(activity([]), WEDNESDAY);
    expect(cells.length % 7).toBe(0);
    const doAno = cells.filter((cell) => !cell.outside);
    expect(doAno).toHaveLength(365);
    expect(doAno[0].date).toBe("2026-01-01");
    expect(doAno[doAno.length - 1].date).toBe("2026-12-31");
  });

  it("preenche os dias sem estudo em vez de omiti-los", () => {
    // É o buraco que mostra a quebra de constância.
    const cells = yearHeat(activity([]), WEDNESDAY).filter((cell) => !cell.outside);
    expect(cells.every((cell) => cell.minutes === 0)).toBe(true);
    expect(cells[0].title).toContain("nenhuma atividade");
  });

  /**
   * O defeito que motivou a troca: com a janela móvel de 53 semanas, a semana
   * de hoje caía sempre na última coluna, embaixo de "Dez" — o estudo de 11 de
   * setembro aparecia em dezembro.
   */
  it("põe setembro na coluna de setembro, não na última", () => {
    const cells = yearHeat(activity([{ date: "2026-09-11", minutes: 12 }]), new Date(2026, 8, 12));
    const coluna = Math.floor(cells.findIndex((cell) => cell.date === "2026-09-11") / 7);
    const meses = yearMonths(new Date(2026, 8, 12));
    const setembro = meses.find((mes) => mes.label === "Set")!.column;
    const outubro = meses.find((mes) => mes.label === "Out")!.column;
    expect(coluna).toBeGreaterThanOrEqual(setembro);
    expect(coluna).toBeLessThan(outubro);
    expect(coluna).toBeLessThan(Math.floor(cells.length / 7) - 1);
  });

  it("marca o que ainda não chegou e não o conta", () => {
    const cells = yearHeat(activity([]), WEDNESDAY);
    expect(cells.find((cell) => cell.date === "2026-09-10")?.future).toBe(true);
    expect(cells.find((cell) => cell.date === "2026-09-09")?.future).toBe(false);
    // 1º de janeiro a 9 de setembro: 252 dias, não 371.
    expect(rangeSummary(activity([]), "ano", WEDNESDAY).headline).toBe(
      "0 de 252 dias ativos até hoje",
    );
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

describe("dia ativo", () => {
  /**
   * Criar o plano ou marcar um material não tem cronômetro. Contar só minutos
   * fazia o heatmap dizer "1 dia ativo" ao lado do cartão dizendo "3".
   */
  const semTempo = activity([
    { date: "2026-09-07", minutes: 0, count: 3 },
    { date: "2026-09-09", minutes: 12, count: 4 },
  ]);

  it("conta o dia com atividade mesmo sem minutos", () => {
    expect(rangeSummary(semTempo, "ano", WEDNESDAY).stats[0].value).toBe("2");
    expect(streakDays(semTempo, WEDNESDAY)[0].done).toBe(true);
  });

  it("acende o primeiro degrau do mapa para atividade sem tempo", () => {
    expect(heatLevel(0, 3)).toBe(1);
    expect(heatLevel(0, 0)).toBe(0);
  });

  it("a média divide o tempo pelos dias que TÊM tempo", () => {
    // Um dia de "plano criado" não pode puxar a média de estudo para baixo.
    expect(rangeSummary(semTempo, "semana", WEDNESDAY).stats[2].value).toBe("12 min");
  });
});

describe("data local", () => {
  /** Às 23h30 de Brasília já é o dia seguinte em UTC. */
  it("a chave do dia é a do calendário de quem usa, não a de UTC", () => {
    const noite = new Date(2026, 8, 11, 23, 30);
    expect(isoLocal(noite)).toBe("2026-09-11");
    expect(recentDays(activity([]), noite, 1)[0].date).toBe("2026-09-11");
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
