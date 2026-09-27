/**
 * Escapes do gerador de SEO, num módulo à parte para poderem ser testados sem
 * rodar o gerador (que escreve em `public/` ao ser importado).
 */

/**
 * Texto que vai para dentro de um elemento OU de um atributo entre aspas
 * (`content="..."`, `title`, `og:*`, `twitter:*`). Sem escapar `"`, uma aspa
 * dupla no metaTitle/metaDesc fecharia o atributo e quebraria a página.
 */
export const esc = (s) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

/**
 * JSON pronto para ir dentro de `<script type="application/ld+json">`.
 *
 * O parser de HTML encerra o bloco no primeiro fechamento de script, mesmo
 * dentro de uma string JSON; então cada `<` vira a sequência de escape
 * backslash-u-0-0-3-c, que o JSON lê como o mesmo caractere. `>` e `&` recebem
 * o mesmo tratamento por precaução, e os separadores de linha U+2028 e U+2029
 * também, porque quebram linha em JavaScript.
 */
export const jsonSeguro = (valor, espacos = 2) =>
  JSON.stringify(valor, null, espacos)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(new RegExp(String.fromCharCode(0x2028), "g"), "\\" + "u2028")
    .replace(new RegExp(String.fromCharCode(0x2029), "g"), "\\" + "u2029");
