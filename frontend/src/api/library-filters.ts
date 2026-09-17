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
import { traduzirPt, type Traduzir } from "@/lib/i18n";

/** `label` guarda a CHAVE de tradução; quem renderiza resolve com `t()`. */
export const LIBRARY_FILTERS = [
  { key: "todos", label: "biblioteca.filtro.todos", icon: "library" },
  { key: "video", label: "biblioteca.filtro.video", icon: "play" },
  { key: "article", label: "biblioteca.filtro.article", icon: "article" },
  { key: "doc", label: "biblioteca.filtro.doc", icon: "file" },
  { key: "exercise", label: "biblioteca.filtro.exercise", icon: "code" },
] as const satisfies readonly { key: string; label: string; icon: IconName }[];

export type LibraryFilter = (typeof LIBRARY_FILTERS)[number]["key"];

/** A chave de tradução de cada `kind` vindo do servidor.
 *
 * `course` continua aqui mesmo sem filtro próprio: linhas gravadas antes da
 * remoção ainda têm esse tipo, e sem o rótulo elas apareceriam sem nada escrito
 * em "Tudo". O filtro sumiu; o que já existe continua legível. */
const KIND_KEY: Record<string, string> = {
  video: "biblioteca.kind.video",
  article: "biblioteca.kind.article",
  course: "biblioteca.kind.course",
  doc: "biblioteca.kind.doc",
  book: "biblioteca.kind.book",
  podcast: "biblioteca.kind.podcast",
  repo: "biblioteca.kind.repo",
  exercise: "biblioteca.kind.exercise",
};

/** Rótulo do `kind` no idioma de quem lê; `kind` desconhecido volta como veio. */
export function kindLabel(kind: string, t: Traduzir = traduzirPt): string {
  const chave = KIND_KEY[kind];
  return chave ? t(chave) : kind;
}
