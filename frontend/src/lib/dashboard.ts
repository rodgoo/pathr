/**
 * Derivações do painel, agora sobre dados reais.
 *
 * O que antes gerava séries a partir de uma semente pseudoaleatória agora
 * recebe as linhas de `pathr_activity` e as organiza. As funções continuam
 * puras — é o que permite testá-las sem montar componente.
 */

import { HEAT } from "@/lib/tokens";
import type { ActivityDay, ActivitySummary } from "@/api/types";
import type { ConstancyView } from "@/types";

export const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"] as const;
export const MONTHS_SHORT = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez",
] as const;
const MONTHS_LONG = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
] as const;

/**
 * Minutos que definem cada degrau do heatmap.
 *
 * Escala fixa, não relativa ao próprio histórico: um degrau relativo faria o
 * mapa de quem estuda 20 min/dia parecer idêntico ao de quem estuda 2h, e a
 * pergunta que o mapa responde é "quanto", não "quanto comparado a mim".
 */
const STEPS = [1, 20, 45, 90] as const;

export function heatLevel(minutes: number): number {
  if (minutes <= 0) return 0;
  if (minutes < STEPS[1]) return 1;
  if (minutes < STEPS[2]) return 2;
  if (minutes < STEPS[3]) return 3;
  return 4;
}

export const heatColor = (minutes: number): string => HEAT[heatLevel(minutes)];

/** Índice por data, para procurar um dia em tempo constante. */
export function byDate(activity: ActivitySummary | null): Map<string, ActivityDay> {
  return new Map((activity?.days ?? []).map((day) => [day.date, day]));
}

export interface HeatCell {
  date: string;
  minutes: number;
  background: string;
  title: string;
}

function label(iso: string, minutes: number, count: number): string {
  const [, month, day] = iso.split("-").map(Number);
  const date = `${day} de ${MONTHS_LONG[(month ?? 1) - 1]}`;
  if (minutes <= 0) return `${date} · nenhuma atividade`;
  return `${date} · ${count} ${count === 1 ? "atividade" : "atividades"} · ${minutes} min`;
}

const iso = (date: Date): string => date.toISOString().slice(0, 10);

/**
 * As últimas 53 semanas terminando hoje, alinhadas na segunda-feira.
 *
 * O grid é preenchido inteiro, com dias sem estudo inclusive: é justamente o
 * buraco que mostra a quebra de constância.
 */
export function yearHeat(activity: ActivitySummary | null, today = new Date()): HeatCell[] {
  const index = byDate(activity);
  const end = new Date(today);
  // Recua até o domingo seguinte para a última coluna ficar completa.
  end.setDate(end.getDate() + (7 - ((end.getDay() + 6) % 7) - 1));

  const cells: HeatCell[] = [];
  const cursor = new Date(end);
  cursor.setDate(cursor.getDate() - 371 + 1);
  for (let step = 0; step < 371; step += 1) {
    const key = iso(cursor);
    const day = index.get(key);
    const minutes = day?.minutes ?? 0;
    cells.push({
      date: key,
      minutes,
      background: heatColor(minutes),
      title: label(key, minutes, day?.count ?? 0),
    });
    cursor.setDate(cursor.getDate() + 1);
  }
  return cells;
}

export interface MonthCell extends HeatCell {
  day: string;
  minutesLabel: string;
  ring: string;
  dayColor: string;
  minutesColor: string;
  outside: boolean;
}

/** O mês corrente como calendário, alinhado na segunda-feira. */
export function monthGrid(activity: ActivitySummary | null, today = new Date()): MonthCell[] {
  const index = byDate(activity);
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const lead = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  const total = Math.ceil((lead + daysInMonth) / 7) * 7;

  const cells: MonthCell[] = [];
  for (let slot = 0; slot < total; slot += 1) {
    const dayNumber = slot - lead + 1;
    const outside = dayNumber < 1 || dayNumber > daysInMonth;
    const date = new Date(today.getFullYear(), today.getMonth(), dayNumber);
    const key = outside ? "" : iso(date);
    const minutes = outside ? 0 : index.get(key)?.minutes ?? 0;
    const dark = heatLevel(minutes) >= 3;
    cells.push({
      date: key,
      minutes,
      outside,
      day: outside ? "" : String(dayNumber),
      minutesLabel: outside || minutes === 0 ? "" : `${minutes}m`,
      background: outside ? "transparent" : heatColor(minutes),
      ring: outside ? "none" : minutes === 0 ? "inset 0 0 0 1px rgba(233,233,237,.06)" : "none",
      dayColor: outside ? "transparent" : dark ? "#161826" : "#e9e9ed",
      minutesColor: outside
        ? "transparent"
        : dark
          ? "#161826"
          : minutes === 0
            ? "rgba(233,233,237,.6)"
            : "#e9e9ed",
      title: outside ? "" : label(key, minutes, index.get(key)?.count ?? 0),
    });
  }
  return cells;
}


