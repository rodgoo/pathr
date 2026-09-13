/**
 * As chamadas da API, tipadas e agrupadas por assunto.
 *
 * Uma função por endpoint em vez de as telas montarem URLs: quando uma rota
 * muda de forma, muda aqui e o TypeScript aponta cada chamador.
 */

import { api } from "./client";
import { esquecerVagas } from "@/lib/vagasGuardadas";
import type {
  Amizades,
  ApiStatusReport,
  DisponibilidadeUsername,
  PessoaCartao,
  Relacao,
  Relato,
  RelatoModeracao,
  StatusRelato,
  TipoRelato,
  City,
  CourseList,
  OwnedCourse,
  JobAnalysis,
  JobList,
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
  PracticeAnswer,
  PracticeAnswerResult,
  PracticeSession,
  SkillBoard,
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
  TagSuggestions,
  User,
  UserTag,
  CodeLanguage,
  Walkthrough,
  WordMeaning,
} from "./types";

/** A stack, o objetivo e a região decidem que vagas aparecem e em que ordem.
 * Mudou algum deles, a lista guardada da tela de Vagas é de outra pessoa. */
function depoisDeMudarOPerfil<T>(resposta: T): T {
  esquecerVagas();
  return resposta;
}

/**
 * Pessoas: o @ de cada um, amizades e sugestões.
 *
 * O @ vai sem o símbolo: o servidor normaliza de qualquer jeito, e mandar
 * limpo evita que "@rodgoo" e "rodgoo" pareçam dois nomes na tela.
 */
/**
 * Relatos para a moderação. A foto vai como ARQUIVO, nunca como endereço: uma
 * URL enviada pelo cliente e mostrada na tela de quem modera seria XSS na
 * conta com mais poder do app.
 */
export const relatos = {
  enviar: (dados: { tipo: TipoRelato; mensagem: string; pagina?: string; foto?: File | null }) => {
    const form = new FormData();
    form.append("tipo", dados.tipo);
    form.append("mensagem", dados.mensagem);
    if (dados.pagina) form.append("pagina", dados.pagina);
    if (dados.foto) form.append("foto", dados.foto);
    return api.form<Relato>("/relatos", form);
  },
  meus: () => api.get<Relato[]>("/relatos/meus"),
  moderacao: (situacao: "abertos" | "todos" | "resolvidos" = "abertos") =>
    api.get<RelatoModeracao[]>(`/relatos/moderacao?situacao=${situacao}`),
  moderar: (id: string, corpo: { status: StatusRelato; moderator_note?: string | null }) =>
    api.patch<Relato>(`/relatos/${encodeURIComponent(id)}`, corpo),
  foto: (id: string) => api.blob(`/relatos/${encodeURIComponent(id)}/foto`),
};

export const social = {
  disponivel: (username: string, nome = "") =>
    api.get<DisponibilidadeUsername>(
      `/social/username/disponivel?username=${encodeURIComponent(username)}&nome=${encodeURIComponent(nome)}`,
    ),
  trocarUsername: (username: string) =>
    api.put<DisponibilidadeUsername>("/social/username", { username }),
  privacidade: () => api.get<{ discoverable: boolean }>("/social/privacidade"),
  gravarPrivacidade: (discoverable: boolean) =>
    api.put<{ discoverable: boolean }>("/social/privacidade", { discoverable }),
  sugestoes: () => api.get<PessoaCartao[]>("/social/pessoas/sugestoes"),
  buscar: (q: string) =>
    api.get<PessoaCartao[]>(`/social/pessoas/busca?q=${encodeURIComponent(q)}`),
  amigos: () => api.get<Amizades>("/social/amigos"),
  convidar: (username: string) =>
    api.post<{ relacao: Relacao }>(`/social/amigos/${encodeURIComponent(username)}`),
  aceitar: (friendshipId: string) =>
    api.post<{ relacao: Relacao }>(`/social/convites/${encodeURIComponent(friendshipId)}/aceitar`),
  /** Recusa, cancela ou desfaz — o servidor sabe qual pelo lado de quem pede. */
  desfazer: (friendshipId: string) =>
    api.del<void>(`/social/convites/${encodeURIComponent(friendshipId)}`),
  avatar: (username: string) =>
    api.blob(`/social/pessoas/${encodeURIComponent(username)}/avatar`),
};

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
    /** Vazio: o servidor escolhe um a partir do nome. */
    username?: string;
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
  // Região, objetivo e senioridade mudam que vagas combinam: a lista guardada
  // da tela de Vagas deixa de valer.
  update: (body: Partial<Profile>) => api.patch<Profile>("/profile", body).then(depoisDeMudarOPerfil),
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
    api.post<{ imported: number; tags: unknown[] }>(`/resumes/${id}/apply`, body ?? {}).then(depoisDeMudarOPerfil),
  remove: (id: string) => api.del<void>(`/resumes/${id}`),
};

