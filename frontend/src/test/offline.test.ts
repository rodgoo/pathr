/**
 * A camada offline: a fila de escritas, a projeção sobre o cache, e o que o
 * cliente HTTP faz quando a rede não responde.
 *
 * O foco é o comportamento que a pessoa percebe: o que ela marcou sem rede
 * não some, sobe na ordem certa quando a rede volta, e não fica preso para
 * sempre quando o servidor o recusa. Nada aqui afirma sobre IndexedDB — ele
 * está presente só porque é onde a fila mora.
 */

import "fake-indexeddb/auto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { ApiError } from "@/api/errors";
import { STORE_CACHE, STORE_META, idbClear, idbPut } from "@/offline/idb";
import { clearOutbox, enqueue, flush, outboxKey, pending } from "@/offline/outbox";
import { project } from "@/offline/projections";
import { readCached, resetOwnerCacheForTests, saveRead } from "@/offline/cache";
import type { Resource, Roadmap } from "@/api/types";

const DONO = "user-1";

async function limpaTudo() {
  await clearOutbox();
  await idbClear(STORE_CACHE);
  await idbClear(STORE_META);
  resetOwnerCacheForTests();
}

const umaEscrita = (path: string, body: Record<string, unknown>, method = "PATCH") => ({
  key: outboxKey(method, path),
  method,
  path,
  body,
  owner: DONO,
});

beforeEach(limpaTudo);

describe("fila de escritas", () => {
  it("funde dois pedidos para o mesmo alvo num só", async () => {
    // Arrange: as duas telas que mexem no progresso de um material mandam
    // campos diferentes.
    await enqueue(umaEscrita("/library/r-1/progress", { status: "in_progress", minutes_spent: 12 }, "PUT"));

    // Act
    await enqueue(umaEscrita("/library/r-1/progress", { status: "in_progress", position_note: "23:10" }, "PUT"));

    // Assert: um item, com os campos das duas — a segunda escrita não pode
    // apagar os minutos que a primeira registrou.
    const fila = await pending(DONO);
    expect(fila).toHaveLength(1);
    expect(fila[0].body).toEqual({ status: "in_progress", minutes_spent: 12, position_note: "23:10" });
  });

  it("mantém a ordem em que a pessoa agiu, não a da última edição", async () => {
    // Só o relógio é controlado, não os temporizadores: o IndexedDB de mentira
    // roda sobre eles, e congelá-los travaria a própria escrita que o teste
    // está exercitando.
    const agora = vi.spyOn(Date, "now");
    try {
      agora.mockReturnValue(1_000);
      await enqueue(umaEscrita("/roadmap/nodes/n-1", { status: "done" }));
      agora.mockReturnValue(2_000);
      await enqueue(umaEscrita("/roadmap/nodes/n-2", { status: "done" }));
      // Retocar o primeiro não pode mandá-lo para o fim da fila.
      agora.mockReturnValue(3_000);
      await enqueue(umaEscrita("/roadmap/nodes/n-1", { progress_pct: 100 }));

      const fila = await pending(DONO);
      expect(fila.map((item) => item.path)).toEqual(["/roadmap/nodes/n-1", "/roadmap/nodes/n-2"]);
    } finally {
      agora.mockRestore();
    }
  });

  it("envia na ordem e esvazia a fila", async () => {
    await enqueue(umaEscrita("/roadmap/nodes/n-1", { status: "done" }));
    await enqueue(umaEscrita("/roadmap/nodes/n-2", { status: "done" }));
    const enviados: string[] = [];

    const resultado = await flush(DONO, async (item) => {
      enviados.push(item.path);
    });

    expect(enviados).toEqual(["/roadmap/nodes/n-1", "/roadmap/nodes/n-2"]);
    expect(resultado).toEqual({ sent: 2, dropped: 0, kept: 0 });
    expect(await pending(DONO)).toHaveLength(0);
  });

  it("para no erro de rede e guarda o que sobrou", async () => {
    await enqueue(umaEscrita("/roadmap/nodes/n-1", { status: "done" }));
    await enqueue(umaEscrita("/roadmap/nodes/n-2", { status: "done" }));
    await enqueue(umaEscrita("/roadmap/nodes/n-3", { status: "done" }));

    const resultado = await flush(DONO, async (item) => {
      if (item.path !== "/roadmap/nodes/n-1") throw new TypeError("Failed to fetch");
    });

    expect(resultado).toEqual({ sent: 1, dropped: 0, kept: 2 });
    // Insistir nos seguintes com a rede fora só gastaria bateria.
    expect((await pending(DONO)).map((item) => item.path)).toEqual([
      "/roadmap/nodes/n-2",
      "/roadmap/nodes/n-3",
    ]);
  });

  it("descarta o que o servidor recusa de forma definitiva e segue", async () => {
    await enqueue(umaEscrita("/roadmap/nodes/apagado", { status: "done" }));
    await enqueue(umaEscrita("/roadmap/nodes/n-2", { status: "done" }));

    const resultado = await flush(DONO, async (item) => {
      if (item.path.endsWith("apagado")) throw new ApiError(404, "Módulo não encontrado");
    });

    // Sem isso o item viraria uma fila que nunca esvazia.
    expect(resultado).toEqual({ sent: 1, dropped: 1, kept: 0 });
    expect(await pending(DONO)).toHaveLength(0);
  });

  it("insiste quando a recusa foi 401 — pode ser só a sessão expirada", async () => {
    await enqueue(umaEscrita("/roadmap/nodes/n-1", { status: "done" }));

    const resultado = await flush(DONO, async () => {
      throw new ApiError(401, "Sessão expirada");
    });

    expect(resultado).toEqual({ sent: 0, dropped: 0, kept: 1 });
    expect(await pending(DONO)).toHaveLength(1);
  });

  it("não envia a fila de outra conta", async () => {
    await enqueue({ ...umaEscrita("/roadmap/nodes/n-1", { status: "done" }), owner: "outra-pessoa" });

    const resultado = await flush(DONO, async () => {
      throw new Error("não devia ter sido chamado");
    });

    expect(resultado.sent).toBe(0);
    expect(await pending("outra-pessoa")).toHaveLength(1);
  });
});

