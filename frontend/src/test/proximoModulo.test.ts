import { describe, expect, it } from "vitest";

import type { NodeStatus, RoadmapNode } from "@/api/types";
import { proximoModulo } from "@/lib/proximoModulo";

function modulo(id: string, status: NodeStatus, ordem: number): RoadmapNode {
  return {
    id,
    title: id,
    description: null,
    kind: "skill",
    status,
    progress_pct: 0,
    level: null,
    estimated_hours: 1,
    week_start: null,
    week_end: null,
    tag_ids: [],
    objectives: [],
    order_index: ordem,
  } as RoadmapNode;
}

describe("proximoModulo", () => {
  it("abre o que o servidor promoveu a em andamento logo depois do concluído", () => {
    const lista = [modulo("git", "done", 1), modulo("docker", "done", 2), modulo("ci", "doing", 3), modulo("aws", "todo", 4)];
    expect(proximoModulo(lista, "docker")?.id).toBe("ci");
  });

  it("sem nenhum em andamento, abre o primeiro por fazer depois do concluído", () => {
    const lista = [modulo("git", "done", 1), modulo("docker", "done", 2), modulo("ci", "todo", 3), modulo("aws", "todo", 4)];
    expect(proximoModulo(lista, "docker")?.id).toBe("ci");
  });

  it("prefere o em andamento que vem DEPOIS a um por fazer que vem antes dele", () => {
    const lista = [modulo("a", "done", 1), modulo("b", "todo", 2), modulo("c", "todo", 3), modulo("d", "doing", 4)];
    expect(proximoModulo(lista, "a")?.id).toBe("d");
  });

  it("não escolhe módulo travado nem já concluído", () => {
    const lista = [modulo("a", "done", 1), modulo("b", "locked", 2), modulo("c", "done", 3), modulo("d", "todo", 4)];
    expect(proximoModulo(lista, "a")?.id).toBe("d");
  });

  it("voltar a um módulo pulado é melhor que dizer que acabou", () => {
    const lista = [modulo("a", "todo", 1), modulo("b", "done", 2), modulo("c", "done", 3)];
    expect(proximoModulo(lista, "c")?.id).toBe("a");
  });

  it("devolve null quando o último módulo foi concluído", () => {
    const lista = [modulo("a", "done", 1), modulo("b", "done", 2)];
    expect(proximoModulo(lista, "b")).toBeNull();
  });

  it("nunca devolve o próprio módulo concluído", () => {
    const lista = [modulo("a", "doing", 1)];
    expect(proximoModulo(lista, "a")).toBeNull();
  });

  it("aguenta lista vazia e id desconhecido", () => {
    expect(proximoModulo([], "x")).toBeNull();
    expect(proximoModulo([modulo("a", "todo", 1)], "desconhecido")?.id).toBe("a");
  });
});
