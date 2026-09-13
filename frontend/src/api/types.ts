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
  /** O @ da pessoa, sem o @. É por ele que as outras contas a encontram. */
  username: string;
  /** Modera os relatos. Só decide o que a tela MOSTRA; o acesso é do servidor. */
  is_moderator?: boolean;
  /** Se ha foto. Os bytes vem por GET /profile/avatar. */
  has_avatar: boolean;
}

/** A relação entre quem está logado e a pessoa do cartão. */
export type Relacao = "nenhuma" | "enviado" | "recebido" | "amigos";

/**
 * O que uma conta vê de outra. Nunca e-mail nem nascimento: o servidor não
 * manda, e por isso o tipo não tem onde guardar.
 */
export interface PessoaCartao {
  username: string;
  name: string;
  has_avatar: boolean;
  city: string | null;
  state: string | null;
  objetivo: string | null;
  cargo: string | null;
  senioridade: string | null;
  stack: string[];
  relacao: Relacao;
  /** O convite ou a amizade, para aceitar, recusar ou desfazer. */
  friendship_id: string | null;
  /** Tecnologias do `stack` que quem olha também tem. */
  em_comum?: string[];
  /** Os dois têm exatamente as mesmas tecnologias. */
  mesma_stack?: boolean;
  /** Só entre amigos: os dias seguidos em que os dois estudaram. */
  sequencia?: SequenciaDupla;
}

/** Um aviso de amizade para o pop-up: convite recebido ou convite aceito. */
export interface NovidadeDeAmizade {
  tipo: "convite" | "aceito";
  friendship_id: string;
  quando: string | null;
  pessoa: PessoaCartao;
}

export interface SequenciaDupla {
  atual: number;
  recorde: number;
  /** Quem olha já estudou hoje. */
  hoje_voce: boolean;
  /** O amigo já estudou hoje. */
  hoje_amigo: boolean;
}

export interface Amizades {
  amigos: PessoaCartao[];
  recebidos: PessoaCartao[];
  enviados: PessoaCartao[];
}

export type TipoRelato = "reclamacao" | "sugestao";
export type StatusRelato = "aberto" | "em_analise" | "resolvido";

export interface Relato {
  id: string;
  kind: TipoRelato;
  message: string;
  page: string | null;
  has_attachment: boolean;
  status: StatusRelato;
  moderator_note: string | null;
  created_at: string;
  updated_at: string | null;
  /** Quando o relato foi salvo mas a foto não. */
  aviso?: string;
}

/** Na moderação, com quem relatou. Só a conta moderadora recebe isto. */
export interface RelatoModeracao extends Relato {
  author: { name: string | null; username: string | null; email: string | null };
}

export interface DisponibilidadeUsername {
  username: string;
  disponivel: boolean;
  problema: string | null;
  sugestoes: string[];
}

export interface Session {
  user: User;
  access_token: string;
  expires_in: number;
}

