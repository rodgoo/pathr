/**
 * As chamadas da API, tipadas e agrupadas por assunto.
 *
 * Uma função por endpoint em vez de as telas montarem URLs: quando uma rota
 * muda de forma, muda aqui e o TypeScript aponta cada chamador.
 */

import { api } from "./client";
import type {
  EnglishAnswerResult,
  EnglishAssessment,
  EnglishProfile,
  Overview,
  Profile,
  Quiz,
  QuizResult,
  Resource,
  Resume,
  Roadmap,
  Session,
  Tag,
  User,
  UserTag,
} from "./types";

export const auth = {
  // Não devolve sessão: a entrada exige e-mail confirmado, então o cadastro
  // termina numa mensagem, não num login.
  signup: (body: {
    name: string;
    email: string;
    password: string;
    birth_date: string;
    city: string;
    state: string;
    country?: string;
  }) => api.post<{ detail: string }>("/auth/signup", body),
  login: (body: { email: string; password: string; mfa_code?: string }) =>
    api.post<Session>("/auth/login", body),
  logout: () => api.post<{ detail: string }>("/auth/logout"),
  logoutAll: () => api.post<{ detail: string }>("/auth/logout-all"),
  me: () => api.get<User>("/auth/me"),
  verifyEmail: (token: string) => api.post<{ detail: string }>("/auth/verify-email", { token }),
  resendVerification: () => api.post<{ detail: string }>("/auth/resend-verification"),
  // Versão sem sessão: quem não confirmou não consegue entrar, e portanto não
  // alcançaria a rota acima.
  resendVerificationPublic: (email: string) =>
    api.post<{ detail: string }>("/auth/resend-verification-public", { email }),
  forgotPassword: (email: string) => api.post<{ detail: string }>("/auth/forgot-password", { email }),
  resetPassword: (token: string, password: string) =>
    api.post<{ detail: string }>("/auth/reset-password", { token, password }),
  changePassword: (current_password: string, new_password: string) =>
    api.post<{ detail: string }>("/auth/change-password", { current_password, new_password }),
  mfaSetup: () => api.post<{ secret: string; otpauth_uri: string; qr_svg: string }>("/auth/mfa/setup"),
  mfaActivate: (code: string) => api.post<{ backup_codes: string[] }>("/auth/mfa/activate", { code }),
  mfaDisable: (current_password: string) =>
    api.post<{ detail: string }>("/auth/mfa/disable", { current_password, new_password: "" }),
};

export const profile = {
  overview: (signal?: AbortSignal) => api.get<Overview>("/profile/overview", signal),
  get: () => api.get<Profile>("/profile"),
  update: (body: Partial<Profile>) => api.patch<Profile>("/profile", body),
  updateAccount: (body: Partial<Pick<User, "name" | "locale" | "timezone_name" | "theme" | "onboarding_completed">>) =>
    api.patch<User>("/profile/account", body),
  activity: (limit = 30) => api.get(`/profile/activity?limit=${limit}`),
};

export const resumes = {
  list: () => api.get<Resume[]>("/resumes"),
  get: (id: string) => api.get<Resume>(`/resumes/${id}`),
  upload: (file: File) => api.upload<Resume>("/resumes", file),
  /** Chama a IA. É a parte lenta — pode levar de 2 a 15 segundos. */
  parse: (id: string) => api.post<Resume>(`/resumes/${id}/parse`),
  /** Importa as competências REVISADAS. Sem corpo, importa o que a IA leu. */
  apply: (id: string, body?: { tecnologias?: unknown[]; aplicar_perfil?: boolean }) =>
    api.post<{ imported: number; tags: unknown[] }>(`/resumes/${id}/apply`, body ?? {}),
  remove: (id: string) => api.del<void>(`/resumes/${id}`),
};