describe("projeção da fila sobre o cache", () => {
  const umPlano = (): Roadmap => ({
    id: "plano-1",
    title: "Backend sênior",
    target_role: "Backend sênior",
    horizon_weeks: 12,
    weekly_hours: 8,
    status: "active",
    summary: null,
    progress_pct: 0,
    total_nodes: 2,
    done_nodes: 0,
    phases: [
      {
        id: "f-1",
        title: "Fase 1",
        description: null,
        kind: "phase",
        status: "doing",
        progress_pct: 0,
        level: null,
        estimated_hours: 20,
        week_start: 1,
        week_end: 6,
        tag_ids: [],
        objectives: [],
        order_index: 0,
        modules: [
          {
            id: "n-1",
            title: "Docker",
            description: null,
            kind: "skill",
            status: "doing",
            progress_pct: 40,
            level: null,
            estimated_hours: 10,
            week_start: 1,
            week_end: 3,
            tag_ids: [],
            objectives: [],
            order_index: 0,
          },
          {
            id: "n-2",
            title: "Kubernetes",
            description: null,
            kind: "skill",
            status: "todo",
            progress_pct: 0,
            level: null,
            estimated_hours: 10,
            week_start: 4,
            week_end: 6,
            tag_ids: [],
            objectives: [],
            order_index: 1,
          },
        ],
      },
    ],
  });

  it("mostra o módulo concluído offline e refaz as contas do plano", () => {
    const fila = [
      { ...umaEscrita("/roadmap/nodes/n-1", { status: "done" }), queuedAt: 1, attempts: 0 },
    ];

    const projetado = project("/roadmap/current", umPlano(), fila) as Roadmap;

    // Sem isto, reabrir o app offline mostraria o módulo como "em andamento"
    // de novo — e a pessoa concluiria que o app perdeu o que ela fez.
    expect(projetado.phases[0].modules[0].status).toBe("done");
    expect(projetado.phases[0].modules[0].progress_pct).toBe(100);
    expect(projetado.done_nodes).toBe(1);
    expect(projetado.progress_pct).toBe(50);
  });

  it("não toca no plano quando a fila é de outro assunto", () => {
    const plano = umPlano();
    const fila = [
      { ...umaEscrita("/library/r-1/progress", { status: "done" }, "PUT"), queuedAt: 1, attempts: 0 },
    ];

    expect(project("/roadmap/current", plano, fila)).toBe(plano);
  });

  it("mostra o material marcado offline e onde a pessoa parou", () => {
    const materiais: Resource[] = [
      {
        id: "r-1",
        kind: "video",
        title: "Docker em 100 minutos",
        url: "https://exemplo",
        provider: "YouTube",
        author: null,
        description: null,
        duration_min: 100,
        language: "pt",
        level: null,
        tag_ids: [],
        quality_score: 8,
        user_status: null,
        user_progress_pct: 0,
        user_rating: null,
        user_position_note: null,
        user_position_seconds: null,
      },
    ];
    const fila = [
      {
        ...umaEscrita("/library/r-1/progress", { status: "in_progress", position_note: "23:10" }, "PUT"),
        queuedAt: 1,
        attempts: 0,
      },
    ];

    const projetado = project("/library?only_mine=true", materiais, fila) as Resource[];

    expect(projetado[0].user_status).toBe("in_progress");
    expect(projetado[0].user_position_note).toBe("23:10");
  });

  it("devolve o rascunho escrito offline, não o que o servidor tinha", () => {
    const fila = [
      {
        ...umaEscrita("/roadmap/nodes/n-1/draft", { content: "minha solução" }, "PUT"),
        queuedAt: 1,
        attempts: 0,
      },
    ];

    const projetado = project(
      "/roadmap/nodes/n-1/draft",
      { content: "versão antiga", updated_at: null },
      fila,
    ) as { content: string };

    expect(projetado.content).toBe("minha solução");
  });
});

