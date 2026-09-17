/**
 * O texto do tutor, formatado — sem nunca virar HTML.
 *
 * O tutor escreve em Markdown simples: parágrafos separados por linha em
 * branco, listas com "- " ou "1. ", **negrito**, `código na linha` e blocos
 * ```linguagem. Mostrado cru, isso vira um paredão com crases soltas. Aqui cada
 * pedaço vira um elemento React (<p>, <ul>, <strong>, <code>, <pre>) com o
 * texto dentro como TEXTO: um "<script>" na resposta aparece escrito, não roda.
 *
 * Pequeno de propósito: só o que o tutor foi instruído a usar. Link, imagem e
 * tabela não existem aqui — um link vindo de modelo é o tipo de coisa que não
 * se clica sem conferir.
 */

import type { ReactNode } from "react";
import { useT } from "@/lib/i18n";
import { ACC4, TEXT } from "@/lib/tokens";

const MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

/** `código` e **negrito** dentro de uma linha. */
function emLinha(texto: string, chave: string): ReactNode[] {
  const pedacos = texto.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g);
  return pedacos.map((pedaco, i) => {
    if (pedaco.startsWith("`") && pedaco.endsWith("`") && pedaco.length > 2) {
      return (
        <code
          key={`${chave}-${i}`}
          style={{
            fontFamily: MONO,
            fontSize: "0.92em",
            padding: "1px 5px",
            borderRadius: 4,
            background: "rgba(233,233,237,.1)",
            color: ACC4,
          }}
        >
          {pedaco.slice(1, -1)}
        </code>
      );
    }
    if (pedaco.startsWith("**") && pedaco.endsWith("**") && pedaco.length > 4) {
      return (
        <strong key={`${chave}-${i}`} style={{ fontWeight: 600, color: TEXT.full }}>
          {pedaco.slice(2, -2)}
        </strong>
      );
    }
    return pedaco;
  });
}

const ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/;
const NUMERADO = /^\s*\d+[.)]\s+/;

/** Parágrafos e listas de um trecho sem bloco de código. */
function blocosDeTexto(texto: string, chave: string): ReactNode[] {
  const saida: ReactNode[] = [];
  const paragrafos = texto.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  paragrafos.forEach((paragrafo, p) => {
    const linhas = paragrafo.split("\n").map((l) => l.trimEnd()).filter((l) => l.trim());
    let i = 0;
    let corrido: string[] = [];
    const soltarTexto = () => {
      if (!corrido.length) return;
      const k = `${chave}-p${p}-${i}`;
      saida.push(
        <p key={k} style={{ margin: "0 0 8px" }}>
          {emLinha(corrido.join(" "), k)}
        </p>,
      );
      corrido = [];
    };
    while (i < linhas.length) {
      if (ITEM.test(linhas[i])) {
        soltarTexto();
        const numerada = NUMERADO.test(linhas[i]);
        const itens: string[] = [];
        while (i < linhas.length && ITEM.test(linhas[i])) {
          itens.push(linhas[i].replace(ITEM, ""));
          i += 1;
        }
        const k = `${chave}-l${p}-${i}`;
        const Lista = numerada ? "ol" : "ul";
        saida.push(
          <Lista key={k} style={{ margin: "0 0 8px", paddingLeft: 20 }}>
            {itens.map((item, j) => (
              <li key={`${k}-${j}`} style={{ marginBottom: 3 }}>
                {emLinha(item, `${k}-${j}`)}
              </li>
            ))}
          </Lista>,
        );
      } else {
        corrido.push(linhas[i].trim());
        i += 1;
      }
    }
    soltarTexto();
  });
  return saida;
}

export function TextoFormatado({ texto }: { texto: string }) {
  const t = useT();
  const partes = texto.split("```");
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {partes.map((parte, indice) => {
        // Índice ímpar: dentro de um bloco ```. Um bloco sem fechamento (o
        // modelo parou no meio) ainda cai aqui e aparece como código.
        if (indice % 2 === 1) {
          const [primeira, ...resto] = parte.split("\n");
          const temLinguagem = /^[a-zA-Z0-9+#.-]{1,20}$/.test(primeira.trim());
          const codigo = (temLinguagem ? resto.join("\n") : parte).replace(/^\n+|\n+$/g, "");
          return (
            <pre
              key={indice}
              aria-label={temLinguagem ? t("modulo.duvidas.codigoEm", { linguagem: primeira.trim() }) : t("modulo.duvidas.codigo")}
              style={{
                margin: "2px 0 10px",
                padding: "9px 11px",
                borderRadius: 7,
                background: "#0a0a0d",
                boxShadow: "inset 0 0 0 1px rgba(233,233,237,.08)",
                overflowX: "auto",
                whiteSpace: "pre",
                fontFamily: MONO,
                fontSize: 12.5,
                lineHeight: 1.55,
                color: TEXT.full,
              }}
            >
              {codigo}
            </pre>
          );
        }
        return blocosDeTexto(parte, `t${indice}`);
      })}
    </div>
  );
}
