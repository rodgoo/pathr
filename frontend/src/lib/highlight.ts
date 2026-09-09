/**
 * A minimal Java/JPQL tokenizer for the code-review activity.
 *
 * Not a general highlighter: it colours the fifteen-line snippet the module
 * ships, and nothing else. Pulling in a real grammar would add a parser and a
 * theme to render one static block, so the rule set is deliberately small and
 * the vocabulary it knows about is listed here in full.
 */

/** Colours by token role, in the One Dark family the design used. */
const TOKEN_COLOR = {
  keyword: "#c678dd",
  type: "#e5c07b",
  string: "#98c379",
  number: "#d19a66",
  annotation: "#e5c07b",
  call: "#61afef",
  comment: "#6b7089",
  operator: "#9aa2b8",
  plain: "#dfe3ee",
} as const;

export type TokenRole = keyof typeof TOKEN_COLOR;

export interface Token {
  readonly text: string;
  readonly color: string;
}

const KEYWORDS = new Set([
  "public", "private", "protected", "class", "return", "new", "for", "if",
  "else", "void", "final", "static", "import", "package",
  "select", "from", "join", "where", "order", "by", "desc", "asc",
]);

const TYPES = new Set([
  "List", "ArrayList", "Pedido", "PedidoDTO", "PedidoRepository",
  "PedidoService", "Long", "String", "Service", "Query", "Param",
]);

/**
 * Splits one line into coloured runs.
 *
 * The pattern matches, in order: whitespace, a quoted string, an annotation,
 * a word, a number, then any single other character — so every character of
 * the input lands in exactly one token and the rendered line is never
 * shorter than the source.
 */
const PATTERN = /(\s+|"[^"]*"|'[^']*'|@[A-Za-z_]\w*|[A-Za-z_]\w*|\d+|[^\sA-Za-z_\d])/g;

export function tokenize(line: string): Token[] {
  if (line.trim().startsWith("//")) {
    return [{ text: line, color: TOKEN_COLOR.comment }];
  }

  const tokens: Token[] = [];
  PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = PATTERN.exec(line)) !== null) {
    const text = match[0];
    tokens.push({ text, color: TOKEN_COLOR[roleOf(text, line, PATTERN.lastIndex)] });
  }

  return tokens;
}

function roleOf(text: string, line: string, nextIndex: number): TokenRole {
  if (/^\s+$/.test(text)) return "plain";
  if (text.startsWith('"') || text.startsWith("'")) return "string";
  if (text.startsWith("@")) return "annotation";
  if (/^\d+$/.test(text)) return "number";
  if (KEYWORDS.has(text)) return "keyword";
  if (TYPES.has(text) || /^[A-Z]/.test(text)) return "type";
  // A word immediately followed by "(" is being called, not read.
  if (line[nextIndex] === "(") return "call";
  if (/^[A-Za-z_]/.test(text)) return "plain";
  return "operator";
}