describe("cache de leitura", () => {
  it("adota o dono a partir de /auth/me e devolve o que guardou", async () => {
    await saveRead("/auth/me", { id: DONO, name: "Lucas" });

    const guardado = await readCached("/auth/me");

    // É isto que faz o app instalado abrir logado no metrô, em vez de cair na
    // tela de entrada como se a sessão tivesse acabado.
    expect(guardado?.body).toMatchObject({ id: DONO });
  });

  it("esconde o que é de outra conta", async () => {
    await saveRead("/auth/me", { id: DONO, name: "Lucas" });
    await idbPut(STORE_CACHE, {
      path: "/roadmap/current",
      body: { title: "plano de outra pessoa" },
      savedAt: Date.now(),
      owner: "outra-pessoa",
    });

    expect(await readCached("/roadmap/current")).toBeNull();
  });

  it("não guarda o segredo do segundo fator", async () => {
    await saveRead("/auth/mfa/setup", { secret: "ABC123" });

    expect(await readCached("/auth/mfa/setup")).toBeNull();
  });

  it("aplica a fila sobre o que devolve", async () => {
    await saveRead("/auth/me", { id: DONO, name: "Lucas" });
    await saveRead("/roadmap/nodes/n-1/draft", { content: "vazio", updated_at: null });
    await enqueue(umaEscrita("/roadmap/nodes/n-1/draft", { content: "escrito sem rede" }, "PUT"));

    const guardado = await readCached("/roadmap/nodes/n-1/draft");

    expect((guardado?.body as { content: string }).content).toBe("escrito sem rede");
  });
});

describe("cliente HTTP sem rede", () => {
  const semRede = () => Promise.reject(new TypeError("Failed to fetch"));

  const respondeCom = (body: unknown) =>
    vi.stubGlobal("fetch", async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

  /**
   * A gravação no cache é disparada e não esperada — segurar a resposta de um
   * GET até o disco confirmar atrasaria toda tela por nada. O teste, esse
   * sim, precisa esperar.
   */
  const esperaGuardar = (path: string) =>
    vi.waitFor(async () => expect(await readCached(path)).not.toBeNull());

  afterEach(() => vi.unstubAllGlobals());

  it("devolve o último GET conhecido em vez de falhar", async () => {
    respondeCom({ id: DONO, name: "Lucas" });
    await api.get("/auth/me");
    await esperaGuardar("/auth/me");

    vi.stubGlobal("fetch", semRede);
    const offline = await api.get<{ name: string }>("/auth/me");

    // É isto que faz o app abrir logado no metrô em vez de mandar a pessoa
    // para a tela de entrada como se a sessão tivesse acabado.
    expect(offline.name).toBe("Lucas");
  });

  it("propaga o erro quando não há nada guardado para aquele caminho", async () => {
    vi.stubGlobal("fetch", semRede);

    // Fingir sucesso aqui esconderia a falha até a próxima abertura do app.
    await expect(api.get("/nunca/visto")).rejects.toThrow();
  });

  it("enfileira a escrita marcada como enfileirável", async () => {
    respondeCom({ id: DONO, name: "Lucas" });
    await api.get("/auth/me");
    await esperaGuardar("/auth/me");

    vi.stubGlobal("fetch", semRede);
    await api.patch("/roadmap/nodes/n-1", { status: "done" }, {});

    expect((await pending(DONO)).map((item) => item.path)).toEqual(["/roadmap/nodes/n-1"]);
  });

  it("deixa falhar a escrita que o servidor precisa processar na hora", async () => {
    respondeCom({ id: DONO, name: "Lucas" });
    await api.get("/auth/me");
    await esperaGuardar("/auth/me");

    vi.stubGlobal("fetch", semRede);

    // Corrigir um quiz offline exigiria o gabarito no aparelho, e repetir um
    // POST criaria a coisa duas vezes. Estes têm que dar erro na tela.
    await expect(api.post("/quizzes/q-1/submit", { answers: {} })).rejects.toThrow();
    expect(await pending(DONO)).toHaveLength(0);
  });
});
