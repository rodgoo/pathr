import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

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

export default defineConfig({
  plugins: [react(), exigeUrlDaApi()],
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
