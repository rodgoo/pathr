/**
 * The status dot in front of a roadmap module.
 *
 * The tick is decorative — the status is announced in text on the row that
 * owns the dot, so repeating it here would make a screen reader say it twice.
 */
import type { ModuleStatusStyle } from "@/lib/moduleStatus";
import { Icon } from "@/components/ui/icons";

export function ModuleDot({ style, size = 18 }: { style: ModuleStatusStyle; size?: number }) {
  return (
    <span
      aria-hidden
      style={{
        width: size,
        height: size,
        flex: "none",
        borderRadius: "50%",
        border: `1.5px solid ${style.dot}`,
        background: style.dotFill,
        color: style.markColor,
        display: "grid",
        placeItems: "center",
      }}
    >
      {style.checked ? <Icon name="check" size={size < 16 ? 9 : 11} /> : null}
    </span>
  );
}
