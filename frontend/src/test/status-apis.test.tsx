/**
 * A aba de status das integrações.
 *
 * O que se segura: o resumo conta os problemas, cada integração diz o que
 * sustenta e o uso da cota, e "verificar agora" respeita a espera do servidor.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiStatusReport } from "@/api/types";
import { ApiStatusTab } from "@/components/profile/ApiStatusTab";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

const relatorio = (extra: Partial<ApiStatusReport> = {}): ApiStatusReport => ({
  verificado_em: new Date().toISOString(),
  pode_atualizar_em_s: 0,
  resumo: { ok: 2, degradada: 1, erro: 0, nao_configurada: 1, sem_verificacao: 0 },
  itens: [
    { id: "supabase", nome: "Supabase (banco de dados)", categoria: "Base", para_que: "Guarda tudo.", configurada: true,
      estado: "ok", detalhe: "Tabelas acessíveis.", latencia_ms: 120, uso: null },
    { id: "ia:Groq", nome: "Groq", categoria: "Inteligência artificial", para_que: "Gera conteúdo.", configurada: true,
      estado: "degradada", detalhe: "Limite de uso atingido.", latencia_ms: 300, uso: { hoje: { requisicoes: 21, tokens: 78230 } },
      modelo: "openai/gpt-oss-120b" },
    { id: "deepl", nome: "DeepL", categoria: "Idiomas", para_que: "Tradução.", configurada: true, estado: "ok",
      detalhe: "Respondendo normalmente.", latencia_ms: 200, uso: { usados: 5126, limite: 1000000, unidade: "caracteres no mês" } },
    { id: "adzuna", nome: "Adzuna", categoria: "Vagas", para_que: "Vagas.", configurada: false, estado: "nao_configurada",
      detalhe: "Sem ADZUNA_APP_ID e ADZUNA_APP_KEY.", latencia_ms: null, uso: null },
  ],
  ...extra,
});

describe("status das APIs", () => {
  it("resume os problemas e agrupa por categoria", async () => {
    mockServer({ "GET /status/apis": () => ({ body: relatorio() }) });
    render(<ApiStatusTab />);

    expect(await screen.findByText("1 integração com problema")).toBeInTheDocument();
    const ia = screen.getByRole("region", { name: "Inteligência artificial" });
    const groq = within(ia).getByRole("group", { name: "Groq: Com problema" });
    expect(within(groq).getByText("Limite de uso atingido.")).toBeInTheDocument();
    expect(within(groq).getByText(/21 requisições · 78\.230 tokens/)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Adzuna: Sem chave" })).toBeInTheDocument();
  });

  it("mostra a cota usada do DeepL", async () => {
    mockServer({ "GET /status/apis": () => ({ body: relatorio() }) });
    render(<ApiStatusTab />);
    expect(await screen.findByRole("meter", { name: "Uso de DeepL" })).toHaveAttribute("aria-valuenow", "1");
  });

  it("verificar agora pede atualização, e espera quando o servidor manda", async () => {
    let chamadas = 0;
    const servidor = mockServer({
      "GET /status/apis": () => {
        chamadas += 1;
        return { body: relatorio({ pode_atualizar_em_s: chamadas > 1 ? 60 : 0 }) };
      },
    });
    const user = userEvent.setup();
    render(<ApiStatusTab />);

    await user.click(await screen.findByRole("button", { name: "Verificar agora" }));
    expect(await screen.findByRole("button", { name: "Verificar de novo em 60s" })).toBeDisabled();
    expect(servidor.calls.map((c) => c.url)).toEqual(["/status/apis?atualizar=false", "/status/apis?atualizar=true"]);
  });
});
