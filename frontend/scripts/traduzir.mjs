/**
 * Gera os dicionários dos outros idiomas a partir do português, com o DeepL.
 *
 * Uso:
 *   node scripts/traduzir.mjs            # traduz só o que falta
 *   node scripts/traduzir.mjs --tudo     # refaz todas as chaves
 *   node scripts/traduzir.mjs --idioma en
 *
 * ## Por que na hora de escrever, e não na hora de exibir
 *
 * Traduzir em tempo de execução colocaria uma chamada de rede paga na frente
 * de cada tela, com atraso visível e conta crescendo por visita. O texto fixo
 * do app muda quando alguém edita o código — então ele é traduzido uma vez,
 * aqui, e vai para o repositório junto com a mudança. O app carrega JSON.
 *
 * ## O que o DeepL não pode encostar
 *
 * `{nome}`, `{n}` e afins são buracos que o app preenche. Traduzidos, viram
 * texto e o valor some da tela. Por isso cada um vira uma tag XML ignorada na
 * ida e volta ao normal na volta.
 *
 * A chave sai de `DEEPL_API_KEY` ou de `backend/.env.local` — a mesma do resto
 * do app. Nunca é impressa.
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const PASTA = join(AQUI, "..", "src", "i18n");
const BASE = join(PASTA, "pt.json");

/** O código do app e o código do DeepL — nem sempre são o mesmo. */
const IDIOMAS = { en: "EN-US", es: "ES", fr: "FR", de: "DE" };

/**
 * Chaves que NÃO passam pelo tradutor — vão iguais para todos os idiomas.
 *
 * Nome de pessoa e de cidade viram outra coisa ("Vitória" → "Victory"), e o
 * vocabulário de inglês da demonstração perde o sentido se for traduzido: ali
 * a palavra em inglês É o conteúdo, não a interface.
 */
const NAO_TRADUZIR = [
  /^landing\.pessoas\.[^.]+\.(nome|cidade|uf)$/,
  /^landing\.palavras\./,
];

const literal = (chave) => NAO_TRADUZIR.some((padrao) => padrao.test(chave));

const argumentos = process.argv.slice(2);
const TUDO = argumentos.includes("--tudo");
const SO_ESTE = (() => {
  const i = argumentos.indexOf("--idioma");
  return i >= 0 ? argumentos[i + 1] : null;
})();

