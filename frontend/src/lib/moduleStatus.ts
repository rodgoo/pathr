/**
 * How a roadmap module paints for each of its three states.
 *
 * Shared by the roadmap timeline, the phase columns and the module screen's
 * sidebar, so a finished module looks finished in all three. Done recedes
 * (it is history), the current one takes the accent outline, and what is next
 * stays legible without competing.
 */
import { ACC, ACC4, SURF } from "@/lib/tokens";
import type { NodeStatus } from "@/api/types";

export interface ModuleStatusStyle {
  dot: string;
  dotFill: string;
  /** Whether to draw the tick inside the dot. */
  checked: boolean;
  markColor: string;
  color: string;
  background: string;
  border: string;
}

export function moduleStatusStyle(status: NodeStatus): ModuleStatusStyle {
  if (status === "done") {
    return {
      dot: ACC,
      dotFill: "rgba(145,132,217,.22)",
      checked: true,
      markColor: ACC4,
      color: "rgba(233,233,237,.55)",
      background: SURF,
      border: "rgba(233,233,237,.10)",
    };
  }

  if (status === "doing") {
    return {
      dot: ACC4,
      dotFill: "transparent",
      checked: false,
      markColor: "transparent",
      color: "#e9e9ed",
      background: "rgba(145,132,217,.10)",
      border: ACC,
    };
  }

  return {
    dot: "rgba(233,233,237,.28)",
    dotFill: "transparent",
    checked: false,
    markColor: "transparent",
    color: "rgba(233,233,237,.82)",
    background: SURF,
    border: "rgba(233,233,237,.12)",
  };
}

/** Spoken form of the status, for the tick that is otherwise decorative. */
export function moduleStatusLabel(status: NodeStatus): string {
  if (status === "done") return "concluído";
  if (status === "doing") return "em curso";
  if (status === "locked") return "bloqueado";
  if (status === "skipped") return "pulado";
  return "a fazer";
}
