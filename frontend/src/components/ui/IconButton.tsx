/**
 * Uma ação que é só ícone: remover, trocar, abrir, voltar, fechar.
 *
 * O nome não some com o texto: vai para `aria-label` (é o que o leitor de tela
 * lê e o que os testes procuram) e para `title` (a dica ao passar o mouse). Um
 * ícone sem nenhum dos dois é um botão que só quem já sabe o que faz consegue
 * usar.
 */

import type { CSSProperties, MouseEventHandler } from "react";
import { Icon, type IconName } from "./icons";

export function IconButton({
  icon,
  label,
  onClick,
  disabled,
  tone = "ghost",
  size = 16,
  color,
  style,
  expanded,
  pressed,
}: {
  icon: IconName;
  /** O nome da ação, dito ao leitor de tela e mostrado ao passar o mouse. */
  label: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
  tone?: "ghost" | "secondary" | "primary";
  size?: number;
  color?: string;
  style?: CSSProperties;
  expanded?: boolean;
  pressed?: boolean;
}) {
  return (
    <button
      type="button"
      className={`btn btn-${tone} btn-icon`}
      aria-label={label}
      title={label}
      aria-expanded={expanded}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      style={{ flex: "none", color, ...style }}
    >
      <Icon name={icon} size={size} />
    </button>
  );
}