function chaveDoDeepL() {
  if (process.env.DEEPL_API_KEY) return process.env.DEEPL_API_KEY.trim();
  const env = join(AQUI, "..", "..", "backend", ".env.local");
  if (!existsSync(env)) return "";
  for (const linha of readFileSync(env, "utf8").split(/\r?\n/)) {
    const casou = linha.match(/^\s*DEEPL_API_KEY\s*=\s*(.+?)\s*$/);
    if (casou) return casou[1].replace(/^["']|["']$/g, "").trim();
  }
  return "";
}

const CHAVE = chaveDoDeepL();
if (!CHAVE) {
  console.error("Sem DEEPL_API_KEY (no ambiente ou em backend/.env.local).");
  process.exit(1);
}
const SERVIDOR = CHAVE.endsWith(":fx") ? "https://api-free.deepl.com" : "https://api.deepl.com";

/**
 * Todas as folhas do dicionário, como caminho "a.b.c" → texto.
 *
 * Lista entra igual, com o índice no caminho ("exemplos.java.linhas.0"): há
 * texto de tela guardado em lista (as linhas de um exemplo), e pular listas
 * deixaria essas frases em português para sempre.
 */
function achatar(objeto, prefixo = "") {
  const saida = {};
  for (const [chave, valor] of Object.entries(objeto)) {
    const caminho = prefixo ? `${prefixo}.${chave}` : chave;
    if (valor && typeof valor === "object") {
      Object.assign(saida, achatar(valor, caminho));
    } else if (typeof valor === "string") {
      saida[caminho] = valor;
    }
  }
  return saida;
}

const ehIndice = (parte) => /^\d+$/.test(parte);

function inserir(objeto, caminho, valor) {
  const partes = caminho.split(".");
  let atual = objeto;
  partes.slice(0, -1).forEach((parte, posicao) => {
    // O que vem DEPOIS decide a forma: índice pede lista, nome pede objeto.
    const molde = ehIndice(partes[posicao + 1]) ? [] : {};
    if (typeof atual[parte] !== "object" || atual[parte] === null) atual[parte] = molde;
    atual = atual[parte];
  });
  atual[partes.at(-1)] = valor;
}

const protegerBuracos = (texto) => texto.replace(/\{(\w+)\}/g, "<ph>$1</ph>");
const soltarBuracos = (texto) => texto.replace(/<ph>\s*(\w+)\s*<\/ph>/g, "{$1}");

async function traduzirLote(textos, destino) {
  const corpo = new URLSearchParams();
  corpo.set("source_lang", "PT");
  corpo.set("target_lang", destino);
  corpo.set("tag_handling", "xml");
  corpo.set("ignore_tags", "ph");
  // Texto de interface é rótulo solto, não prosa: sem isso o DeepL "melhora" a
  // frase e o botão vira uma oração.
  corpo.set("preserve_formatting", "1");
  for (const texto of textos) corpo.append("text", protegerBuracos(texto));

  const resposta = await fetch(`${SERVIDOR}/v2/translate`, {
    method: "POST",
    headers: {
      Authorization: `DeepL-Auth-Key ${CHAVE}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: corpo,
  });
  if (!resposta.ok) {
    throw new Error(`DeepL respondeu HTTP ${resposta.status} para ${destino}`);
  }
  const dados = await resposta.json();
  return (dados.translations ?? []).map((item) => soltarBuracos(item.text));
}

async function gerar(codigo, alvoDeepL, base) {
  const arquivo = join(PASTA, `${codigo}.json`);
  const atual = existsSync(arquivo) ? JSON.parse(readFileSync(arquivo, "utf8")) : {};
  const jaTem = achatar(atual);

  const saidaLiteral = Object.entries(base).filter(([chave]) => literal(chave));
  const pendentes = Object.entries(base).filter(
    ([chave]) => !literal(chave) && (TUDO || !jaTem[chave]),
  );
  if (pendentes.length === 0) {
    console.log(`${codigo}: nada a traduzir (${Object.keys(base).length} chaves em dia)`);
    return;
  }

  const saida = TUDO ? {} : atual;
  // O que não se traduz entra igual, sempre: se o português mudar, o outro
  // idioma acompanha em vez de ficar com o texto antigo.
  for (const [chave, texto] of saidaLiteral) inserir(saida, chave, texto);
  // Lotes de 40: o DeepL aceita várias frases por chamada, e uma chamada por
  // rótulo gastaria a cota à toa.
  for (let i = 0; i < pendentes.length; i += 40) {
    const lote = pendentes.slice(i, i + 40);
    const traduzidos = await traduzirLote(
      lote.map(([, texto]) => texto),
      alvoDeepL,
    );
    lote.forEach(([chave], posicao) => {
      inserir(saida, chave, traduzidos[posicao] ?? base[chave]);
    });
    console.log(`${codigo}: ${Math.min(i + lote.length, pendentes.length)}/${pendentes.length}`);
  }

  writeFileSync(arquivo, `${JSON.stringify(saida, null, 2)}\n`, "utf8");
  console.log(`${codigo}: gravado`);
}

const base = achatar(JSON.parse(readFileSync(BASE, "utf8")));
console.log(`português: ${Object.keys(base).length} chaves`);

for (const [codigo, alvo] of Object.entries(IDIOMAS)) {
  if (SO_ESTE && SO_ESTE !== codigo) continue;
  await gerar(codigo, alvo, base);
}