export interface WeekBar {
  date: string;
  label: string;
  minutes: number;
  height: number;
  value: string;
  valueColor: string;
  color: string;
  title: string;
  today: boolean;
}

/**
 * A semana corrente em barras.
 *
 * A altura é relativa ao maior dia da própria semana, com um piso de 2px para
 * o dia zerado ainda marcar posição no eixo. Escala fixa faria uma semana
 * fraca inteira parecer plana e ilegível.
 */
export function weekBars(activity: ActivitySummary | null, today = new Date()): WeekBar[] {
  const index = byDate(activity);
  const monday = new Date(today);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));

  const days = WEEKDAYS.map((label_, offset) => {
    const date = new Date(monday);
    date.setDate(date.getDate() + offset);
    const key = iso(date);
    return { key, label: label_, minutes: index.get(key)?.minutes ?? 0, today: key === iso(today) };
  });

  const peak = Math.max(60, ...days.map((day) => day.minutes));
  return days.map((day) => ({
    date: day.key,
    label: day.label,
    minutes: day.minutes,
    height: Math.max(2, Math.round((day.minutes / peak) * 100)),
    value: day.minutes ? `${day.minutes}m` : "—",
    valueColor: day.minutes ? "rgba(233,233,237,.6)" : "rgba(233,233,237,.3)",
    color: day.today && day.minutes ? "#63b48f" : day.minutes ? "#3f6f57" : "rgba(233,233,237,.08)",
    title: `${day.label} · ${day.minutes ? `${day.minutes} minutos` : "sem estudo"}`,
    today: day.today,
  }));
}

export interface SummaryEntry {
  value: string;
  label: string;
}

/** Formata minutos como "5h40" ou "45 min" — o que couber melhor. */
export function humanMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h${String(rest).padStart(2, "0")}` : `${hours}h`;
}

/**
 * Os números do recorte selecionado.
 *
 * Calculados a partir dos mesmos dias que o gráfico desenha, e não de um
 * agregado separado — dois caminhos para o mesmo número é como um painel
 * passa a se contradizer.
 */
export function rangeSummary(
  activity: ActivitySummary | null,
  view: ConstancyView,
  today = new Date(),
): { title: string; headline: string; stats: SummaryEntry[] } {
  const cells =
    view === "ano"
      ? yearHeat(activity, today)
      : view === "mes"
        ? monthGrid(activity, today).filter((cell) => !cell.outside)
        : weekBars(activity, today).map((bar) => ({ minutes: bar.minutes }));

  const active = cells.filter((cell) => cell.minutes > 0);
  const total = cells.reduce((sum, cell) => sum + cell.minutes, 0);
  const average = active.length ? Math.round(total / active.length) : 0;
  const best = cells.reduce((max, cell) => Math.max(max, cell.minutes), 0);

  const period =
    view === "ano"
      ? `Sua constância em ${today.getFullYear()}`
      : view === "mes"
        ? `${MONTHS_LONG[today.getMonth()][0].toUpperCase()}${MONTHS_LONG[today.getMonth()].slice(1)} de ${today.getFullYear()}`
        : "Esta semana";

  const scope = view === "ano" ? "no ano" : view === "mes" ? "no mês" : "na semana";

  return {
    title: period,
    headline: `${active.length} de ${cells.length} dias ativos`,
    stats: [
      { value: String(active.length), label: `dias ativos ${scope}` },
      { value: humanMinutes(total), label: "tempo total" },
      { value: average ? `${average} min` : "—", label: "média por dia ativo" },
      { value: best ? humanMinutes(best) : "—", label: "melhor dia" },
    ],
  };
}

/** A faixa da semana no cartão de sequência. */
export function streakDays(activity: ActivitySummary | null, today = new Date()) {
  return weekBars(activity, today).map((bar) => ({
    label: bar.label,
    done: bar.minutes > 0,
    today: bar.today,
  }));
}
