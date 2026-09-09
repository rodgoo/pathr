/**
 * The handful of shapes every screen repeats.
 *
 * Nocturne ships buttons, inputs, tags and cards as CSS classes; those are
 * used directly. What is here are the compositions the *product* repeats and
 * the stylesheet does not name — the raised panel, the accent kicker, the
 * 3px meter, the number-over-label stat.
 */
import type { CSSProperties, ReactNode } from "react";
import { ACC, HAIRLINE, SECTION_GRADIENT, SURF, TEXT } from "@/lib/tokens";

type PanelTone = "surface" | "section";

interface PanelProps {
  children: ReactNode;
  /** `section` is the one saturated ground the system allows. */
  tone?: PanelTone;
  /** Nocturne spacing steps: 14, 16.8 or 22.4 depending on density. */
  pad?: number;
  style?: CSSProperties;
}

/** A raised surface: the box almost every group of content sits in. */
export function Panel({ children, tone = "surface", pad = 14, style }: PanelProps) {
  return (
    <div
      style={{
        padding: pad,
        borderRadius: 14,
        minWidth: 0,
        background: tone === "section" ? SECTION_GRADIENT : SURF,
        boxShadow: tone === "section" ? "0 0 0 1px #595d6c" : "0 0 0 1px #3f424d",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** The small uppercase label that titles a group. */
export function Kicker({
  children,
  tone = "accent",
  style,
}: {
  children: ReactNode;
  tone?: "accent" | "section" | "muted";
  style?: CSSProperties;
}) {
  const color = tone === "accent" ? ACC : tone === "section" ? "#d2cefd" : TEXT.muted;
  return (
    <span
      style={{
        fontSize: 9.5,
        letterSpacing: ".12em",
        textTransform: "uppercase",
        color,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/**
 * A progress meter.
 *
 * Rendered as a real `progressbar` so a screen reader announces the number
 * the sighted user reads off the bar; `label` names what is progressing.
 */
export function Meter({
  pct,
  color = ACC,
  height = 3,
  label,
  style,
}: {
  pct: number;
  color?: string;
  height?: number;
  label: string;
  style?: CSSProperties;
}) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{
        height,
        borderRadius: 2,
        background: "rgba(233,233,237,.12)",
        overflow: "hidden",
        ...style,
      }}
    >
      <div style={{ height: "100%", background: color, width: `${clamped}%` }} />
    </div>
  );
}

/** A number with its caption underneath. */
export function Stat({
  value,
  label,
  size = 20,
}: {
  value: ReactNode;
  label: ReactNode;
  size?: number;
}) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: size, lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 11, color: TEXT.muted, marginTop: 2.8 }}>{label}</div>
    </div>
  );
}

/** A hairline that separates rows inside one surface. */
export function Hairline({ style }: { style?: CSSProperties }) {
  return <div style={{ borderTop: `1px solid ${HAIRLINE}`, ...style }} />;
}

/** The animation every screen enters with. */
export const SCREEN_IN: CSSProperties = { animation: "noc-in .3s ease both" };
