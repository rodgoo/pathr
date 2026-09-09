/**
 * A togglable pill — library filters, settings tabs, language focuses.
 *
 * Selection is carried by `aria-pressed` rather than colour alone, so the
 * state survives for anyone who cannot see the accent tint.
 */
import type { CSSProperties, ReactNode } from "react";
import { ACC, TEXT } from "@/lib/tokens";

interface ChipProps {
  children: ReactNode;
  active: boolean;
  onClick: () => void;
  title?: string;
  /** Dashed chips read as suggestions rather than filters. */
  dashed?: boolean;
  style?: CSSProperties;
}

export function Chip({ children, active, onClick, title, dashed, style }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      style={{
        padding: "6px 12px",
        borderRadius: 7,
        font: "inherit",
        fontSize: 12.5,
        cursor: "pointer",
        border: `1px ${dashed ? "dashed" : "solid"} ${active ? ACC : "rgba(233,233,237,.14)"}`,
        background: active ? "rgba(145,132,217,.12)" : "transparent",
        color: active ? "#e7e5fe" : TEXT.muted,
        ...style,
      }}
    >
      {children}
    </button>
  );
}
