/**
 * The Nocturne values the screens reach for from TypeScript.
 *
 * Everything static lives in nocturne.css as a custom property. These
 * constants exist only where a colour is *computed* — interpolated into a
 * gradient stop, picked per data point, handed to an SVG `stroke` — which
 * CSS classes cannot express. They are the same values the stylesheet
 * carries, not a second palette.
 */

/** `--color-accent` */
export const ACC = "#9184d9";
/** `--color-accent-400`, the pressed/lit step on a dark ground. */
export const ACC4 = "#b5abfc";
/** `--color-accent-300`, the step readable at paragraph size. */
export const ACC3 = "#d2cefd";
/** `--color-surface` */
export const SURF = "#232532";
/** `--color-bg` */
export const BG = "#161826";
/** The panel ground: one step above `--color-bg`, below `--color-surface`. */
export const PANEL = "#1b1d2b";
/** The 1px inset ring the segmented control paints when selected. */
export const RING = `inset 0 0 0 1px ${ACC}`;

/**
 * Supporting hues for semantic roles — one per study track, plus the two the
 * heatmap and the alert strip use. All sit at the accent's lightness and
 * chroma so no single track shouts over the others.
 */
export const C = {
  verde: "#63b48f",
  azul: "#6aa6de",
  ambar: "#cfa25e",
  rosa: "#d189ab",
  teal: "#5cb0b0",
} as const;

/**
 * A escala de texto. Três degraus, e é de propósito que sejam poucos.
 *
 * Antes disto os controles do app usavam oito combinações de tamanho e peso
 * — 11, 12.5, 13, 13.5, 14, 15, 16 — e o resultado é o que se vê num
 * celular: dois botões lado a lado com corpos diferentes, um rótulo maior que
 * o título que ele descreve, uma pílula que grita mais alto que a ação.
 *
 * A regra: toda AÇÃO usa `corpo`, o mesmo 14px do `.btn` do Nocturne. Uma
 * ação secundária, que acompanha outra maior na mesma linha, usa `apoio`.
 * `rotulo` é só para metadado — nunca para algo em que se toca.
 */
export const SIZE = {
  /** Metadado, kicker, badge. Não é alvo de toque. */
  rotulo: 11,
  /** Ação secundária e texto de apoio. */
  apoio: 12.5,
  /** Corpo do texto e TODA ação principal. O mesmo tamanho do `.btn`. */
  corpo: 14,
  /** Título de painel. */
  titulo: 18,
  /** O número grande de um cartão de KPI. */
  destaque: 26,
} as const;

/** Text at the four opacities the design uses over the dark ground. */
export const TEXT = {
  /** Body copy. */
  full: "#e9e9ed",
  /** Secondary copy inside a card. */
  strong: "rgba(233,233,237,.75)",
  /** Labels and metadata. */
  muted: "rgba(233,233,237,.5)",
  /** Captions and disabled affordances. */
  faint: "rgba(233,233,237,.42)",
} as const;

/** Hairline separators inside a surface. */
export const HAIRLINE = "rgba(233,233,237,.10)";

/** The five heatmap steps, from "no study" to a full session. */
export const HEAT = [
  "rgba(233,233,237,.06)",
  "#2c4a3c",
  "#3f6f57",
  "#549277",
  "#63b48f",
] as const;

/** A translucent wash of `hex` at `pct` percent — used for icon chips. */
export const tint = (hex: string, pct: number): string =>
  `color-mix(in srgb, ${hex} ${pct}%, transparent)`;

/** The section ground: the one saturated field the system allows. */
export const SECTION_GRADIENT = "linear-gradient(135deg,#262a60,#232532)";

/**
 * A linear congruential generator.
 *
 * The dashboard shows a year of study history that no backend has produced
 * yet. Drawing it from `Math.random()` would reshuffle the heatmap on every
 * render; seeding it keeps each chart stable across renders and identical in
 * a test run, so a snapshot of the sparkline means something.
 */
export function seeded(count: number, seed: number): number[] {
  const out: number[] = [];
  let x = seed;
  for (let i = 0; i < count; i += 1) {
    x = (x * 1103515245 + 12345) % 2147483648;
    out.push(x / 2147483648);
  }
  return out;
}