export interface Profile {
  user_id: string;
  city?: string | null;
  /** UF, duas letras. */
  state?: string | null;
  /** Raio das vagas presenciais e híbridas; 0 = só remotas; null = padrão (50 km). */
  job_radius_km?: number | null;
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
/** Uma coisa feita num dia: o que o painel lista ao passar o mouse. */
export interface ActivityItem {
  /** `resource_done`, `quiz_done`, `english_assessment`… */
  kind: string;
  /** Para material: `article`, `video`, `doc`… */
  resource_kind?: string | null;
  title: string;
  minutes: number;
  /** Minutos estimados pelo tamanho do texto, não medidos. */
  estimated?: boolean;
}

export interface ActivityDay {
  date: string;
  minutes: number;
  count: number;
  xp: number;
  items?: ActivityItem[];
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
  /** Onde a pessoa parou. Nulo quando nunca foi marcado. */
  user_position_note: string | null;
  /** A posicao do video em segundos. Nulo para artigo e para o que nunca
   * foi aberto. */
  user_position_seconds: number | null;
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

/** Uma faixa da prova e o ponto do CEFR que ela representa. */
export interface ExamBand {
  rotulo: string;
  cefr: string;
  /** Detalhe da nota ("banda 7.0-8.0"), quando o exame publica faixa. */
  nota: string;
}

export interface Exam {
  id: string;
  nome: string;
  descricao: string;
  faixas: ExamBand[];
}

export interface LanguageCatalogEntry {
  codigo: string;
  nome: string;
  nativo: string;
  exames: Exam[];
}

/**
 * O perfil de UM idioma. Uma pessoa tem uma linha por idioma que estuda.
 *
 * `cefr_level` e a escala interna, a unica em que o app mede. `exam_level` e
 * o mesmo ponto traduzido para a regua escolhida, calculado pelo servidor na
 * leitura — trocar de exame reapresenta o resultado, nao o invalida.
 */
export interface LanguageProfile {
  user_id: string;
  language: string;
  enabled: boolean;
  cefr_level: string | null;
  target_level: string;
  exam: string;
  exam_target: string | null;
  exam_level: string | null;
  target_cefr: string | null;
  sub_scores: Record<string, number>;
  focus_areas: unknown[];
  daily_goal_min: number;
  last_assessment_at: string | null;
}

/** Uma lacuna que a explicacao revelou. Vira item de revisao. */
export interface ExplanationGap {
  conceito: string;
  por_que: string;
}

export interface ExplanationResult {
  id: string;
  concept?: string;
  /** 0..100 — quanto da ideia a explicacao sustenta SOZINHA. */
  score: number;
  feedback: string | null;
  /** O que ficou de pe. So vem na resposta do envio. */
  sustenta?: string[];
  gaps: ExplanationGap[];
  /** Quantas lacunas entraram na fila de revisao (as repetidas nao entram). */
  viraram_revisao?: number;
  created_at?: string;
}

/** Um item do checklist da semana. A ordem da lista é a do método. */
export interface WeeklyItem {
  id: string;
  tipo: "revisao" | "material" | "quiz" | "feynman" | "pratica" | "desafio";
  pilar: string;
  titulo: string;
  detalhe: string;
  minutos: number;
  node_id: string | null;
  modulo: string | null;
  nivel: "iniciante" | "intermediario" | "avancado" | null;
  feito: boolean;
  /** Confirmado por evidência (quiz ou explicação) — não se desmarca. */
  verificado: boolean;
  feito_em: string | null;
}

/** Uma mudança que o ajuste de rota fez, com o motivo em texto. */
export interface RouteChange {
  node_id: string | null;
  titulo: string;
  tipo: "compactar" | "reforcar" | "reagendar";
  motivo: string;
  antes: Record<string, number>;
  depois: Record<string, number>;
}

export interface WeeklyPlan {
  semana: number;
  inicio: string;
  itens: WeeklyItem[];
  resumo: { total: number; feitos: number; minutos: number; minutos_feitos: number };
  orcamento_min: number;
  /** Os ajustes feitos na virada desta semana. Vazio fora da virada. */
  ajustes: RouteChange[];
}

export interface RouteAdjustmentEntry {
  em: string;
  semana: number;
  mudancas: RouteChange[];
}

/** Uma chave de acesso cadastrada. Só metadados: a chave em si nunca sai do aparelho. */
export interface Passkey {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  /** Sincronizada entre aparelhos (iCloud, Google) — sobrevive à troca de celular. */
  backed_up: boolean;
}

/** As opções de uma cerimônia WebAuthn, no JSON padrão do @simplewebauthn/browser. */
export interface PasskeyOptions {
  challenge_id: string;
  options: Record<string, unknown>;
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

/** O artigo extraido pelo servidor, pronto para renderizar.
 *
 * `status`: "ok" traz o html; "failed" traz o motivo; "pending" nunca foi
 * buscado. A tela mostra os tres de forma diferente -- nunca um quadro vazio.
 */
export interface ReaderContent {
  id: string;
  title: string;
  url: string;
  provider: string | null;
  status: "ok" | "failed" | "pending";
  html: string | null;
  words: number | null;
  error: string | null;
}

export interface EnglishAssessment {
  id: string;
  /** O idioma medido. A tela usa para escolher a voz do listening. */
  language: string;
  status: string;
  item_count: number;
  answered_count: number;
  correct_count: number;
  cefr_result: string | null;
  items: EnglishItem[];
}

/** Um erro do nivelamento que ainda não foi recuperado. `front` é o enunciado
 * que a pessoa errou; `back`, a resposta certa com a explicação. */
export interface LanguageImprovement {
  id: string;
  front: string;
  back: string;
  due_at: string;
  lapses: number;
  repetitions: number;
  skill?: string | null;
  topic?: string | null;
}

export interface LanguageImprovements {
  items: LanguageImprovement[];
  /** Quantos já venceram. É o número que a tela mostra. */
  due_count: number;
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

/**
 * Um exemplo de codigo com o traco de execucao linha a linha.
 *
 * `steps` pode vir VAZIO de proposito: o servidor recusa traco que nao bate
 * com o codigo (services/code_lab.conferir), e o exemplo continua valendo como
 * codigo comentado. A tela precisa dizer isso em vez de mostrar um passo a
 * passo inventado.
 */
export interface Walkthrough {
  id: string;
  language: string;
  language_label: string;
  /** Identificador de sintaxe para o realce. */
  highlight: string;
  topic: string;
  level: string;
  title: string;
  summary: string;
  code: string;
  /** O codigo ja quebrado como a tela numera: indice 0 = linha 1. */
  lines: string[];
  steps: WalkthroughStep[];
  concepts: string[];
  created_at: string | null;
}

export interface WalkthroughStep {
  /** 1-based, para casar com a numeracao que a pessoa ve ao lado do codigo. */
  linha: number;
  acao: string;
  estado: { nome: string; valor: string }[];
  /** So o que ESTA linha imprimiu. O painel acumula. */
  saida: string;
}

export interface CodeLanguage {
  id: string;
  rotulo: string;
  realce: string;
}

/**
 * O que uma palavra consultada quer dizer.
 *
 * Consultar não é só ver a tradução: o termo entra no baralho de vocabulário
 * vencendo hoje, e quem já o tinha leva o cartão de volta ao início. Por isso
 * a resposta traz `card` — é a prova de que o app registrou a lacuna, e não
 * só respondeu à pergunta.
 */
export interface WordMeaning {
  term: string;
  translation: string | null;
  synonyms: string[];
  definition: string | null;
  example: string | null;
  phonetic: string | null;
  cefr_band: string;
  card: { id: string; due_at: string } | null;
}

/**
 * Uma tecnologia sugerida a partir do objetivo.
 *
 * `demand` é o quanto o mercado usa aquilo — `consolidada` (está em vaga há
 * anos), `em alta` (crescendo agora) ou `aposta` (vale conhecer, ainda não é
 * exigida). São três respostas e não uma nota porque "76% de relevância" seria
 * um número inventado com cara de medido.
 */
export interface TagSuggestion {
  name: string;
  category: string;
  reason: string;
  demand: string;
}

export interface TagSuggestions {
  /** O objetivo que gerou a lista. `null` quando ainda não há objetivo. */
  objetivo: string | null;
  sugestoes: TagSuggestion[];
  geradas_em: string | null;
}

/* ------------------------------------------------------------------------
 * Nivel por habilidade e treino diario de idioma
 * --------------------------------------------------------------------- */

/** Como a pessoa foi num topico dentro de uma habilidade. */
export interface SkillTopic {
  topic: string;
  answered: number;
  correct: number;
  /** De 0 a 100, suavizada: 1 de 1 nao vira 100. */
  score: number;
  status: "reforcar" | "progredindo" | "dominado" | "poucos_dados";
  last_seen: string | null;
}

export type SkillConfidence = "alta" | "media" | "inicial" | "sem_dados";

export interface SkillLevel {
  skill: string;
  /** Nivel CEFR estimado, ou null sem nenhuma resposta naquela habilidade. */
  level: string | null;
  theta: number;
  /** Quanto ja andou dentro da banda, de 0 a 1. */
  progress_in_band: number;
  uncertainty: number;
  confidence: SkillConfidence;
  answered: number;
  topics: SkillTopic[];
}

export interface SkillBoard {
  overall: {
    level: string | null;
    theta: number;
    progress_in_band: number;
    uncertainty: number;
    confidence: SkillConfidence;
    answered: number;
  };
  skills: SkillLevel[];
}

export type PracticeType =
  | "mcq"
  | "gap"
  | "reorder"
  | "match"
  | "listening"
  | "dictation"
  | "image"
  | "speaking";

/** O que a tela mostra de um exercicio. O gabarito nunca vem junto. */
export interface PracticePayload {
  enunciado?: string;
  alternativas?: string[];
  frase?: string;
  emoji?: string;
  audio?: string;
  dialogo?: boolean;
  pecas?: string[];
  traducao?: string;
  esquerda?: string[];
  direita?: string[];
  texto?: string;
}

export interface PracticeItem {
  id: string;
  type: PracticeType;
  skill: string;
  topic: string | null;
  band: string | null;
  origin: "revisao" | "reforco" | "novo";
  payload: PracticePayload;
}

export interface PracticeSummary {
  correct: number;
  answered: number;
  reviewed: number;
  recovered: number;
  levels: { skill: string; before: string | null; after: string; delta: number | null }[];
  topics: { skill: string; topic: string; answered: number; correct: number }[];
}

export interface PracticeSession {
  id: string;
  language: string;
  practice_day: string;
  status: "active" | "done";
  total: number;
  answered: number;
  correct: number;
  /** Ainda ha exercicios sendo preparados. */
  generating: boolean;
  /** So os pendentes, na ordem do treino. */
  items: PracticeItem[];
  summary: PracticeSummary | null;
}

export type PracticeAnswer =
  | { indice: number }
  | { tokens: string[] }
  | { pares: Record<string, number> }
  | { texto: string };

export type ApiIntegrationState = "ok" | "degradada" | "erro" | "nao_configurada" | "sem_verificacao";

export interface ApiIntegration {
  id: string;
  nome: string;
  categoria: string;
  /** O que a integração sustenta no app. */
  para_que: string;
  configurada: boolean;
  estado: ApiIntegrationState;
  detalhe: string;
  latencia_ms: number | null;
  uso: {
    hoje?: { requisicoes: number; tokens: number };
    usados?: number;
    limite?: number;
    restantes?: number;
    unidade?: string;
  } | null;
  /** Só nas IAs. */
  modelo?: string;
  ultimo_uso_em?: string;
}

export interface ApiStatusReport {
  itens: ApiIntegration[];
  resumo: Partial<Record<ApiIntegrationState, number>>;
  verificado_em: string;
  /** Segundos até o servidor aceitar outra verificação. */
  pode_atualizar_em_s: number;
}

/** Da barra de chama: de "pegando fogo" (muito procurado) a "chama apagada" (o básico). */
export type DemandBand = "pegando_fogo" | "em_alta" | "procurado" | "comum" | "basico";

export interface Course {
  id: string;
  titulo: string;
  emissor: string;
  url: string;
  tags: string[];
  nivel: "iniciante" | "intermediario" | "avancado";
  idioma: "pt" | "en";
  horas: number | null;
  /** O CERTIFICADO, não só as aulas. */
  certificado: { gratuito: boolean; detalhe: string };
  demanda: { nota: number; faixa: DemandBand; rotulo: string; motivo: string | null };
  /** Por que o curso apareceu: qual configuração pediu qual tag. */
  motivos: { tipo: "meta" | "quero_aprender" | "roadmap" | "objetivo"; tag: string }[];
  relevancia: number;
  /** A pessoa marcou "já possuo" este certificado. */
  possuo?: boolean;
}

/** Um certificado que a pessoa já possui, como aparece em Perfil e tags. */
export interface OwnedCourse {
  id: string;
  titulo: string;
  emissor: string;
  url: string;
  tags: string[];
  gratuito: boolean;
  possuido_em: string | null;
}

export interface CourseList {
  /** Já ordenada: todo gratuito antes de qualquer pago. */
  cursos: Course[];
  /** "AAAA-MM" em que preços e gratuidade foram conferidos. */
  conferido_em: string;
  /** Se a pessoa disse o que quer aprender — separa os dois vazios. */
  tem_pedido: boolean;
}

export interface JobCompatibility {
  /** 0 a 100; null quando o anúncio não foi lido (resultado de busca). */
  nota: number | null;
  tem: string[];
  parcial: string[];
  falta: string[];
}

/** O inglês que a vaga pede contra o nível medido no módulo de Idiomas. */
export interface JobEnglish {
  exigido: string | null;
  seu: string | null;
  /** null quando a vaga não pede inglês; sem_nivel quando não há nivelamento. */
  situacao: "tem" | "parcial" | "falta" | "sem_nivel" | null;
}

export interface Job {
  id: string;
  titulo: string;
  empresa: string | null;
  url: string;
  fonte: string;
  local: string | null;
  remota: boolean | null;
  publicada_ha_dias: number | null;
  nivel: "junior" | "pleno" | "senior" | null;
  na_sua_regiao: boolean;
  /** Veio de um buscador: só o link, sem o anúncio lido. */
  so_link: boolean;
  /** Veio só um trecho do anúncio (Adzuna): sem nota até a análise ler a página. */
  so_trecho: boolean;
  /** Contratação de fora (Remotive, ou vaga de buscador anunciada em inglês). */
  internacional: boolean;
  ingles: JobEnglish;
  resumo: string | null;
  compatibilidade: JobCompatibility;
  /** Por que a vaga tem a cara da pessoa: a stack que ela cita e o objetivo. */
  afinidade?: { stack_em_comum: string[]; objetivo: boolean };
  /** 0 a 100: o quanto a vaga tem a cara da pessoa. A lista vem nesta ordem. */
  combina?: number;
  /** Em linha reta, da cidade do perfil. null para remota ou local desconhecido. */
  distancia_km?: number | null;
  /** O anúncio em partes, lido dos títulos de seção. null quando não foi lido. */
  sobre?: JobAbout | null;
  /** O que falta para a vaga, já calculado — obrigatórias primeiro. */
  lacunas?: JobListGap[];
}

export interface JobAbout {
  apresentacao: string | null;
  faz: string[];
  pede: string[];
  diferenciais: string[];
}

export interface JobListGap {
  nome: string;
  slug: string;
  obrigatorio: boolean;
  situacao: "falta" | "parcial" | "sem_nivel";
  tag_id: string | null;
  user_tag_id: string | null;
  e_meta: boolean;
  no_roadmap: boolean;
  idioma?: boolean;
}

export interface JobCourse {
  id: string;
  titulo: string;
  emissor: string;
  url: string;
  gratuito: boolean;
}

export interface City {
  ibge: string;
  nome: string;
  uf: string;
  capital: boolean;
}

export type JobSourceState = "ok" | "erro" | "sem_chave";

export interface JobList {
  termos: string[];
  vagas: Job[];
  /** Os cursos de cada lacuna, por slug — uma lista por tecnologia, não por vaga. */
  cursos?: Record<string, JobCourse[]>;
  /** A região usada no filtro; null sem cidade nem UF no perfil. */
  regiao?: { cidade: string | null; uf: string | null; raio_km: number } | null;
  /** Quando esta lista foi montada (ISO). */
  buscado_em?: string;
  fontes: Partial<Record<"gupy" | "remotive" | "adzuna" | "busca", JobSourceState>>;
  /** Sem competências nem objetivo: não há por onde buscar. */
  sem_perfil: boolean;
  /** O CEFR do módulo de Idiomas, ou null sem nivelamento. */
  nivel_ingles?: string | null;
}

export interface JobRequirement {
  nome: string;
  obrigatorio: boolean;
  situacao: "tem" | "parcial" | "falta" | "desconhecido" | "sem_nivel";
  tag_id: string | null;
  user_tag_id: string | null;
  e_meta: boolean;
}

export interface JobGap extends JobRequirement {
  no_roadmap: boolean;
  /** A lacuna é o inglês: o caminho passa pelo módulo de Idiomas. */
  idioma?: boolean;
  cursos: { id: string; titulo: string; emissor: string; url: string; gratuito: boolean }[];
}

export interface JobAnalysis {
  titulo: string;
  empresa: string | null;
  senioridade: string | null;
  resumo: string | null;
  url: string | null;
  usou_ia: boolean;
  nota: number | null;
  requisitos: JobRequirement[];
  /** Obrigatórias primeiro. */
  lacunas: JobGap[];
  ingles: JobEnglish;
}

export interface PracticeAnswerResult {
  is_correct: boolean;
  /** Fala sem microfone: nao conta como erro. */
  skipped: boolean;
  correct_answer: string | Record<string, number> | null;
  detail: { semelhanca?: number; faltaram?: string[]; acentos?: boolean; certos?: number; total?: number } | null;
  explanation: string | null;
  /** O que aconteceu com o ponto de melhora. */
  improvement: "novo_ponto" | "subiu" | "volta_hoje" | null;
  session: PracticeSession;
}
