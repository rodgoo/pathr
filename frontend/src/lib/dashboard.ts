/**
 * Derivações do painel, agora sobre dados reais.
 *
 * O que antes gerava séries a partir de uma semente pseudoaleatória agora
 * recebe as linhas de `pathr_activity` e as organiza. As funções continuam
 * puras — é o que permite testá-las sem montar componente.
 *
 * Duas regras valem para todas elas:
 *
 * 1. **Data é a do calendário de quem usa.** `toISOString()` converte para
 *    UTC, e às 21h de Brasília já é o dia seguinte em UTC: o estudo da noite
 *    ia parar no quadrado de amanhã. Toda chave de dia sai de `isoLocal`.
 * 2. **Dia ativo é dia com atividade, com ou sem minutos.** Criar o plano ou
 *    marcar um material não tem cronômetro, e contar só minutos fazia o
 *    heatmap dizer "1 dia ativo" ao lado de um cartão dizendo "3 dias ativos"
 *    — dois números para a mesma pergunta, e os dois vindo da mesma tabela.
 */

import { HEAT } from "@/lib/tokens";
import { traduzirPt, type Traduzir } from "@/lib/i18n";
import type { ActivityDay, ActivityItem, ActivitySummary } from "@/api/types";
import type { ConstancyView } from "@/types";

/**
 * O idioma do painel, e como ele fala.
 *
 * Este arquivo não é componente: não pode usar hook. A tela avisa qual é o
 * idioma ao renderizar (`configurarTextosDoPainel`), e nome de mês e de dia
 * saem do `Intl` do navegador — que já tem os doze meses em todos os idiomas,
 * sem listas escritas à mão que envelheceriam uma por idioma.
 *
 * Sem aviso, fica o português: é o que faz este módulo funcionar solto, num
 * teste ou antes de a tela montar.
 */
let idiomaDoPainel = "pt";
let traduzir: Traduzir = traduzirPt;

export function configurarTextosDoPainel(idioma: string, t: Traduzir): void {
  idiomaDoPainel = idioma;
  traduzir = t;
}

const maiuscula = (texto: string) => (texto ? texto[0].toUpperCase() + texto.slice(1) : texto);

/** Os nomes de data por idioma, calculados uma vez só. */
const nomesPorIdioma = new Map<string, { curtosDeMes: string[]; diasDaSemana: string[] }>();

function nomes(idioma = idiomaDoPainel) {
  const guardado = nomesPorIdioma.get(idioma);
  if (guardado) return guardado;
  const mes = new Intl.DateTimeFormat(idioma, { month: "short" });
  const semana = new Intl.DateTimeFormat(idioma, { weekday: "short" });
  const novo = {
    curtosDeMes: Array.from({ length: 12 }, (_, i) =>
      maiuscula(mes.format(new Date(2026, i, 1)).replace(".", "")),
    ),
    // 5 de janeiro de 2026 é uma segunda: a semana do mapa começa nela.
    diasDaSemana: Array.from({ length: 7 }, (_, i) =>
      maiuscula(semana.format(new Date(2026, 0, 5 + i)).replace(".", "")),
    ),
  };
  nomesPorIdioma.set(idioma, novo);
  return novo;
}

/** Segunda a domingo, no idioma da tela. */
export const diasDaSemana = (idioma?: string) => nomes(idioma).diasDaSemana;
/** Jan…Dez, no idioma da tela. */
export const mesesCurtos = (idioma?: string) => nomes(idioma).curtosDeMes;

/** "9 de setembro", "September 9", "9. September" — quem formata é o Intl. */
function diaEMes(iso: string): string {
  const [ano, mes, dia] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat(idiomaDoPainel, { day: "numeric", month: "long" }).format(
    new Date(ano, (mes ?? 1) - 1, dia),
  );
}

/**
 * Minutos que definem cada degrau do heatmap.
 *
 * Escala fixa, não relativa ao próprio histórico: um degrau relativo faria o
 * mapa de quem estuda 20 min/dia parecer idêntico ao de quem estuda 2h, e a
 * pergunta que o mapa responde é "quanto", não "quanto comparado a mim".
 */
const STEPS = [1, 20, 45, 90] as const;

/** Dia que ainda não chegou: aparece no mapa, apagado, e não entra na conta. */
const FUTURE = "rgba(233,233,237,.03)";

