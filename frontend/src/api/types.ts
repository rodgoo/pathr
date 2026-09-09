/**
 * Formatos que a API devolve.
 *
 * Espelham os schemas do backend (backend/app/schemas e os dicionários que os
 * routers montam). Onde o backend devolve uma linha do banco quase crua, o
 * tipo aqui lista só os campos que a interface realmente usa — inventar um
 * tipo com tudo daria a impressão de que a tela depende de mais do que
 * depende.
 */

export interface User {
  id: string;
  email: string;
  name: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  onboarding_completed: boolean;
  locale: string;
  timezone_name: string;
  theme: string;
}

export interface Session {
  user: User;
  access_token: string;
  expires_in: number;
}

export interface Profile {
  user_id: string;
  headline: string | null;
  current_role: string | null;
  target_role: string | null;
  seniority: string | null;
  years_experience: number | null;
  weekly_hours: number;
  learning_style: string | null;
  goals: unknown[];
  bio: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  /** Avisos por e-mail. O servidor sempre devolve as cinco chaves, ja com
   * o padrao aplicado — o front nao guarda padrao nenhum. */
  notifications?: Record<string, boolean>;
}

export interface Streak {
  current: number;
  longest: number;
  last_active_date: string | null;
  total_xp: number;
  total_minutes: number;
}

/** Um dia do heatmap. `count` são ações concluídas, não minutos. */
export interface ActivityDay {
  date: string;
  minutes: number;
  count: number;
  xp: number;
}

export interface ActivitySummary {
  days: ActivityDay[];
  active_days: number;
  total_minutes: number;
  total_xp: number;
}

export type NodeStatus = "locked" | "todo" | "doing" | "done" | "skipped";
export type NodeKind = "phase" | "skill" | "project" | "checkpoint" | "reading";

export interface RoadmapNode {
  id: string;
  title: string;
  description: string | null;
  kind: NodeKind;
  status: NodeStatus;
  progress_pct: number;
  level: string | null;
  estimated_hours: number;
  week_start: number | null;
  week_end: number | null;
  tag_ids: string[];
  objectives: string[];
  order_index: number;
}

export interface RoadmapPhase extends RoadmapNode {
  modules: RoadmapNode[];
}

export interface Roadmap {
  id: string;
  title: string;
  target_role: string | null;
  horizon_weeks: number;
  weekly_hours: number;
  status: string;
  summary: string | null;
  progress_pct: number;
  total_nodes: number;
  done_nodes: number;
  phases: RoadmapPhase[];
}

export interface RoadmapSummary {
  id: string;
  title: string;
  horizon_weeks: number;
  weekly_hours: number;
  status: string;
  total_nodes: number;
  done_nodes: number;
  progress_pct: number;
  current_node: RoadmapNode | null;
}

export interface Overview {
  profile: Profile;
  streak: Streak;
  english: { enabled: boolean; cefr_level: string | null; target_level: string };
  roadmap: RoadmapSummary | null;
  activity: ActivitySummary;
}

export interface Tag {
  id: string;
  slug: string;
  name: string;
  category: string;
  color: string | null;
  popularity: number;
}

export interface UserTag {
  id: string;
  tag_id: string;
  slug: string;
  name: string;
  category: string;
  color: string | null;
  proficiency: number;
  confidence: number;
  is_target: boolean;
  source: string;
  last_assessed_at: string | null;
}

export type ResumeStatus = "pending" | "parsing" | "parsed" | "failed";

/** Uma tecnologia como a IA a leu, antes da revisão do usuário. */
export interface ParsedTechnology {
  nome: string;
  categoria: string;
  proficiencia: number;
  anos: number;
  /** A frase do currículo que sustenta a estimativa. Pode vir vazia. */
  evidencia: string;
}

export interface ParsedResume {
  nome: string;
  email: string;
  cidade: string;
  cargo_atual: string;
  senioridade: string;
  anos_experiencia: number;
  resumo: string;
  linkedin: string;
  github: string;
  tecnologias: ParsedTechnology[];
  experiencias: unknown[];
  formacao: unknown[];
  idiomas: unknown[];
  projetos: unknown[];
}

export interface Resume {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: ResumeStatus;
  error: string | null;
  is_primary: boolean;
  parsed: ParsedResume | Record<string, never>;
  created_at: string;
  parsed_at: string | null;
  /** Só na resposta do upload: o arquivo já tinha sido lido antes. */
  reused?: boolean;
}

export type ResourceKind = "video" | "article" | "course" | "doc" | "book" | "podcast" | "repo" | "exercise";
export type ResourceState = "saved" | "in_progress" | "done" | "dismissed";

export interface Resource {
  id: string;
  kind: ResourceKind;
  title: string;
  url: string;
  provider: string | null;
  author: string | null;
  description: string | null;
  duration_min: number | null;
  language: string;
  level: string | null;
  tag_ids: string[];
  quality_score: number;
  user_status: ResourceState | null;
  user_progress_pct: number;
  user_rating: number | null;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  code_snippet: string | null;
  code_language: string | null;
  options: string[];
  difficulty: string;
  order_index: number;
}

export interface Quiz {
  id: string;
  title: string;
  kind: string;
  difficulty: string;
  question_count: number;
  tag_ids: string[];
  questions: QuizQuestion[];
}

export interface QuizResult {
  attempt_id: string;
  score: number;
  correct_count: number;
  total: number;
  results: {
    question_id: string;
    answer: number | null;
    correct_index: number;
    is_correct: boolean;
    explanation: string;
  }[];
  /**
   * O que o erro virou. `volta` são os conceitos que reaparecerão reescritos
   * no próximo quiz da tag; `aprendido` são os que a pessoa acabou de fechar
   * ao acertar uma questão reciclada.
   *
   * Opcional porque tentativas gravadas antes da reciclagem existir não têm
   * este campo — e uma tela que quebra ao abrir um resultado antigo seria
   * pior que uma que só não mostra o aviso.
   */
  review?: { volta: string[]; aprendido: string[] };
}

export interface EnglishProfile {
  user_id: string;
  enabled: boolean;
  cefr_level: string | null;
  target_level: string;
  sub_scores: Record<string, number>;
  focus_areas: unknown[];
  daily_goal_min: number;
  last_assessment_at: string | null;
}

export interface EnglishItem {
  id: string;
  skill: string;
  cefr_band: string;
  prompt: string;
  context: string | null;
  options: string[];
  order_index: number;
}

export interface EnglishAssessment {
  id: string;
  status: string;
  item_count: number;
  answered_count: number;
  correct_count: number;
  cefr_result: string | null;
  items: EnglishItem[];
}

export interface EnglishAnswerResult {
  is_correct: boolean;
  correct_index: number;
  explanation: string;
  finished: boolean;
  answered?: number;
  total?: number;
  result?: { cefr_level: string; sub_scores: Record<string, number> };
}
