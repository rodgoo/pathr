/**
 * A togglable pill — library filters, settings tabs, language focuses.
 *
 * Selection is carried by `aria-pressed` rather than colour alone, so the
 * state survives for anyone who cannot see the accent tint.
 */
import type { CSSProperties, ReactNode } from "react";
import { ACC, SIZE, TEXT } from "@/lib/tokens";
import { Icon, type IconName } from "./icons";

interface ChipProps {
  children: ReactNode;
  active: boolean;
  onClick: () => void;
  title?: string;
  /** Dashed chips read as suggestions rather than filters. */
  dashed?: boolean;
  /** O símbolo à esquerda do rótulo. */
  icon?: IconName;
  style?: CSSProperties;
}

export function Chip({ children, active, onClick, title, dashed, icon, style }: ChipProps) {
  return (
    <button
      type="button"
      // Sem `.toque`: a pílula é um controle que acompanha, não a ação
      // principal da tela, e a 36px de altura seis delas lado a lado viravam
      // um paredão. 32 é a altura que o próprio iOS usa nesses filtros.
      onClick={onClick}
      title={title}
      aria-pressed={active}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5.6,
        minHeight: 32,
        padding: "0 10px",
        borderRadius: 8,
        font: "inherit",
        fontSize: SIZE.apoio,
        cursor: "pointer",
        border: `1px ${dashed ? "dashed" : "solid"} ${active ? ACC : "rgba(233,233,237,.14)"}`,
        background: active ? "rgba(145,132,217,.12)" : "transparent",
        color: active ? "#e7e5fe" : TEXT.muted,
        ...style,
      }}
    >
      {icon ? <Icon name={icon} size={13} /> : null}
      {children}
    </button>
  );
}