/** `2026-09-11`, no calendário local. Ver a regra 1 no topo do arquivo. */
export function isoLocal(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** O degrau do dia. Atividade sem minutos ainda acende o primeiro degrau. */
export function heatLevel(minutes: number, count = 0): number {
  if (minutes <= 0) return count > 0 ? 1 : 0;
  if (minutes < STEPS[1]) return 1;
  if (minutes < STEPS[2]) return 2;
  if (minutes < STEPS[3]) return 3;
  return 4;
}

export const heatColor = (minutes: number, count = 0): string => HEAT[heatLevel(minutes, count)];

/** Índice por data, para procurar um dia em tempo constante. */
export function byDate(activity: ActivitySummary | null): Map<string, ActivityDay> {
  return new Map((activity?.days ?? []).map((day) => [day.date, day]));
}

/** Tudo o que se sabe de um dia — é o que o balão do mouse mostra. */
export interface DayDetail {
  date: string;
  minutes: number;
  count: number;
  items: ActivityItem[];
  /** Algum minuto do dia foi estimado pelo tamanho do texto. */
  estimated: boolean;
}

function detail(index: Map<string, ActivityDay>, key: string): DayDetail {
  const day = index.get(key);
  const items = day?.items ?? [];
  return {
    date: key,
    minutes: day?.minutes ?? 0,
    count: day?.count ?? 0,
    items,
    estimated: items.some((item) => item.estimated),
  };
}

/** "sexta-feira, 11 de setembro" — no idioma da tela. */
export function longDate(iso: string): string {
  const [ano, mes, dia] = iso.split("-").map(Number);
  const data = new Date(ano, (mes ?? 1) - 1, dia);
  const nomeDoDia = new Intl.DateTimeFormat(idiomaDoPainel, { weekday: "long" }).format(data);
  return `${maiuscula(nomeDoDia)}, ${diaEMes(iso)}`;
}

function label(iso: string, minutes: number, count: number): string {
  const data = diaEMes(iso);
  if (count <= 0 && minutes <= 0) return `${data} · ${traduzir("painel.nenhumaAtividade")}`;
  const atividades = traduzir(count === 1 ? "painel.umaAtividade" : "painel.atividades", { n: count });
  return minutes > 0
    ? `${data} · ${atividades} · ${traduzir("painel.minutos", { n: minutes })}`
    : `${data} · ${atividades}`;
}

export interface HeatCell extends DayDetail {
  background: string;
  title: string;
  /** Preenchimento de semana que cai no ano vizinho. */
  outside: boolean;
  /** Depois de hoje. */
  future: boolean;
}

/** Segunda-feira da semana de `date`. */
function mondayOf(date: Date): Date {
  const monday = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  return monday;
}

/** Dias inteiros entre duas datas locais, imune à troca de horário de verão. */
function daysBetween(from: Date, to: Date): number {
  const a = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const b = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b - a) / 86_400_000);
}

/**
 * O ano civil de `today`, em colunas de semana começando na segunda.
 *
 * Era "as últimas 53 semanas terminando hoje" — mas o painel diz "Sua
 * constância em 2026" e rotula as colunas de Jan a Dez. Com a janela móvel, a
 * semana de hoje caía sempre na última coluna, embaixo de "Dez": o estudo de
 * 11 de setembro aparecia em dezembro, e o total dizia "de 371 dias".
 *
 * As semanas das pontas são completadas com dias do ano vizinho (`outside`)
 * para a grade fechar; eles não se desenham nem contam.
 */
export function yearHeat(activity: ActivitySummary | null, today = new Date()): HeatCell[] {
  const index = byDate(activity);
  const year = today.getFullYear();
  const hoje = isoLocal(today);
  const start = mondayOf(new Date(year, 0, 1));
  const last = new Date(year, 11, 31);
  const end = new Date(last);
  end.setDate(end.getDate() + (6 - ((last.getDay() + 6) % 7)));

  const cells: HeatCell[] = [];
  const total = daysBetween(start, end) + 1;
  for (let step = 0; step < total; step += 1) {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + step);
    const key = isoLocal(date);
    const outside = date.getFullYear() !== year;
    const future = !outside && key > hoje;
    const day = detail(index, key);
    cells.push({
      ...day,
      outside,
      future,
      background: outside ? "transparent" : future ? FUTURE : heatColor(day.minutes, day.count),
      title: outside ? "" : label(key, day.minutes, day.count),
    });
  }
  return cells;
}

/** Em que coluna do mapa do ano cada mês começa. */
export function yearMonths(today = new Date()): { label: string; column: number }[] {
  const year = today.getFullYear();
  const start = mondayOf(new Date(year, 0, 1));
  return mesesCurtos().map((month, index) => ({
    label: month,
    column: Math.floor(daysBetween(start, new Date(year, index, 1)) / 7),
  }));
}

/** Os últimos `count` dias terminando hoje — a minissérie dos cartões. */
export function recentDays(
  activity: ActivitySummary | null,
  today = new Date(),
  count = 22,
): DayDetail[] {
  const index = byDate(activity);
  return Array.from({ length: count }, (_, offset) => {
    const date = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate() - (count - 1 - offset),
    );
    return detail(index, isoLocal(date));
  });
}

export interface MonthCell extends HeatCell {
  day: string;
  minutesLabel: string;
  ring: string;
  dayColor: string;
  minutesColor: string;
}

