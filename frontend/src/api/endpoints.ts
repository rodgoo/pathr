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
  ExplanationResult,
  RouteAdjustmentEntry,
  RouteChange,
  WeeklyItem,
  WeeklyPlan,
  LanguageCatalogEntry,
  LanguageImprovements,
  LanguageProfile,
  Overview,
  Passkey,
  PasskeyOptions,
  Profile,
  Quiz,
  ReaderContent,
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

/**
 * Chave de acesso. As opções vêm do servidor com um `challenge_id`, o
 * navegador faz a cerimônia com o aparelho, e a resposta volta para conferir.
 * A entrada devolve a MESMA sessão do login por senha.
 */
export const passkeys = {
  list: () => api.get<Passkey[]>("/auth/passkeys"),
  registerOptions: () => api.post<PasskeyOptions>("/auth/passkeys/register/options"),
  registerVerify: (challenge_id: string, credential: unknown, name?: string) =>
    api.post<Passkey>("/auth/passkeys/register/verify", { challenge_id, credential, name }),
  remove: (id: string) => api.del<void>(`/auth/passkeys/${id}`),
  loginOptions: () => api.post<PasskeyOptions>("/auth/passkeys/login/options"),
  loginVerify: (challenge_id: string, credential: unknown) =>
    api.post<Session>("/auth/passkeys/login/verify", { challenge_id, credential }),
};

export const profile = {
  overview: (signal?: AbortSignal) => api.get<Overview>("/profile/overview", signal),
  get: () => api.get<Profile>("/profile"),
  update: (body: Partial<Profile>) => api.patch<Profile>("/profile", body),
  updateAccount: (body: Partial<Pick<User, "name" | "locale" | "timezone_name" | "theme" | "onboarding_completed">>) =>
    api.patch<User>("/profile/account", body),
  activity: (limit = 30) => api.get(`/profile/activity?limit=${limit}`),
  /** Tudo que o app guarda sobre a pessoa. O navegador monta o arquivo. */
  exportData: () => api.get<Record<string, unknown>>("/profile/export"),
  /** Apaga a conta e tudo que pende dela. Sem carencia. */
  deleteAccount: () => api.del<void>("/profile/account"),
  /** Os bytes da foto de perfil de quem esta logado. */
  avatar: () => api.blob("/profile/avatar"),
  uploadAvatar: (file: File) => api.upload<{ has_avatar: boolean }>("/profile/avatar", file),
  removeAvatar: () => api.del<void>("/profile/avatar"),
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
  /**
   * Concluir ou reabrir um modulo. Vai para a fila quando nao ha rede: marcar
   * um modulo no metro e o uso offline mais comum do app, e o PATCH e
   * idempotente — mandar duas vezes tem o mesmo efeito de mandar uma.
   */
  patchNode: (nodeId: string, body: { status?: string; progress_pct?: number; minutes?: number }) =>
    api.patch(`/roadmap/nodes/${nodeId}`, body, {}),
  /** O rascunho da atividade pratica. Mora no servidor: preso a um navegador,
   * a solucao escrita do zero se perdia ao trocar de maquina. */
  draft: (nodeId: string) =>
    api.get<{ content: string; updated_at: string | null }>(`/roadmap/nodes/${nodeId}/draft`),
  /** Sem rede o rascunho fica na fila. Perder a solucao escrita do zero por
   * causa de um tunel e o pior desfecho possivel desta tela. */
  saveDraft: (nodeId: string, content: string) =>
    api.put<{ content: string; updated_at: string }>(
      `/roadmap/nodes/${nodeId}/draft`,
      { content },
      { optimistic: () => ({ content, updated_at: new Date().toISOString() }) },
    ),
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
  /** O artigo extraido, para ler dentro do PathR. Ver services/reader.py. */
  reader: (resourceId: string) =>
    api.get<ReaderContent>(`/library/${resourceId}/reader`),
  setProgress: (
    resourceId: string,
    body: {
      status: string;
      progress_pct?: number;
      rating?: number;
      minutes_spent?: number;
      /** Onde parou: "23:10", "capitulo 4". E o que permite retomar. */
      position_note?: string | null;
      /** A posicao do video em segundos, mandada pelo player. */
      position_seconds?: number | null;
    },
    /** Enfileiravel: marcar onde parou num video e anotar progresso sao as
     * duas acoes que mais acontecem longe de uma rede boa. */
  ) => api.put(`/library/${resourceId}/progress`, body, {}),
};

