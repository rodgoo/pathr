/**
 * A meta da pessoa, como aparece na barra lateral.
 *
 * O que vem do servidor é o que ela DIGITOU no onboarding, do jeito que digitou: "fullstack Java, Typescript,
 * React, tudo de java, testes, Scrum". Mostrado cru, é uma lista solta, sem maiúsculas e sem sentido de resumo.
 * Aqui vira algo que dá para ler de relance: cada item com as iniciais em maiúscula, as tecnologias com a grafia
 * que elas têm ("TypeScript", "CI/CD"), sem repetição, e só os primeiros itens — o resto vira "+N", e o texto
 * completo fica no `title` para quem quiser ver.
 *
 * Só apresentação: o dado guardado não é alterado.
 */

/** Grafias que não são "primeira letra maiúscula, resto minúsculo". Chave em minúsculas. */
const GRAFIA: Record<string, string> = {
  typescript: "TypeScript",
  javascript: "JavaScript",
  nodejs: "Node.js",
  "node.js": "Node.js",
  aws: "AWS",
  gcp: "GCP",
  sql: "SQL",
  nosql: "NoSQL",
  html: "HTML",
  css: "CSS",
  api: "API",
  apis: "APIs",
  rest: "REST",
  devops: "DevOps",
  "ci/cd": "CI/CD",
  ci: "CI",
  cd: "CD",
  github: "GitHub",
  gitlab: "GitLab",
  postgresql: "PostgreSQL",
  postgres: "PostgreSQL",
  mysql: "MySQL",
  mongodb: "MongoDB",
  graphql: "GraphQL",
  ios: "iOS",
  ui: "UI",
  ux: "UX",
  ia: "IA",
  ai: "AI",
  ml: "ML",
  "c#": "C#",
  "c++": "C++",
  ".net": ".NET",
  fullstack: "Fullstack",
  "full-stack": "Full-stack",
};

/** Palavras de ligação: ficam em minúsculas no meio do item ("Tudo de Java"), mas abrem o item em maiúscula. */
const LIGACAO = new Set(["de", "da", "do", "das", "dos", "e", "em", "com", "para", "por", "a", "o", "as", "os", "of", "and", "the", "for", "in", "to", "with", "on"]);

function palavra(bruta: string, primeira: boolean): string {
  const minuscula = bruta.toLowerCase();
  if (GRAFIA[minuscula]) return GRAFIA[minuscula];
  // Grafia MISTA, com maiúscula depois da primeira letra ("TypeScript", "iPhone", "OAuth"): quem digitou sabia a
  // grafia. Tudo em maiúsculas ("JAVA") não conta — é caixa alta, não grafia — e cai na regra geral abaixo.
  if (/.[A-Z]/.test(bruta) && /[a-z]/.test(bruta)) return bruta;
  if (!primeira && LIGACAO.has(minuscula)) return minuscula;
  return minuscula.charAt(0).toUpperCase() + minuscula.slice(1);
}

function item(bruto: string): string {
  return bruto
    .trim()
    .split(/\s+/)
    .map((p, i) => palavra(p, i === 0))
    .join(" ");
}

export interface MetaFormatada {
  /** O resumo curto: "Fullstack Java · TypeScript · React +3". */
  texto: string;
  /** Tudo, para o `title` (dica ao passar o mouse). */
  completo: string;
}

export function formatarMeta(bruto: string | null | undefined, limite = 3): MetaFormatada {
  const vistos = new Set<string>();
  const itens: string[] = [];
  for (const parte of String(bruto ?? "").split(/[,;\n]+/)) {
    const formatado = item(parte);
    const chave = formatado.toLowerCase();
    if (!formatado || vistos.has(chave)) continue;
    vistos.add(chave);
    itens.push(formatado);
  }
  const resto = itens.length - limite;
  return {
    texto: itens.slice(0, limite).join(" · ") + (resto > 0 ? ` +${resto}` : ""),
    completo: itens.join(", "),
  };
}