/** O mês corrente como calendário, alinhado na segunda-feira. */
export function monthGrid(activity: ActivitySummary | null, today = new Date()): MonthCell[] {
  const index = byDate(activity);
  const hoje = isoLocal(today);
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const lead = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  const total = Math.ceil((lead + daysInMonth) / 7) * 7;

  const cells: MonthCell[] = [];
  for (let slot = 0; slot < total; slot += 1) {
    const dayNumber = slot - lead + 1;
    const outside = dayNumber < 1 || dayNumber > daysInMonth;
    const key = outside
      ? ""
      : isoLocal(new Date(today.getFullYear(), today.getMonth(), dayNumber));
    const future = !outside && key > hoje;
    const day = outside ? detail(new Map(), "") : detail(index, key);
    const dark = heatLevel(day.minutes, day.count) >= 3;
    const idle = day.minutes === 0 && day.count === 0;
    cells.push({
      ...day,
      outside,
      future,
      day: outside ? "" : String(dayNumber),
      minutesLabel:
        outside || day.minutes === 0 ? "" : `${day.estimated ? "≈" : ""}${day.minutes}m`,
      background: outside ? "transparent" : future ? FUTURE : heatColor(day.minutes, day.count),
      ring: outside || !idle ? "none" : "inset 0 0 0 1px rgba(233,233,237,.06)",
      dayColor: outside
        ? "transparent"
        : future
          ? "rgba(233,233,237,.3)"
          : dark
            ? "#000000"
            : "#e9e9ed",
      minutesColor: outside
        ? "transparent"
        : dark
          ? "#000000"
          : idle
            ? "rgba(233,233,237,.6)"
            : "#e9e9ed",
      title: outside ? "" : label(key, day.minutes, day.count),
    });
  }
  return cells;
}

export interface WeekBar extends DayDetail {
  label: string;
  height: number;
  value: string;
  valueColor: string;
  color: string;
  title: string;
  today: boolean;
  future: boolean;
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
  const hoje = isoLocal(today);
  const monday = mondayOf(today);

  const days = diasDaSemana().map((label_, offset) => {
    const key = isoLocal(
      new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + offset),
    );
    return { ...detail(index, key), label: label_, today: key === hoje, future: key > hoje };
  });

  const peak = Math.max(60, ...days.map((day) => day.minutes));
  return days.map((day) => {
    const ativo = day.count > 0 || day.minutes > 0;
    const tempo = day.minutes ? `${day.minutes} minutos` : ativo ? "atividade sem tempo" : "sem estudo";
    return {
      ...day,
      height: Math.max(2, Math.round((day.minutes / peak) * 100)),
      value: day.minutes ? `${day.estimated ? "≈" : ""}${day.minutes}m` : "—",
      valueColor: day.minutes ? "rgba(233,233,237,.6)" : "rgba(233,233,237,.3)",
      color: day.today && ativo ? "#63b48f" : ativo ? "#3f6f57" : "rgba(233,233,237,.08)",
      title: `${day.label} · ${tempo}`,
    };
  });
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
 *
 * Só contam os dias que já passaram: "3 de 365 dias ativos" em setembro
 * compararia o que a pessoa fez com dias que ainda não existiram.
 */
export function rangeSummary(
  activity: ActivitySummary | null,
  view: ConstancyView,
  today = new Date(),
): { title: string; headline: string; stats: SummaryEntry[] } {
  const cells: { minutes: number; count: number }[] =
    view === "ano"
      ? yearHeat(activity, today).filter((cell) => !cell.outside && !cell.future)
      : view === "mes"
        ? monthGrid(activity, today).filter((cell) => !cell.outside && !cell.future)
        : weekBars(activity, today).filter((bar) => !bar.future);

  const active = cells.filter((cell) => cell.count > 0 || cell.minutes > 0);
  const total = cells.reduce((sum, cell) => sum + cell.minutes, 0);
  const withTime = cells.filter((cell) => cell.minutes > 0);
  const average = withTime.length ? Math.round(total / withTime.length) : 0;
  const best = cells.reduce((max, cell) => Math.max(max, cell.minutes), 0);

  const nomeDoMes = maiuscula(
    new Intl.DateTimeFormat(idiomaDoPainel, { month: "long" }).format(today),
  );
  const period =
    view === "ano"
      ? traduzir("painel.constanciaEm", { ano: today.getFullYear() })
      : view === "mes"
        ? traduzir("painel.mesDoAno", { mes: nomeDoMes, ano: today.getFullYear() })
        : traduzir("painel.estaSemana");

  const escopo = traduzir(
    view === "ano" ? "painel.noAno" : view === "mes" ? "painel.noMes" : "painel.naSemana",
  );

  return {
    title: period,
    headline: traduzir("painel.diasAtivosAteHoje", { ativos: active.length, total: cells.length }),
    stats: [
      { value: String(active.length), label: traduzir("painel.diasAtivos", { escopo }) },
      { value: humanMinutes(total), label: traduzir("painel.tempoTotal") },
      {
        value: average ? traduzir("painel.minutos", { n: average }) : "—",
        label: traduzir("painel.mediaPorDia"),
      },
      { value: best ? humanMinutes(best) : "—", label: traduzir("painel.melhorDia") },
    ],
  };
}

/** A faixa da semana no cartão de sequência. */
export function streakDays(activity: ActivitySummary | null, today = new Date()) {
  return weekBars(activity, today).map((bar) => ({
    label: bar.label,
    done: bar.count > 0 || bar.minutes > 0,
    today: bar.today,
  }));
}
