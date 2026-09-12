/**
 * Estado de INTERFACE do app.
 *
 * Só o que é escolha de navegação e visualização: qual tela, qual aba, qual
 * recorte do gráfico, o que está digitado numa busca. Nada de dado de
 * domínio — perfil, competências, roadmap, biblioteca e quizzes vêm do
 * servidor pelos hooks de `useApi`, e guardar uma cópia aqui criaria duas
 * fontes de verdade que divergem no primeiro erro de rede.
 *
 * Antes desta separação o reducer também carregava os dados de exemplo do
 * protótipo. Eles saíram junto com os arquivos de fixture.
 */

import type { LibraryFilter } from "@/api/library-filters";
import type {
  ActivityMode,
  ConstancyView,
  ContentLang,
  ModuleTab,
  RoadmapView,
  Screen,
  SettingsTab,
} from "@/types";

export interface AppState {
  screen: Screen;

  /** Apresentação do roadmap e do módulo. */
  roadmapView: RoadmapView;
  moduleTab: ModuleTab;
  activityMode: ActivityMode;
  constancyView: ConstancyView;
  settingsTab: SettingsTab;

  /** Idioma do material — vale para a biblioteca e para o módulo. */
  contentLang: ContentLang;

  /** Campos de busca. Ficam aqui para sobreviver à troca de tela. */
  librarySearch: string;
  libraryFilter: LibraryFilter;
  skillSearch: string;

  /** O módulo aberto na trilha. `null` = o que o servidor marcar como atual. */
  activeNodeId: string | null;
  /** O quiz em andamento, quando existe. */
  activeQuizId: string | null;
  /** O currículo em revisão, entre o upload e a importação. */
  activeResumeId: string | null;
  /** O material aberto na tela dele. */
  activeResourceId: string | null;
  /**
   * Para onde o "voltar" da tela de material leva.
   *
   * Hoje o material é alcançado de um lugar só — a aba de material do módulo,
   * que absorveu a Biblioteca. O campo fica porque o destino continua sendo
   * uma decisão de quem abre: uma segunda porta para o mesmo material
   * (a busca do painel, um link de aviso) vai querer voltar para a porta dela.
   */
  resourceReturn: Screen;
}

export const INITIAL_STATE: AppState = {
  screen: "home",
  roadmapView: "a",
  moduleTab: "material",
  activityMode: "escrever",
  constancyView: "ano",
  settingsTab: "conta",
  contentLang: "pt",
  librarySearch: "",
  libraryFilter: "todos",
  skillSearch: "",
  activeNodeId: null,
  activeQuizId: null,
  activeResumeId: null,
  activeResourceId: null,
  resourceReturn: "modulo",
};

export type Action =
  | {
      type: "navigate";
      screen: Screen;
      moduleTab?: ModuleTab;
      settingsTab?: SettingsTab;
      nodeId?: string | null;
    }
  | { type: "setRoadmapView"; view: RoadmapView }
  | { type: "setModuleTab"; tab: ModuleTab }
  | { type: "setActivityMode"; mode: ActivityMode }
  | { type: "setConstancyView"; view: ConstancyView }
  | { type: "setSettingsTab"; tab: SettingsTab }
  | { type: "setContentLang"; lang: ContentLang }
  | { type: "setLibrarySearch"; value: string }
  | { type: "setLibraryFilter"; filter: LibraryFilter }
  | { type: "setSkillSearch"; value: string }
  | { type: "openNode"; nodeId: string | null }
  | { type: "openQuiz"; quizId: string | null }
  | { type: "openResume"; resumeId: string | null }
  | { type: "openResource"; resourceId: string };

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "navigate":
      return {
        ...state,
        screen: action.screen,
        moduleTab: action.moduleTab ?? state.moduleTab,
        settingsTab: action.settingsTab ?? state.settingsTab,
        activeNodeId: action.nodeId !== undefined ? action.nodeId : state.activeNodeId,
        // Sair da trilha encerra o quiz aberto: voltar depois e reencontrar
        // um quiz pela metade, sem contexto, é pior que recomeçar.
        activeQuizId: action.screen === "modulo" ? state.activeQuizId : null,
      };

    case "setRoadmapView":
      return { ...state, roadmapView: action.view };
    case "setModuleTab":
      return { ...state, moduleTab: action.tab };
    case "setActivityMode":
      return { ...state, activityMode: action.mode };
    case "setConstancyView":
      return { ...state, constancyView: action.view };
    case "setSettingsTab":
      return { ...state, settingsTab: action.tab };
    case "setContentLang":
      return { ...state, contentLang: action.lang };
    case "setLibrarySearch":
      return { ...state, librarySearch: action.value };
    case "setLibraryFilter":
      return { ...state, libraryFilter: action.filter };
    case "setSkillSearch":
      return { ...state, skillSearch: action.value };
    case "openNode":
      return { ...state, activeNodeId: action.nodeId, activeQuizId: null };
    case "openQuiz":
      return { ...state, activeQuizId: action.quizId };
    case "openResume":
      return { ...state, activeResumeId: action.resumeId };

    case "openResource":
      // Guarda de onde veio no mesmo passo em que abre: depois de trocar de
      // tela essa informação já se perdeu.
      return {
        ...state,
        screen: "material",
        activeResourceId: action.resourceId,
        resourceReturn: state.screen === "material" ? state.resourceReturn : state.screen,
      };

    default: {
      // Exaustividade: uma ação nova sem case falha a compilação aqui.
      const unreachable: never = action;
      return unreachable;
    }
  }
}