export const tags = {
  catalog: (q = "", category = "") =>
    api.get<Tag[]>(`/tags?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`),
  mine: () => api.get<UserTag[]>("/tags/mine"),
  add: (body: { tag_id?: string; name?: string; category?: string; proficiency: number; is_target: boolean }) =>
    api.post<UserTag>("/tags/mine", body).then(depoisDeMudarOPerfil),
  update: (id: string, body: { proficiency?: number; is_target?: boolean }) =>
    api.patch<UserTag>(`/tags/mine/${id}`, body).then(depoisDeMudarOPerfil),
  /** O que aprender a seguir, a partir do objetivo — com o motivo de cada um.
   *
   * `refresh` refaz a lista mesmo dentro da validade: é o botão de quem
   * acabou de mudar o objetivo e não quer esperar o prazo. */
  suggestions: (refresh = false) =>
    api.get<TagSuggestions>(`/tags/suggestions?refresh=${refresh}`),
  remove: (id: string) => api.del<void>(`/tags/mine/${id}`).then(depoisDeMudarOPerfil),
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

/** Cursos com certificado, pelo que a pessoa quer aprender. O catálogo é
 * curado no servidor (services/courses.py) e chega já ordenado. */
export const courses = {
  list: () => api.get<CourseList>("/courses"),
  /** Os certificados marcados como "já possuo". */
  mine: () => api.get<OwnedCourse[]>("/courses/mine"),
  own: (courseId: string) => api.put<OwnedCourse>(`/courses/mine/${encodeURIComponent(courseId)}`, {}),
  disown: (courseId: string) => api.del<void>(`/courses/mine/${encodeURIComponent(courseId)}`),
};

/** Vagas reais de fontes confiáveis (Gupy, Remotive, Adzuna, sites de vaga),
 * e o que falta para cada uma. Ver services/vagas.py. */
export const jobs = {
  list: (
    params: {
      q?: string;
      remotas?: boolean;
      alcance?: "todas" | "nacionais" | "internacionais";
      /** Busca de novo nas fontes em vez de usar o que foi buscado há pouco. */
      atualizar?: boolean;
    } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.remotas) query.set("remotas", "true");
    if (params.alcance && params.alcance !== "todas") query.set("alcance", params.alcance);
    if (params.atualizar) query.set("atualizar", "true");
    return api.get<JobList>(`/vagas?${query}`);
  },
  /** Um dos três: a vaga da listagem, o link de uma vaga ou o texto do anúncio.
   * Chama a IA na primeira vez de cada anúncio — leva alguns segundos. */
  analyze: (body: { vaga_id?: string; url?: string; texto?: string }) =>
    api.post<JobAnalysis>("/vagas/analise", body),
};

/** Cidades do Brasil pelo começo do nome, para o campo de região. */
export const geo = {
  cidades: (q: string) => api.get<City[]>(`/geo/cidades?q=${encodeURIComponent(q)}`),
  /** Sem sessão, para o cadastro. Limitada por IP no servidor. */
  cidadesPublico: (q: string) => api.get<City[]>(`/geo/cidades/publico?q=${encodeURIComponent(q)}`),
};

/** O estado das integrações externas. A chave nunca vem junto. */
export const status = {
  apis: (atualizar = false) => api.get<ApiStatusReport>(`/status/apis?atualizar=${atualizar}`),
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
  /** O que a pessoa errou e ainda não recuperou, SÓ deste idioma. */
  improvements: (language = "en") =>
    api.get<LanguageImprovements>(`/languages/improvements?language=${language}`),
  /** O nível de cada habilidade, com a incerteza, e como foi em cada tópico. */
  skills: (language = "en") => api.get<SkillBoard>(`/languages/skills?language=${language}`),
  /** O treino de hoje, se já começou. Não cria nada. */
  practiceToday: (language = "en") =>
    api.get<PracticeSession | null>(`/languages/practice/today?language=${language}`),
  /** Abre ou retoma o treino de hoje. A primeira abertura gera exercícios. */
  startPractice: (language = "en") =>
    api.post<PracticeSession>(`/languages/practice?language=${language}`),
  /** O treino com os pendentes; prepara os próximos se nenhum estiver pronto. */
  practice: (sessionId: string) => api.get<PracticeSession>(`/languages/practice/${sessionId}`),
  answerPractice: (sessionId: string, itemId: string, answer: PracticeAnswer) =>
    api.post<PracticeAnswerResult>(`/languages/practice/${sessionId}/answer`, {
      item_id: itemId,
      answer,
    }),
  answer: (assessmentId: string, itemId: string, answer: number) =>
    api.post<EnglishAnswerResult>(`/languages/assessment/${assessmentId}/answer`, {
      item_id: itemId,
      answer,
    }),
  /** O significado de uma palavra — e o registro de que ela foi consultada.
   *
   * `context` é a frase em que ela apareceu: "book" num e-mail de reserva não
   * é o "book" de uma estante, e sem a frase volta a acepção mais comum, que
   * é justamente a que a pessoa já conhecia. */
  lookup: (term: string, language = "en", context?: string) =>
    api.post<WordMeaning>("/languages/lookup", { term, language, context }),
  vocab: (language = "en", dueOnly = false) =>
    api.get(`/languages/vocab?language=${language}&due_only=${dueOnly}`),
  reviewVocab: (id: string, quality: number) =>
    api.post(`/languages/vocab/${id}/review`, { quality }),
};

/** Nome antigo do modulo, de quando ele so falava ingles. Mantido para as
 * telas que ainda nao foram renomeadas apontarem para o mesmo lugar. */
export const english = languages;

export const walkthroughs = {
  /** A lista fechada de linguagens e niveis que o gerador aceita. */
  languages: () =>
    api.get<{ languages: CodeLanguage[]; levels: string[] }>("/walkthroughs/languages"),
  list: (language?: string) =>
    api.get<Walkthrough[]>(
      language ? `/walkthroughs?language=${encodeURIComponent(language)}` : "/walkthroughs",
    ),
  get: (id: string) => api.get<Walkthrough>(`/walkthroughs/${encodeURIComponent(id)}`),
  /**
   * Gera um exemplo novo. Leva segundos -- e uma chamada de IA -- e por isso o
   * resultado fica guardado: quem estuda volta ao MESMO exemplo varias vezes, e
   * regerar a cada abertura apagaria o que ela estava construindo sobre ele.
   */
  create: (language: string, topic: string, level: string) =>
    api.post<Walkthrough>("/walkthroughs", { language, topic, level }),
  remove: (id: string) => api.del<void>(`/walkthroughs/${encodeURIComponent(id)}`),
};