export const plan = {
  /** O checklist da semana. Na virada, o servidor ajusta a rota antes de montá-lo. */
  week: () => api.get<WeeklyPlan>("/plan/week"),
  mark: (itemId: string, feito: boolean) =>
    api.patch<{ item: WeeklyItem; resumo: WeeklyPlan["resumo"] }>(
      `/plan/week/items/${encodeURIComponent(itemId)}`,
      { feito },
    ),
  /** Remonta com o nível de agora, mantendo o que já foi feito. */
  refresh: () => api.post<WeeklyPlan>("/plan/week/refresh"),
  adjust: (preview = false) =>
    api.post<{ semana: number; mudancas: RouteChange[]; aplicado: boolean }>(
      `/plan/adjust?preview=${preview}`,
    ),
  adjustments: () => api.get<RouteAdjustmentEntry[]>("/plan/adjustments"),
};

export const explanations = {
  /**
   * Envia a explicacao pelo metodo Feynman e recebe a correcao.
   *
   * O retorno nao traz uma versao melhorada do texto de proposito: ler a
   * explicacao pronta faz a pessoa concordar e voltar a achar que entendeu,
   * que e a ilusao que o exercicio existe para quebrar. Vem a nota, o que se
   * sustentou e as lacunas -- e cada lacuna ja entrou na fila de revisao.
   */
  submit: (body: { concept: string; content: string; node_id?: string }) =>
    api.post<ExplanationResult>("/explanations", body),
  list: (nodeId?: string) =>
    api.get<ExplanationResult[]>(nodeId ? `/explanations?node_id=${nodeId}` : "/explanations"),
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

export const languages = {
  /** Idiomas e as provas de cada um, com a equivalencia em CEFR. Vem do
   * servidor: e a MESMA tabela que converte a meta, e uma copia no front
   * divergiria na primeira correcao feita so de um lado. */
  catalog: () => api.get<LanguageCatalogEntry[]>("/languages/catalog"),
  /** Todos os idiomas que a pessoa estuda, de uma vez. */
  profiles: () => api.get<LanguageProfile[]>("/languages/profiles"),
  profile: (language = "en") =>
    api.get<LanguageProfile>(`/languages/profile?language=${language}`),
  update: (
    language: string,
    body: Partial<
      Pick<
        LanguageProfile,
        "enabled" | "target_level" | "daily_goal_min" | "exam" | "exam_target"
      >
    >,
  ) => api.patch<LanguageProfile>(`/languages/profile?language=${language}`, body),
  startAssessment: (language = "en") =>
    api.post<EnglishAssessment>(`/languages/assessment?language=${language}`),
  getAssessment: (id: string) => api.get<EnglishAssessment>(`/languages/assessment/${id}`),
  /** O nivelamento em andamento, ou `null`. É o que permite retomar depois de
   * um F5 ou de uma ida a outra tela. */
  activeAssessment: (language = "en") =>
    api.get<EnglishAssessment | null>(`/languages/assessment/active?language=${language}`),
  /** O que a pessoa errou e ainda não recuperou. */
  improvements: () => api.get<LanguageImprovements>("/languages/improvements"),
  answer: (assessmentId: string, itemId: string, answer: number) =>
    api.post<EnglishAnswerResult>(`/languages/assessment/${assessmentId}/answer`, {
      item_id: itemId,
      answer,
    }),
  vocab: (language = "en", dueOnly = false) =>
    api.get(`/languages/vocab?language=${language}&due_only=${dueOnly}`),
  reviewVocab: (id: string, quality: number) =>
    api.post(`/languages/vocab/${id}/review`, { quality }),
};

/** Nome antigo do modulo, de quando ele so falava ingles. Mantido para as
 * telas que ainda nao foram renomeadas apontarem para o mesmo lugar. */
export const english = languages;
