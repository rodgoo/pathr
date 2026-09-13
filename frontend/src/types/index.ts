/**
 * Vocabulário de INTERFACE.
 *
 * Só o que descreve escolhas de navegação e visualização. Os formatos de
 * dado vivem em `src/api/types.ts`, espelhando o que a API devolve — manter
 * os dois aqui foi o que, no protótipo, fez existirem dois `UserTag`
 * diferentes com o mesmo nome.
 */

/** Destino de topo. Um por tela do produto. */
export type Screen =
  | "home"
  | "cv"
  | "roadmap"
  | "modulo"
  | "ingles"
  | "perfil"
  | "codigo"
  | "material"
  | "cursos"
  | "vagas"
  | "config";

/** Idioma do material curado. "both" é ausência de filtro, não um terceiro. */
export type ContentLang = "pt" | "en" | "both";

/** Recorte do painel de constância. */
export type ConstancyView = "ano" | "mes" | "semana";

/** Apresentação do roadmap: linha do tempo, fases lado a lado, matriz. */
export type RoadmapView = "a" | "b" | "c";

/** Abas do módulo aberto. */
export type ModuleTab = "material" | "quiz" | "atividade";

/** A atividade prática tem dois formatos: escrever, ou revisar código alheio. */
export type ActivityMode = "escrever" | "revisar";

/** Seções da tela de configurações. */
export type SettingsTab = "conta" | "objetivo" | "skills" | "idiomas" | "avisos" | "integracoes";
