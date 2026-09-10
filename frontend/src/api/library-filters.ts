/**
 * Os filtros de tipo da biblioteca.
 *
 * Ficam à parte dos endpoints porque são vocabulário de INTERFACE — o
 * reducer guarda qual está ativo, e importar isso de um módulo que fala com a
 * rede faria o estado depender do cliente HTTP sem motivo.
 *
 * As chaves são as de `pathr_resource.kind`, mais "todos" para nenhum filtro.
 *
 * "Cursos" saiu. Um link para uma plataforma de curso não é material que este
 * app consiga acompanhar: ele não sabe se a pessoa assistiu, quanto viu, nem o
 * que aprendeu — e a Biblioteca inteira existe para medir isso. O filtro dava
 * a entender uma capacidade que não existe. Volta no dia em que o PathR montar
 * o curso por dentro e puder aferir o aprendizado dele.
 * O ícone acompanha o rótulo: seis pílulas de texto puro, lado a lado, viram
 * um bloco em que não se distingue nada sem ler as seis.
 */

import type { IconName } from "@/components/ui/icons";

export const LIBRARY_FILTERS = [
  { key: "todos", label: "Tudo", icon: "library" },
  { key: "video", label: "Vídeos", icon: "play" },
  { key: "article", label: "Artigos", icon: "article" },
  { key: "doc", label: "Documentação", icon: "file" },
  { key: "exercise", label: "Exercícios", icon: "code" },
] as const satisfies readonly { key: string; label: string; icon: IconName }[];

export type LibraryFilter = (typeof LIBRARY_FILTERS)[number]["key"];

/** Rótulo em português para um `kind` vindo do servidor.
 *
 * `course` continua aqui mesmo sem filtro próprio: linhas gravadas antes da
 * remoção ainda têm esse tipo, e sem o rótulo elas apareceriam sem nada escrito
 * em "Tudo". O filtro sumiu; o que já existe continua legível. */
export const KIND_LABEL: Record<string, string> = {
  video: "vídeo",
  article: "artigo",
  course: "curso",
  doc: "documentação",
  book: "livro",
  podcast: "podcast",
  repo: "repositório",
  exercise: "exercício",
};
