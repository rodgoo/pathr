/**
 * A última lista de vagas, guardada enquanto o app está aberto.
 *
 * Buscar vagas passa por quatro fontes e leva segundos. Sair da tela e voltar
 * não é pedir vagas novas — é voltar à lista que estava ali. Por isso a tela
 * reabre com o que já tinha, e só vai às fontes quando a pessoa aperta
 * "Atualizar" (ou muda o que está procurando).
 *
 * Em memória e não no navegador: a lista é da pessoa logada, e sai junto no
 * logout (ver useAuth). Recarregar a página busca de novo — o servidor ainda
 * tem as fontes em cache, então é rápido.
 */

import type { JobList } from "@/api/types";

const guardadas = new Map<string, JobList>();

export const vagasGuardadas = {
  get: (termo: string) => guardadas.get(termo),
  set: (termo: string, lista: JobList) => void guardadas.set(termo, lista),
};

export function esquecerVagas(): void {
  guardadas.clear();
}
