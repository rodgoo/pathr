/**
 * O canal que avisa esta tela do que mudou em outro aparelho.
 *
 * O que importa aqui não é SSE funcionar — isso é do navegador. É o que a
 * tela FAZ com o que chega: reconsultar quando outro aparelho gravou, e
 * ficar quieta quando o aviso é o eco da própria escrita. Sem a segunda
 * metade, cada gravação custaria uma rodada extra de requisições em todo
 * aparelho, inclusive no que acabou de gravar.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dataRevision } from "@/offline/status";
import {
  ID_DESTA_ABA,
  conectarEventos,
  desconectarEventos,
} from "@/offline/eventos";

/** Um `EventSource` de mentira, para o teste empurrar eventos à mão. */
class FonteFalsa {
  static ultima: FonteFalsa | null = null;
  onmessage: ((evento: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onopen: (() => void) | null = null;
  fechada = false;

  constructor(
    readonly url: string,
    readonly init?: { withCredentials?: boolean },
  ) {
    FonteFalsa.ultima = this;
  }

  close() {
    this.fechada = true;
  }

  emite(corpo: unknown) {
    this.onmessage?.({ data: JSON.stringify(corpo) });
  }
}

function contaRevisoes() {
  let vezes = 0;
  const parar = dataRevision.subscribe(() => {
    vezes += 1;
  });
  return { vezes: () => vezes, parar };
}

beforeEach(() => {
  FonteFalsa.ultima = null;
  vi.stubGlobal("EventSource", FonteFalsa);
  vi.useFakeTimers();
});

afterEach(() => {
  desconectarEventos();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("canal de avisos", () => {
  it("abre com o cookie de sessão", () => {
    conectarEventos();

    // Sem `withCredentials` o cookie não atravessa para a outra origem e o
    // servidor responde 401 — o canal nunca subiria.
    expect(FonteFalsa.ultima?.init?.withCredentials).toBe(true);
    expect(FonteFalsa.ultima?.url).toMatch(/\/events$/);
  });

  it("manda reconsultar quando outro aparelho gravou", () => {
    conectarEventos();
    const contador = contaRevisoes();

    FonteFalsa.ultima?.emite({ rota: "/roadmap/nodes/n-1", origem: "outra-aba" });
    vi.advanceTimersByTime(200);

    expect(contador.vezes()).toBe(1);
    contador.parar();
  });

  it("ignora o eco da própria escrita", () => {
    conectarEventos();
    const contador = contaRevisoes();

    FonteFalsa.ultima?.emite({ rota: "/roadmap/nodes/n-1", origem: ID_DESTA_ABA });
    vi.advanceTimersByTime(200);

    // Esta aba já atualizou a própria tela ao gravar. Reconsultar por causa
    // do próprio POST seria uma requisição a mais por escrita.
    expect(contador.vezes()).toBe(0);
    contador.parar();
  });

  it("não reconsulta pelo aperto de mão inicial", () => {
    conectarEventos();
    const contador = contaRevisoes();

    // O primeiro evento só confirma que o canal está de pé.
    FonteFalsa.ultima?.emite({ rota: "", origem: "", aberto: true });
    vi.advanceTimersByTime(200);

    expect(contador.vezes()).toBe(0);
    contador.parar();
  });

  it("junta uma rajada de avisos numa reconsulta só", () => {
    conectarEventos();
    const contador = contaRevisoes();

    // Salvar o perfil dispara várias escritas seguidas no outro aparelho.
    // Cada uma vira um aviso; as telas não podem recarregar cinco vezes.
    for (let i = 0; i < 5; i += 1) {
      FonteFalsa.ultima?.emite({ rota: `/tags/mine/${i}`, origem: "outra-aba" });
    }
    vi.advanceTimersByTime(200);

    expect(contador.vezes()).toBe(1);
    contador.parar();
  });

  it("reabre depois de uma queda, com espera", () => {
    conectarEventos();
    const primeira = FonteFalsa.ultima;

    primeira?.onerror?.();

    // Nada imediato: um laço apertado de reconexão contra uma API fora do ar
    // é o oposto do que ajuda.
    expect(FonteFalsa.ultima).toBe(primeira);
    vi.advanceTimersByTime(2_500);
    expect(FonteFalsa.ultima).not.toBe(primeira);
  });

  it("para de reconectar depois de desligado", () => {
    conectarEventos();
    const primeira = FonteFalsa.ultima;

    desconectarEventos();
    primeira?.onerror?.();
    vi.advanceTimersByTime(120_000);

    // No logout o canal precisa MORRER: sem sessão o servidor responde 401,
    // e insistir seria um pedido recusado a cada dois segundos.
    expect(primeira?.fechada).toBe(true);
    expect(FonteFalsa.ultima).toBe(primeira);
  });
});
