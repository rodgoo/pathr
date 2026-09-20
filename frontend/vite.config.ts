import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * O domínio das metatags (canonical, Open Graph, JSON-LD) sai do ambiente.
 *
 * O `index.html` guarda o endereço de produção como padrão — assim o build
 * normal não depende de variável nenhuma. Quem sobe um fork exporta
 * `SITE_URL` e as metatags apontam para o site dele, em vez de mandarem o
 * Google para a instalação original.
 */
function dominioDoSite() {
  const site = process.env.SITE_URL ?? PADRAO_DO_SITE;
  return {
    name: "pathr-dominio-do-site",
    transformIndexHtml(html: string) {
      return site === PADRAO_DO_SITE ? html : html.split(PADRAO_DO_SITE).join(site);
    },
  };
}

const PADRAO_DO_SITE = "https://pathr.notter.com.br";


/**
 * O Vite substitui `import.meta.env.VITE_*` em tempo de build: num arquivo
 * estático servido por CDN não há como ler variável de ambiente depois. Se a
 * URL da API faltar, o cliente cai no default de desenvolvimento e o bundle
 * sai apontando para localhost — o deploy termina verde e cada pedido falha
 * só no navegador de quem abrir o site. Melhor quebrar o build.
 */
function exigeUrlDaApi() {
  return {
    name: "exige-url-da-api",
    apply: "build" as const,
    config(_config: unknown, { mode }: { mode: string }) {
      if (mode === "production" && !process.env.VITE_API_URL) {
        throw new Error(
          "VITE_API_URL não está definida. O build de produção embute essa URL " +
            "no bundle; sem ela o app apontaria para localhost. Defina-a no " +
            "painel do host (Render: Environment do static site).",
        );
      }
    },
  };
}

/** O que vale a pena guardar no aparelho para o app abrir sem rede. */
const EXTENSOES_DO_CASCO = [".html", ".js", ".css", ".svg", ".png", ".ico", ".woff2", ".webmanifest"];
/** Arquivos de configuração do host: existem no disco, não são do app. */
const FORA_DO_CASCO = ["sw.js", "_headers", "_redirects"];
/**
 * As telas de abertura do iOS somam ~270KB e são pedidas UMA vez, pelo
 * sistema, fora do contexto da página. Guardá-las na instalação atrasaria a
 * primeira visita de todo mundo para servir um arquivo que a pessoa vê por
 * meio segundo.
 */
const PASTAS_FORA_DO_CASCO = ["/splash/"];

function listaArquivos(raiz: string, atual = raiz): string[] {
  return readdirSync(atual).flatMap((nome) => {
    const caminho = join(atual, nome);
    if (statSync(caminho).isDirectory()) return listaArquivos(raiz, caminho);
    return [`/${relative(raiz, caminho).split(sep).join("/")}`];
  });
}

/**
 * Gera `dist/sw.js` a partir de `src/pwa/service-worker.js`.
 *
 * Existe em vez de um plugin de PWA pronto pelo mesmo motivo de `useApi` não
 * ser uma biblioteca de cache: o que os plugins resolvem — estratégias por
 * rota, injeção de manifest, workbox — este app não precisa. Precisa de uma
 * coisa só, e é a que um service worker escrito à mão não consegue ter
 * sozinho: a lista dos arquivos com hash que ESTE build produziu.
 *
 * A versão é o hash dessa lista. Um build que não muda nenhum arquivo produz
 * a mesma versão, e o navegador não vê atualização nenhuma — é o certo, já
 * que não há o que atualizar.
 */
function geraServiceWorker() {
  let saida = "";
  let raizDoProjeto = "";

  return {
    name: "gera-service-worker",
    apply: "build" as const,
    configResolved(config: { root: string; build: { outDir: string } }) {
      raizDoProjeto = config.root;
      saida = join(config.root, config.build.outDir);
    },
    closeBundle() {
      const arquivos = listaArquivos(saida)
        .filter((url) => EXTENSOES_DO_CASCO.some((ext) => url.endsWith(ext)))
        .filter((url) => !FORA_DO_CASCO.includes(url.slice(1)))
        .filter((url) => !PASTAS_FORA_DO_CASCO.some((pasta) => url.startsWith(pasta)))
        .sort();

      const versao = createHash("sha256").update(arquivos.join("\n")).digest("hex").slice(0, 12);
      const modelo = readFileSync(join(raizDoProjeto, "src/pwa/service-worker.js"), "utf8");

      writeFileSync(
        join(saida, "sw.js"),
        modelo
          .replace("__VERSION__", versao)
          .replace("__PRECACHE__", JSON.stringify(arquivos, null, 2)),
        "utf8",
      );
    },
  };
}

export default defineConfig({
  plugins: [dominioDoSite(), react(), exigeUrlDaApi(), geraServiceWorker()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
