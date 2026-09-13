/**
 * Cores para o que a pessoa escreve na atividade prática.
 *
 * Diferente de `highlight.ts` (que colore um trecho Java fixo), aqui o texto é
 * de qualquer assunto do roadmap: comandos de terminal, Java, Python, SQL,
 * HTML, YAML. Não há gramática de cada linguagem — só as marcas que valem para
 * quase todas, e a mais importante delas é o COMENTÁRIO: é nele que a pessoa
 * explica o que o comando faz, e ele precisa ficar visivelmente separado.
 *
 * Toda letra do texto cai em exatamente um pedaço, na ordem: juntar os pedaços
 * devolve o texto original. É o que deixa a camada colorida alinhar letra a
 * letra com o campo de texto por cima dela.
 */

export type Papel =
  | "comentario"
  | "texto"
  | "numero"
  | "palavra_chave"
  | "comando"
  | "opcao"
  | "tipo"
  | "chamada"
  | "simbolo"
  | "comum";

export interface Pedaco {
  readonly texto: string;
  readonly papel: Papel;
}

export const COR_DO_PAPEL: Record<Papel, string> = {
  comentario: "#7f8699",
  texto: "#98c379",
  numero: "#d19a66",
  palavra_chave: "#c678dd",
  comando: "#61afef",
  opcao: "#56b6c2",
  tipo: "#e5c07b",
  chamada: "#61afef",
  simbolo: "#9aa2b8",
  comum: "#dfe3ee",
};

const PALAVRAS_CHAVE = new Set(
  (
    // Java, JS/TS, Python, C#, Go
    "abstract async await break case catch class const continue def default do elif else enum export extends " +
    "final finally for from func function if implements import in interface is lambda let new not or and package " +
    "private protected public return static super switch this throw throws try type var void while with yield " +
    "true false null None True False undefined record sealed override val fun struct " +
    // SQL (vale em maiúsculas também)
    "select insert update delete into values set where join left right inner outer on group by order having " +
    "limit create table alter drop index primary key foreign references distinct as asc desc union count " +
    // YAML de CI e shell
    "name uses run steps jobs runs-on then fi esac done"
  ).split(" "),
);

const COMANDOS = new Set(
  (
    "git gh npm npx yarn pnpm node python python3 pip pip3 java javac mvn gradle docker docker-compose kubectl " +
    "cd ls mkdir rm cp mv cat echo touch curl wget sudo chmod export source ssh scp grep make go cargo dotnet " +
    "terraform aws az gcloud psql mysql"
  ).split(" "),
);

type Regra = { padrao: RegExp; papel: Papel | ((texto: string, fonte: string, fim: number) => Papel) };

function papelDaPalavra(texto: string, fonte: string, fim: number): Papel {
  const inicio = fim - texto.length;
  const inicioDaLinha = fonte.lastIndexOf("\n", inicio - 1) + 1;
  const antes = fonte.slice(inicioDaLinha, inicio);
  // O primeiro nome da linha, se for de um comando conhecido, é o comando.
  if (COMANDOS.has(texto) && /^\s*(\$\s*)?$/.test(antes)) return "comando";
  if (PALAVRAS_CHAVE.has(texto) || PALAVRAS_CHAVE.has(texto.toLowerCase())) return "palavra_chave";
  if (fonte[fim] === "(") return "chamada";
  if (/^[A-Z][a-z]/.test(texto)) return "tipo";
  return "comum";
}

const REGRAS: Regra[] = [
  { padrao: /\s+/y, papel: "comum" },
  { padrao: /\/\*[\s\S]*?(?:\*\/|$)/y, papel: "comentario" },
  { padrao: /<!--[\s\S]*?(?:-->|$)/y, papel: "comentario" },
  { padrao: /"(?:[^"\\\n]|\\.)*"?/y, papel: "texto" },
  { padrao: /'(?:[^'\\\n]|\\.)*'?/y, papel: "texto" },
  { padrao: /`[^`\n]*`?/y, papel: "texto" },
  { padrao: /--?[A-Za-z][\w-]*/y, papel: "opcao" },
  { padrao: /\d+(?:\.\d+)?/y, papel: "numero" },
  { padrao: /@?[A-Za-z_][\w-]*/y, papel: papelDaPalavra },
  { padrao: /\S/y, papel: "simbolo" },
];

/** Se um comentário de linha começa exatamente em `i`, onde ele termina. */
function comentarioDeLinha(fonte: string, i: number): number | null {
  const anterior = i === 0 ? "\n" : fonte[i - 1];
  const inicioOuEspaco = /\s/.test(anterior);
  const resto = fonte.slice(i, i + 3);
  const fimDaLinha = () => {
    const quebra = fonte.indexOf("\n", i);
    return quebra === -1 ? fonte.length : quebra;
  };
  // `//`, mas não o de `https://`.
  if (resto.startsWith("//") && anterior !== ":") return fimDaLinha();
  // `#` no começo da linha ou depois de espaço, seguido de espaço ou `!`:
  // pega `# comentário` e `#!/bin/bash`, deixa `#fff` e `#include` como código.
  if (resto[0] === "#" && inicioOuEspaco && (resto.length === 1 || /[\s!]/.test(resto[1]))) return fimDaLinha();
  // `-- ` do SQL; `--amend` continua sendo opção.
  if (resto.startsWith("--") && inicioOuEspaco && (resto.length === 2 || /\s/.test(resto[2]))) return fimDaLinha();
  return null;
}

export function realcar(fonte: string): Pedaco[] {
  const pedacos: Pedaco[] = [];
  let i = 0;
  while (i < fonte.length) {
    const fimDoComentario = comentarioDeLinha(fonte, i);
    if (fimDoComentario !== null) {
      pedacos.push({ texto: fonte.slice(i, fimDoComentario), papel: "comentario" });
      i = fimDoComentario;
      continue;
    }
    for (const regra of REGRAS) {
      regra.padrao.lastIndex = i;
      const achado = regra.padrao.exec(fonte);
      if (!achado || achado[0].length === 0) continue;
      const texto = achado[0];
      const fim = i + texto.length;
      pedacos.push({ texto, papel: typeof regra.papel === "function" ? regra.papel(texto, fonte, fim) : regra.papel });
      i = fim;
      break;
    }
  }
  return pedacos;
}
