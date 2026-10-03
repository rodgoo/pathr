/**
 * Remover o currículo precisa invalidar o cache de análise de vaga por IA.
 *
 * `vagasGuardadas.ts` guarda a análise de cada vaga em memória porque ela
 * compara a vaga com o perfil E o currículo — mudar qualquer um dos dois a
 * invalida, e isso é feito chamando `esquecerVagas()`. `resumes.remove`
 * (DELETE /resumes/:id) não passava por essa invalidação: quem excluía o
 * currículo usado numa análise continuava vendo, na volta, a leitura antiga.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { resumes } from "@/api/endpoints";
import { analisesGuardadas, vagasGuardadas } from "@/lib/vagasGuardadas";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

describe("remover currículo", () => {
  it("esquece a análise de vaga e a lista guardadas depois do DELETE", async () => {
    mockServer({ "DELETE /resumes/cv-1": () => ({ status: 204 }) });

    vagasGuardadas.set("docker", { vagas: [], total: 0 } as never);
    analisesGuardadas.set("vaga-1", { resumo: "compatível" } as never);
    expect(vagasGuardadas.get("docker")).toBeDefined();
    expect(analisesGuardadas.get("vaga-1")).toBeDefined();

    await resumes.remove("cv-1");

    expect(vagasGuardadas.get("docker")).toBeUndefined();
    expect(analisesGuardadas.get("vaga-1")).toBeUndefined();
  });
});