export const tags = {
  catalog: (q = "", category = "") =>
    api.get<Tag[]>(`/tags?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`),
  mine: () => api.get<UserTag[]>("/tags/mine"),
  add: (body: { tag_id?: string; name?: string; category?: string; proficiency: number; is_target: boolean }) =>
    api.post<UserTag>("/tags/mine", body),
  update: (id: string, body: { proficiency?: number; is_target?: boolean }) =>
    api.patch<UserTag>(`/tags/mine/${id}`, body),
  remove: (id: string) => api.del<void>(`/tags/mine/${id}`),
};

export const roadmap = {
  current: () => api.get<Roadmap>("/roadmap/current"),
  get: (id: string) => api.get<Roadmap>(`/roadmap/${id}`),
  list: () => api.get<{ id: string; title: string; is_primary: boolean }[]>("/roadmap"),
  generate: (body: { objective: string; horizon_weeks: number; weekly_hours: number; context?: string }) =>
    api.post<Roadmap>("/roadmap/generate", body),
  patchNode: (nodeId: string, body: { status?: string; progress_pct?: number; minutes?: number }) =>
    api.patch(`/roadmap/nodes/${nodeId}`, body),
};

export const library = {
  list: (params: { q?: string; kind?: string; language?: string; only_mine?: boolean } = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.kind) query.set("kind", params.kind);
    if (params.language) query.set("language", params.language);
    query.set("only_mine", String(params.only_mine ?? true));
    return api.get<Resource[]>(`/library?${query}`);
  },
  mine: (statusFilter = "") => api.get(`/library/mine?status_filter=${statusFilter}`),
  /**
   * Manda o servidor procurar material novo — no YouTube, num buscador e, se
   * nenhum dos dois achar, na IA. Sem `nodeId` busca pelas tags do perfil.
   *
   * Devolve o que ENTROU nesta chamada, não o catálogo: quem chama recarrega
   * a lista depois. `motivo` vem preenchido quando `novos` é 0, e é a
   * diferença entre "não achamos" e "buscamos há pouco, tente mais tarde".
   */
  curate: (nodeId?: string) =>
    api.post<{ novos: number; tags_buscadas: string[]; motivo: string | null }>(
      nodeId ? `/library/curate?node_id=${nodeId}` : "/library/curate",
      {},
    ),
  setProgress: (
    resourceId: string,
    body: { status: string; progress_pct?: number; rating?: number; minutes_spent?: number },
  ) => api.put(`/library/${resourceId}/progress`, body),
};

export const quizzes = {
  list: () => api.get("/quizzes"),
  get: (id: string) => api.get<Quiz>(`/quizzes/${id}`),
  generate: (body: { tag_ids?: string[]; node_id?: string; question_count?: number; difficulty?: string }) =>
    api.post<Quiz>("/quizzes/generate", body),
  submit: (id: string, answers: Record<string, number>, duration_s = 0) =>
    api.post<QuizResult>(`/quizzes/${id}/submit`, { answers, duration_s }),
  attempts: (id: string) => api.get(`/quizzes/${id}/attempts`),
};

export const english = {
  profile: () => api.get<EnglishProfile>("/english/profile"),
  update: (body: Partial<Pick<EnglishProfile, "enabled" | "target_level" | "daily_goal_min">>) =>
    api.patch<EnglishProfile>("/english/profile", body),
  startAssessment: () => api.post<EnglishAssessment>("/english/assessment"),
  getAssessment: (id: string) => api.get<EnglishAssessment>(`/english/assessment/${id}`),
  answer: (assessmentId: string, itemId: string, answer: number) =>
    api.post<EnglishAnswerResult>(`/english/assessment/${assessmentId}/answer`, {
      item_id: itemId,
      answer,
    }),
  vocab: (dueOnly = false) => api.get(`/english/vocab?due_only=${dueOnly}`),
  reviewVocab: (id: string, quality: number) =>
    api.post(`/english/vocab/${id}/review`, { quality }),
};
