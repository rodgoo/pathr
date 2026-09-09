/**
 * Os filtros de tipo da biblioteca.
 *
 * Ficam à parte dos endpoints porque são vocabulário de INTERFACE — o
 * reducer guarda qual está ativo, e importar isso de um módulo que fala com a
 * rede faria o estado depender do cliente HTTP sem motivo.
 *
 * As chaves são as de `pathr_resource.kind`, mais "todos" para nenhum filtro.
 */

export const LIBRARY_FILTERS = [
  { key: "todos", label: "Tudo" },
  { key: "video", label: "Vídeos" },
  { key: "article", label: "Artigos" },
  { key: "course", label: "Cursos" },
  { key: "doc", label: "Documentação" },
  { key: "exercise", label: "Exercícios" },
] as const;

export type LibraryFilter = (typeof LIBRARY_FILTERS)[number]["key"];

/** Rótulo em português para um `kind` vindo do servidor. */
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
