/**
 * The answer list shared by the technical quiz, the language placement test
 * and the code-review activity.
 *
 * Once a choice is made the list locks and repaints: the correct option
 * takes the accent, the chosen one is labelled, the rest recede. The options
 * stay focusable after locking (aria-disabled, not disabled) so someone
 * reading back with a screen reader can still reach the row that was right.
 */
import { ACC, PANEL, TEXT } from "@/lib/tokens";

export interface ChoiceState {
  border: string;
  background: string;
  color: string;
  mark: string;
}

/**
 * How option `index` should paint given the current pick.
 * `answered` in English gets English marks — the quiz is bilingual.
 */
export function choiceState(
  pick: number | null,
  index: number,
  answer: number | undefined,
  english = false,
): ChoiceState {
  // Sem gabarito, a escolha só é destacada como escolha.
  if (pick === null || answer === undefined) {
    const chosen = pick !== null && pick === index;
    return {
      border: chosen ? ACC : "rgba(233,233,237,.16)",
      background: chosen ? "rgba(145,132,217,.12)" : PANEL,
      color: TEXT.full,
      mark: "",
    };
  }
  if (index === answer) {
    return {
      border: ACC,
      background: "rgba(145,132,217,.16)",
      color: "#e7e5fe",
      mark: english ? "correct" : "correta",
    };
  }
  if (index === pick) {
    return {
      border: "#75798c",
      background: "rgba(233,233,237,.05)",
      color: "rgba(233,233,237,.6)",
      mark: english ? "your answer" : "sua resposta",
    };
  }
  return {
    border: "rgba(233,233,237,.10)",
    background: "transparent",
    color: "rgba(233,233,237,.45)",
    mark: "",
  };
}

interface ChoiceListProps {
  options: readonly string[];
  pick: number | null;
  /** O gabarito. Ausente enquanto a correção não chegou do servidor. */
  answer?: number;
  onPick: (index: number) => void;
  /** Quiz questions letter their options; scenarios and reviews do not. */
  letters?: boolean;
  /**
   * A resposta está a caminho do servidor.
   *
   * Trava a lista antes de o gabarito chegar. Sem isto, a lista só travava
   * quando a correção voltava — e a janela entre o clique e a resposta era
   * larga o bastante para um segundo clique gravar duas respostas para o
   * mesmo item.
   */
  busy?: boolean;
  english?: boolean;
  /** Names the set of choices for assistive tech. */
  label: string;
}

export function ChoiceList({
  options,
  pick,
  answer,
  onPick,
  letters = false,
  english = false,
  busy = false,
  label,
}: ChoiceListProps) {
  const answered = pick !== null && answer !== undefined;
  const locked = answered || busy;

  return (
    <div
      role="group"
      aria-label={label}
      style={{ display: "flex", flexDirection: "column", gap: 8.4 }}
    >
      {options.map((text, index) => {
        const state = choiceState(pick, index, answer, english);
        return (
          <button
            key={text}
            type="button"
            aria-disabled={locked}
            onClick={() => {
              if (!locked) onPick(index);
            }}
            style={{
              display: "flex",
              gap: 11.2,
              alignItems: "flex-start",
              textAlign: "left",
              padding: "11.2px 14px",
              borderRadius: 8,
              font: "inherit",
              fontSize: 14,
              cursor: locked ? "default" : "pointer",
              border: `1px solid ${state.border}`,
              background: state.background,
              color: state.color,
            }}
          >
            {letters ? (
              <span style={{ fontSize: 11.5, opacity: 0.6, paddingTop: 2 }}>{"ABCD"[index]}</span>
            ) : null}
            <span style={{ flex: 1 }}>{text}</span>
            <span style={{ fontSize: 11.5, whiteSpace: "nowrap" }}>{state.mark}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * The panel that follows an answered question: why, then what next.
 * The accent bar on the left is the system marking an aside, not a border.
 */
export function Explanation({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        marginTop: 16.8,
        padding: 14,
        borderRadius: 8,
        background: PANEL,
        borderLeft: `2px solid ${ACC}`,
      }}
    >
      {children}
    </div>
  );
}
