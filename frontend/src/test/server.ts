/**
 * Um servidor de mentira para os testes de integração.
 *
 * Substitui `fetch` por um roteador de rotas conhecidas. É deliberadamente
 * mais burro que MSW: a suíte precisa afirmar coisas sobre o que a interface
 * faz com uma resposta, não sobre HTTP, e um interceptador de rede completo
 * traria um servidor de verdade para dentro de testes que rodam em jsdom.
 *
 * Cada teste declara só as rotas que a tela dele chama; qualquer outra
 * responde 404 e o erro aparece na tela, que é o comportamento real.
 */

import { vi } from "vitest";
import type { Overview, User } from "@/api/types";

export type Handler = (request: { url: string; method: string; body: unknown }) => {
  status?: number;
  body?: unknown;
  headers?: Record<string, string>;
};

export interface MockServer {
  /** Chamadas recebidas, em ordem — para afirmar que a tela pediu o que devia. */
  calls: { method: string; url: string; body: unknown }[];
  on: (route: string, handler: Handler) => void;
}

/**
 * Instala o `fetch` falso. A chave da rota é "MÉTODO /caminho"; o caminho é
 * comparado só pelo prefixo, então "/library" cobre "/library?q=docker".
 */
export function mockServer(routes: Record<string, Handler> = {}): MockServer {
  const table = new Map<string, Handler>(Object.entries(routes));
  const calls: MockServer["calls"] = [];

  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    const body = init?.body ? safeParse(String(init.body)) : undefined;
    calls.push({ method, url: path, body });

    // Da rota mais específica para a mais genérica: sem isso
    // "POST /resumes" capturaria "POST /resumes/cv-1/parse", e o teste
    // afirmaria sobre uma resposta que não é a da rota exercitada.
    const match = [...table.entries()]
      .sort(([a], [b]) => b.length - a.length)
      .find(([key]) => {
        const [routeMethod, routePath] = key.split(" ");
        return routeMethod === method && path.startsWith(routePath);
      });

    if (!match) {
      return jsonResponse(404, { detail: `Rota não registrada no teste: ${method} ${path}` });
    }
    const result = match[1]({ url: path, method, body });
    return jsonResponse(result.status ?? 200, result.body ?? {}, result.headers);
  });

  return { calls, on: (route, handler) => table.set(route, handler) };
}

function safeParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

// --- Fixtures mínimas, só o que os testes afirmam ---

export const aUser = (overrides: Partial<User> = {}): User => ({
  id: "user-1",
  email: "lucas@exemplo.com",
  name: "Lucas Martins",
  email_verified: true,
  mfa_enabled: false,
  onboarding_completed: true,
  locale: "pt-BR",
  timezone_name: "America/Sao_Paulo",
  theme: "system",
  has_avatar: false,
  ...overrides,
});

export const anOverview = (overrides: Partial<Overview> = {}): Overview => ({
  profile: {
    user_id: "user-1",
    headline: null,
    current_role: "Desenvolvedor frontend",
    target_role: null,
    seniority: "pleno",
    years_experience: 3,
    weekly_hours: 8,
    learning_style: null,
    goals: [],
    bio: null,
    linkedin_url: null,
    github_url: null,
  },
  streak: {
    current: 3,
    longest: 12,
    last_active_date: "2026-09-09",
    total_xp: 240,
    total_minutes: 480,
  },
  english: { enabled: true, cefr_level: "B1", target_level: "B2" },
  roadmap: null,
  activity: { days: [], active_days: 0, total_minutes: 480, total_xp: 240 },
  ...overrides,
});
