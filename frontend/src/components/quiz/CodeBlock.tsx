/**
 * A read-only code listing with line numbers.
 *
 * Rendered as a `<pre>` so the source is selectable and copyable as written,
 * and so a screen reader reads it as preformatted text rather than as prose.
 * `highlight` marks the lines the explanation is about.
 */
import { tokenize } from "@/lib/highlight";
import { PANEL } from "@/lib/tokens";

const MONO = "ui-monospace, Menlo, monospace";

interface CodeBlockProps {
  lines: readonly string[];
  /** Inclusive 0-based range to tint once the diagnosis has been made. */
  highlight?: { from: number; to: number } | null;
  filename?: string;
  meta?: string;
  /** The accent ring marks the corrected version. */
  corrected?: boolean;
  label: string;
}

export function CodeBlock({
  lines,
  highlight = null,
  filename,
  meta,
  corrected = false,
  label,
}: CodeBlockProps) {
  return (
    <div
      style={{
        borderRadius: 8,
        background: PANEL,
        boxShadow: corrected
          ? "0 0 0 1px rgba(145,132,217,.35)"
          : "0 0 0 1px rgba(233,233,237,.10)",
        overflow: "hidden",
      }}
    >
      {filename ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8.4,
            padding: "8.4px 11.2px",
            borderBottom: "1px solid rgba(233,233,237,.10)",
          }}
        >
          <span style={{ fontSize: 11.5, fontFamily: MONO, color: "rgba(233,233,237,.6)" }}>
            {filename}
          </span>
          {meta ? (
            <span style={{ marginLeft: "auto", fontSize: 10.5, color: "rgba(233,233,237,.35)" }}>
              {meta}
            </span>
          ) : null}
        </div>
      ) : null}

      <pre
        aria-label={label}
        style={{ overflowX: "auto", padding: "11.2px 0", margin: 0, fontFamily: MONO }}
      >
        {lines.map((line, index) => {
          const marked = highlight !== null && index >= highlight.from && index <= highlight.to;
          return (
            <div
              key={index}
              style={{
                display: "flex",
                gap: 14,
                padding: "0 14px",
                background: marked ? "rgba(145,132,217,.10)" : "transparent",
                boxShadow: marked ? "inset 2px 0 0 0 #9184d9" : "none",
              }}
            >
              <span
                aria-hidden
                style={{
                  flex: "none",
                  width: 20,
                  textAlign: "right",
                  fontSize: 12.5,
                  lineHeight: 1.65,
                  color: "rgba(233,233,237,.28)",
                }}
              >
                {index + 1}
              </span>
              <span style={{ fontSize: 12.5, lineHeight: 1.65 }}>
                {tokenize(line).map((token, tokenIndex) => (
                  <span key={tokenIndex} style={{ whiteSpace: "pre", color: token.color }}>
                    {token.text}
                  </span>
                ))}
              </span>
            </div>
          );
        })}
      </pre>
    </div>
  );
}
