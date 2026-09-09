"""Schema do PathR.

Estas classes SQLModel existem SÓ para descrever o schema ao Alembic — em
runtime os routers falam com o Postgres via `supabase-py` (PostgREST, ver
app/database.py), não por sessão SQLAlchemy. Por isso não há `Relationship()`
aqui, e a semântica de cascata é expressa em FKs reais com ON DELETE CASCADE.

O PathR tem projeto Supabase PRÓPRIO — nada aqui divide banco com outro app.

TODA tabela leva o prefixo `pathr_` mesmo assim, e a razão mudou: não é mais
evitar colisão, é evitar `user`. Num banco só do PathR os nomes estariam
livres, mas `user` é palavra reservada no Postgres — uma tabela com esse nome
precisa de aspas em toda consulta escrita à mão e é uma armadilha conhecida.
Prefixar UMA tabela e deixar as outras 27 sem prefixo seria pior: a exceção é
que se esquece. O prefixo uniforme também mantém o filtro do Alembic
(alembic/env.py) simples e à prova de alguém apontar o `DATABASE_URL` para o
banco errado por engano.

Nenhuma migration rodou ainda, então tirar o prefixo continua barato caso a
preferência mude — é renomear aqui e nas chamadas `.table("pathr_...")` dos
routers.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Column, Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_array() -> Column:
    """uuid[] nativo do Postgres — usado onde a lista de tags/dependências é
    consultada com operadores de array (`&&`, `@>`) em vez de uma tabela de
    junção. Junção existe onde a relação carrega dados próprios (ordem,
    curadoria); array existe onde é só um conjunto de rótulos."""
    return Column(ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default="{}")


def _fk(target: str, *, index: bool = True, nullable: bool = False) -> Column:
    """FK uuid com ON DELETE CASCADE — apagar a conta apaga tudo que é dela."""
    return Column(
        PGUUID(as_uuid=True),
        sa.ForeignKey(target, ondelete="CASCADE"),
        nullable=nullable,
        index=index,
    )


def _jsonb(default: str = "{}") -> Column:
    return Column(JSONB, nullable=False, server_default=default)


# ---------------------------------------------------------------------------
# Identidade e sessão
# ---------------------------------------------------------------------------


class PathrUser(SQLModel, table=True):
    __tablename__ = "pathr_user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    password_hash: str  # Argon2id
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    # -- MFA (TOTP, RFC 6238). Mesmo desenho do Notter: o segredo só sai de
    # `pending` quando o usuário confirma um código, então um segredo nunca
    # confirmado jamais passa a valer para autenticar.
    mfa_enabled: bool = Field(default=False)
    mfa_secret_encrypted: Optional[str] = Field(default=None)
    mfa_pending_secret_encrypted: Optional[str] = Field(default=None)

    # -- Rate limiting / lockout (bloqueio de 15 min após 5 falhas)
    failed_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))

    email_verified_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))

    # -- Preferências
    locale: str = Field(default="pt-BR")
    timezone_name: str = Field(default="America/Sao_Paulo")
    theme: str = Field(default="system")  # 'light' | 'dark' | 'system'
    onboarding_completed: bool = Field(default=False)


class PathrRefreshToken(SQLModel, table=True):
    __tablename__ = "pathr_refresh_token"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    # Só o hash — um dump do banco não deve render sessões vivas.
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_type=sa.DateTime(timezone=True))
    revoked_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    # Rotação: cada uso emite um token novo e aponta para o anterior. Se um
    # token JÁ rotacionado reaparecer, é sinal de roubo — a cadeia inteira é
    # revogada (detecção de replay).
    rotated_from: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    user_agent: Optional[str] = Field(default=None)
    ip: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrMfaBackupCode(SQLModel, table=True):
    __tablename__ = "pathr_mfa_backup_code"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    code_hash: str  # Argon2id, uso único
    used_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrEmailToken(SQLModel, table=True):
    """Verificação de e-mail e reset de senha na mesma tabela, separados por
    `purpose` — os dois têm exatamente o mesmo ciclo de vida (token de uso
    único, com expiração, atrelado a um usuário)."""

    __tablename__ = "pathr_email_token"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    purpose: str = Field(index=True)  # 'verify_email' | 'reset_password'
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_type=sa.DateTime(timezone=True))
    used_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrSecurityEvent(SQLModel, table=True):
    """Trilha de auditoria. NUNCA grava senha, código TOTP ou token em texto."""

    __tablename__ = "pathr_security_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    event_type: str = Field(index=True)  # signup, login_ok, login_fail, mfa_fail, ...
    ip: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True), index=True)


# ---------------------------------------------------------------------------
# Perfil de estudo e currículo
# ---------------------------------------------------------------------------


class PathrProfile(SQLModel, table=True):
    """1:1 com o usuário. Separado de PathrUser de propósito: aqui mora o que
    a IA lê e reescreve (objetivo, senioridade, disponibilidade); lá mora o
    que autentica. Um bug no parser de currículo não deve poder tocar em
    password_hash."""

    __tablename__ = "pathr_profile"

    user_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    # Quem a pessoa é, perguntado no cadastro. Fica aqui e não em PathrUser
    # porque não autentica nada: é dado pessoal, do mesmo tipo do resto deste
    # arquivo. A data é `date` e não `datetime` de propósito — nascimento não
    # tem hora, e guardar uma inventaria fuso onde não existe.
    birth_date: Optional[date] = Field(default=None, sa_type=sa.Date)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)  # UF, duas letras no Brasil
    country: str = Field(default="BR")  # ISO 3166-1 alfa-2

    headline: Optional[str] = Field(default=None)
    current_role: Optional[str] = Field(default=None)
    target_role: Optional[str] = Field(default=None)
    # estagio|junior|pleno|senior|especialista|lideranca
    seniority: Optional[str] = Field(default=None)
    years_experience: Optional[float] = Field(default=None)
    weekly_hours: int = Field(default=8)  # alimenta o dimensionamento do roadmap
    learning_style: Optional[str] = Field(default=None)  # video|texto|pratica|misto
    goals: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    bio: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    github_url: Optional[str] = Field(default=None)
    # Quais e-mails a pessoa aceita receber. JSONB e não cinco colunas
    # booleanas porque a lista de avisos muda com o produto, e cada aviso novo
    # custaria uma migration mais um deploy coordenado com o frontend. As
    # chaves válidas vivem em routers/profile.py (AVISOS); o que não estiver lá
    # é ignorado na escrita, então remover um aviso não deixa lixo para trás.
    notifications: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrResume(SQLModel, table=True):
    __tablename__ = "pathr_resume"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    filename: str
    mime_type: str
    size_bytes: int
    # SHA-256 do arquivo: reenviar o mesmo currículo não gasta uma chamada de
    # IA nem duplica linha — reaproveita o `parsed` do envio anterior.
    content_hash: str = Field(index=True)
    storage_path: Optional[str] = Field(default=None)  # Supabase Storage
    raw_text: Optional[str] = Field(default=None)
    parsed: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    status: str = Field(default="pending")  # pending|parsing|parsed|failed
    error: Optional[str] = Field(default=None)
    is_primary: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    parsed_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Taxonomia de tecnologia (catálogo global) e domínio do usuário
# ---------------------------------------------------------------------------


class PathrTag(SQLModel, table=True):
    """Catálogo GLOBAL de assuntos (não pertence a um usuário). Populado por
    seed (services/tag_seed.py) e ampliável pela IA quando um currículo cita
    algo fora do catálogo."""

    __tablename__ = "pathr_tag"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str = Field(unique=True, index=True)  # 'python', 'react', 'postgres'
    name: str
    category: str = Field(index=True)
    # categoria ∈ linguagem | framework | banco | cloud | devops | dados | ia |
    #             arquitetura | testes | seguranca | mobile | frontend |
    #             backend | ferramenta | metodologia | soft-skill | idioma
    parent_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    description: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None)  # hex; default deriva da categoria
    icon: Optional[str] = Field(default=None)  # slug simple-icons
    aliases: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    popularity: int = Field(default=0)  # ordena o autocomplete
    # Quando esta tag foi buscada por material pela última vez. NULL = nunca.
    # A cota da YouTube Data API dá ~100 buscas por dia para o app inteiro, e
    # a curadoria é global (uma tag serve todos os usuários) — este carimbo é
    # o que impede dois usuários no mesmo módulo de gastarem duas buscas pelo
    # mesmo resultado. Ver services/resource_search.py.
    curated_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True), index=True
    )
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrUserTag(SQLModel, table=True):
    """O que o usuário sabe / quer aprender, e quão bem."""

    __tablename__ = "pathr_user_tag"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    tag_id: uuid.UUID = Field(sa_column=_fk("pathr_tag.id"))
    source: str = Field(default="manual")  # cv | manual | quiz | roadmap
    proficiency: int = Field(default=0)  # 0..5 (0 = quero aprender)
    # 0..1 — quanto o sistema confia nessa nota. Vinda do currículo entra
    # baixa (o CV diz o que a pessoa escreveu); um quiz respondido a sobe.
    confidence: float = Field(default=0.5)
    is_target: bool = Field(default=False)  # marcado como meta de estudo
    last_assessed_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    __table_args__ = (sa.UniqueConstraint("user_id", "tag_id", name="uq_pathr_user_tag"),)


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------


class PathrRoadmap(SQLModel, table=True):
    __tablename__ = "pathr_roadmap"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    title: str
    goal: str  # objetivo em texto livre do usuário
    target_role: Optional[str] = Field(default=None)
    horizon_weeks: int = Field(default=12)
    weekly_hours: int = Field(default=8)
    status: str = Field(default="active")  # draft|active|paused|done|archived
    is_primary: bool = Field(default=False)
    generated_by: Optional[str] = Field(default=None)  # id do modelo que gerou
    summary: Optional[str] = Field(default=None)
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrRoadmapNode(SQLModel, table=True):
    """Nó da trilha. `parent_id` dá a hierarquia (fase → habilidade → tarefa);
    `depends_on` dá o grafo de pré-requisitos, que é o que trava/destrava um
    nó — as duas coisas são diferentes e por isso não compartilham campo."""

    __tablename__ = "pathr_roadmap_node"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    roadmap_id: uuid.UUID = Field(sa_column=_fk("pathr_roadmap.id"))
    parent_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    title: str
    description: Optional[str] = Field(default=None)
    kind: str = Field(default="skill")  # phase|skill|project|checkpoint|reading
    tag_ids: list[uuid.UUID] = Field(default_factory=list, sa_column=_uuid_array())
    depends_on: list[uuid.UUID] = Field(default_factory=list, sa_column=_uuid_array())
    order_index: int = Field(default=0)
    level: Optional[str] = Field(default=None)  # iniciante|intermediario|avancado
    estimated_hours: float = Field(default=0)
    week_start: Optional[int] = Field(default=None)
    week_end: Optional[int] = Field(default=None)
    status: str = Field(default="todo")  # locked|todo|doing|done|skipped
    progress_pct: int = Field(default=0)
    objectives: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    completed_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Biblioteca de conteúdo
# ---------------------------------------------------------------------------


class PathrResource(SQLModel, table=True):
    """Catálogo de conteúdo (vídeo, artigo, doc, curso...). Compartilhado
    entre usuários: `url` é único, então o mesmo vídeo descoberto por dois
    roadmaps é uma linha só, e a curadoria/qualidade acumula."""

    __tablename__ = "pathr_resource"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    kind: str = Field(index=True)  # video|article|course|doc|book|podcast|repo|exercise
    title: str
    url: str = Field(unique=True, index=True)
    provider: Optional[str] = Field(default=None)  # youtube|devto|medium|docs|github|...
    author: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    thumbnail_url: Optional[str] = Field(default=None)
    duration_min: Optional[int] = Field(default=None)
    language: str = Field(default="pt")  # pt|en|es
    level: Optional[str] = Field(default=None)  # iniciante|intermediario|avancado
    is_free: bool = Field(default=True)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, sa_column=_uuid_array())
    # 0..100, heurística de curadoria (fonte, engajamento, atualidade) — ordena
    # a busca e evita empurrar tutorial de 2015 sobre framework que mudou.
    quality_score: int = Field(default=50)
    published_at: Optional[date] = Field(default=None, sa_type=sa.Date())
    added_by: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrUserResource(SQLModel, table=True):
    __tablename__ = "pathr_user_resource"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    resource_id: uuid.UUID = Field(sa_column=_fk("pathr_resource.id"))
    status: str = Field(default="saved")  # saved|in_progress|done|dismissed
    progress_pct: int = Field(default=0)
    rating: Optional[int] = Field(default=None)  # 1..5
    notes: Optional[str] = Field(default=None)
    minutes_spent: int = Field(default=0)
    completed_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    __table_args__ = (sa.UniqueConstraint("user_id", "resource_id", name="uq_pathr_user_resource"),)


class PathrNodeResource(SQLModel, table=True):
    """Curadoria: quais recursos o roadmap indicou para um nó, e em que ordem.
    Tabela de junção (e não um array em PathrRoadmapNode) porque a relação
    carrega dado próprio — ordem e motivo da indicação."""

    __tablename__ = "pathr_node_resource"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    node_id: uuid.UUID = Field(sa_column=_fk("pathr_roadmap_node.id"))
    resource_id: uuid.UUID = Field(sa_column=_fk("pathr_resource.id"))
    order_index: int = Field(default=0)
    reason: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Quiz, atividades e repetição espaçada
# ---------------------------------------------------------------------------


class PathrQuiz(SQLModel, table=True):
    __tablename__ = "pathr_quiz"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    title: str
    kind: str = Field(default="practice")  # diagnostic|practice|exam|code|flashcard
    node_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, sa_column=_uuid_array())
    difficulty: str = Field(default="medio")  # facil|medio|dificil|adaptativo
    question_count: int = Field(default=10)
    time_limit_s: Optional[int] = Field(default=None)
    generated_by: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrQuestion(SQLModel, table=True):
    __tablename__ = "pathr_question"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(sa_column=_fk("pathr_quiz.id"))
    type: str = Field(default="single")  # single|multiple|code|open|fill|order|truefalse
    prompt: str
    code_snippet: Optional[str] = Field(default=None)
    code_language: Optional[str] = Field(default=None)
    # [{ "id": "a", "text": "..." }] — a resposta certa NUNCA vem marcada aqui.
    options: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    # Fica fora do payload que o frontend recebe ANTES de responder — o router
    # remove este campo na listagem de questões (ver docs/API_CONTRACT.md).
    correct: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    explanation: Optional[str] = Field(default=None)
    difficulty: str = Field(default="medio")
    # O que a questão testa, em uma frase, escrito pela IA junto com ela.
    # É por aqui que duas questões diferentes sobre a MESMA ideia viram um
    # item de revisão só — o enunciado não serve para isso, porque reescrever
    # o enunciado é justamente o que a reciclagem faz.
    concept: Optional[str] = Field(default=None)
    # Preenchido quando esta questão nasceu de um erro anterior. É o fio que
    # liga a resposta de hoje ao item de revisão que a gerou, e sem ele o
    # acerto de uma questão reciclada não teria como aposentar o item.
    review_item_id: Optional[uuid.UUID] = Field(
        default=None, sa_type=PGUUID(as_uuid=True), index=True
    )
    tag_ids: list[uuid.UUID] = Field(default_factory=list, sa_column=_uuid_array())
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrAttempt(SQLModel, table=True):
    __tablename__ = "pathr_attempt"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(sa_column=_fk("pathr_quiz.id"))
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    started_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    finished_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    score: Optional[float] = Field(default=None)  # 0..100
    correct_count: int = Field(default=0)
    duration_s: int = Field(default=0)
    # [{question_id, answer, is_correct, feedback}]
    answers: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    # Diagnóstico por tag gerado ao fechar a tentativa — realimenta
    # PathrUserTag.proficiency e o roadmap.
    tag_breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())


class PathrReviewItem(SQLModel, table=True):
    """Repetição espaçada (SM-2). Um item por conceito que o usuário errou ou
    marcou para revisar — não por questão, porque a mesma ideia reaparece em
    questões diferentes e revisar o conceito é o que consolida."""

    __tablename__ = "pathr_review_item"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    kind: str = Field(default="concept")  # concept|question|vocab
    tag_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    question_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    front: str
    back: str
    ease: float = Field(default=2.5)  # SM-2 E-Factor
    interval_days: int = Field(default=0)
    repetitions: int = Field(default=0)
    lapses: int = Field(default=0)
    due_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True), index=True)
    last_reviewed_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Inglês corporativo (módulo ativável)
# ---------------------------------------------------------------------------


class PathrEnglishProfile(SQLModel, table=True):
    """`enabled` é o interruptor da aba de inglês — o pedido foi um módulo que
    se LIGA quando quiser, não uma seção sempre presente."""

    __tablename__ = "pathr_english_profile"

    user_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    # A chave e (user_id, language): uma linha por idioma que a pessoa estuda.
    # Com user_id sozinho, como era ate a 0007, o banco so tinha lugar para um
    # idioma -- nenhuma tela resolveria isso.
    language: str = Field(default="en", primary_key=True)  # ISO 639-1
    # A regua que a pessoa escolheu ver: cefr, ielts, toefl_ibt, jlpt, hsk...
    # O app SEMPRE mede em `cefr_level`; este campo diz como apresentar. Ver
    # services/languages.py.
    exam: str = Field(default="cefr")
    # A meta na escala do exame ("7.0", "N2", "95"). O equivalente em CEFR sai
    # da tabela de conversao, e nao daqui: guardar os dois deixaria os dois
    # divergirem no dia em que a equivalencia fosse corrigida.
    exam_target: Optional[str] = Field(default=None)
    enabled: bool = Field(default=False)
    cefr_level: Optional[str] = Field(default=None)  # A1..C2
    target_level: str = Field(default="B2")
    # {"grammar": 62, "vocabulary": 70, "listening": 55, "reading": 74,
    #  "writing": 60, "speaking": 48, "business": 58} — 0..100
    sub_scores: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    focus_areas: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    daily_goal_min: int = Field(default=15)
    last_assessment_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrEnglishAssessment(SQLModel, table=True):
    """Nivelamento adaptativo: a dificuldade do próximo item sai do acerto do
    anterior, então o teste converge no nível CEFR em ~20 itens."""

    __tablename__ = "pathr_english_assessment"

    # Qual idioma esta linha mede/pratica. Sem isto o baralho de
    # espanhol e o de ingles virariam um so.
    language: str = Field(default="en", index=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    kind: str = Field(default="placement")  # placement|progress
    status: str = Field(default="in_progress")  # in_progress|done|abandoned
    item_count: int = Field(default=20)
    answered_count: int = Field(default=0)
    correct_count: int = Field(default=0)
    cefr_result: Optional[str] = Field(default=None)
    sub_scores: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    feedback: Optional[str] = Field(default=None)
    started_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    finished_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))


class PathrEnglishItem(SQLModel, table=True):
    __tablename__ = "pathr_english_item"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    assessment_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    # grammar|vocabulary|reading|listening|writing|speaking|business
    skill: str = Field(default="grammar")
    type: str = Field(default="mcq")  # mcq|gap|reorder|match|writing|speaking|email|roleplay
    cefr_band: str = Field(default="B1")
    prompt: str
    context: Optional[str] = Field(default=None)  # e-mail/reunião que enquadra o item
    audio_url: Optional[str] = Field(default=None)
    options: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    correct: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    user_answer: Optional[str] = Field(default=None)
    is_correct: Optional[bool] = Field(default=None)
    feedback: Optional[str] = Field(default=None)
    order_index: int = Field(default=0)
    answered_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrEnglishSession(SQLModel, table=True):
    """Treino conversacional em cenário corporativo (daily, 1:1, entrevista,
    apresentação, negociação). O transcript inteiro fica aqui para o feedback
    poder citar a frase exata que o usuário escreveu."""

    __tablename__ = "pathr_english_session"

    # Qual idioma esta linha mede/pratica. Sem isto o baralho de
    # espanhol e o de ingles virariam um so.
    language: str = Field(default="en", index=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    # roleplay|interview|meeting|email|presentation|smalltalk|standup
    mode: str = Field(default="roleplay")
    scenario: str
    persona: Optional[str] = Field(default=None)
    cefr_band: str = Field(default="B1")
    status: str = Field(default="active")  # active|done
    # [{role: 'user'|'coach', text, corrected, notes, ts}]
    transcript: list[Any] = Field(default_factory=list, sa_column=_jsonb("[]"))
    feedback: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    score: Optional[float] = Field(default=None)
    duration_s: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    finished_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))


class PathrEnglishVocab(SQLModel, table=True):
    __tablename__ = "pathr_english_vocab"

    # Qual idioma esta linha mede/pratica. Sem isto o baralho de
    # espanhol e o de ingles virariam um so.
    language: str = Field(default="en", index=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    term: str
    translation: Optional[str] = Field(default=None)
    definition: Optional[str] = Field(default=None)
    example: Optional[str] = Field(default=None)
    phonetic: Optional[str] = Field(default=None)
    domain: str = Field(default="business")  # business|tech|general
    cefr_band: str = Field(default="B1")
    source: Optional[str] = Field(default=None)  # de qual sessão/item veio
    # SRS próprio (mesmos campos de PathrReviewItem, mantidos aqui porque o
    # baralho de vocabulário é consultado e revisado dentro do módulo de
    # inglês, não misturado com a revisão de programação).
    ease: float = Field(default=2.5)
    interval_days: int = Field(default=0)
    repetitions: int = Field(default=0)
    due_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True), index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    __table_args__ = (sa.UniqueConstraint("user_id", "term", name="uq_pathr_english_vocab"),)


# ---------------------------------------------------------------------------
# Progresso e operação
# ---------------------------------------------------------------------------


class PathrActivity(SQLModel, table=True):
    """Feed + heatmap. Uma linha por ação concluída — é a fonte única para
    streak, XP e horas estudadas, em vez de cada módulo manter seu contador."""

    __tablename__ = "pathr_activity"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    kind: str = Field(index=True)
    # resource_done|quiz_done|node_done|english_session|english_assessment|
    # review_done|roadmap_created|resume_parsed
    ref_id: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    title: Optional[str] = Field(default=None)
    minutes: int = Field(default=0)
    xp: int = Field(default=0)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, sa_column=_uuid_array())
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    # Data local do usuário (não UTC) — o heatmap e o streak são por DIA no
    # fuso dele; derivar isso de created_at em UTC erraria o dia para quem
    # estuda de noite no Brasil.
    activity_date: date = Field(sa_type=sa.Date(), index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrStreak(SQLModel, table=True):
    __tablename__ = "pathr_streak"

    user_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    current: int = Field(default=0)
    longest: int = Field(default=0)
    last_active_date: Optional[date] = Field(default=None, sa_type=sa.Date())
    total_xp: int = Field(default=0)
    total_minutes: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrAiJob(SQLModel, table=True):
    """Auditoria de toda chamada de IA: qual modelo respondeu, quanto custou,
    e o que voltou. Sem isso, não há como diagnosticar um roadmap ruim nem
    perceber que o fallback do OpenRouter virou o caminho padrão."""

    __tablename__ = "pathr_ai_job"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(sa_column=_fk("pathr_user.id"))
    # resume_parse|roadmap_gen|quiz_gen|english_eval|english_turn|resource_search
    kind: str = Field(index=True)
    status: str = Field(default="queued")  # queued|running|done|failed
    provider: Optional[str] = Field(default=None)  # gemini|openrouter
    model: Optional[str] = Field(default=None)
    input_ref: Optional[uuid.UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True))
    output: dict[str, Any] = Field(default_factory=dict, sa_column=_jsonb())
    error: Optional[str] = Field(default=None)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    latency_ms: int = Field(default=0)
    attempt: int = Field(default=1)  # >1 = caiu no fallback
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    finished_at: Optional[datetime] = Field(default=None, sa_type=sa.DateTime(timezone=True))


class PathrAiProviderCooldown(SQLModel, table=True):
    """Circuit breaker persistido da rotação de IA (app/ai_providers.py).

    Um candidato (provedor + chave) que respondeu 429/402 fica rebaixado na
    fila por um tempo, para não gastar uma ida e volta por requisição numa
    chave cuja cota diária já acabou. Persistir em vez de manter só em
    memória importa porque o processo reinicia — em plano free de hospedagem,
    várias vezes por dia — e a cota, não.

    Nunca é fonte de verdade: um registro obsoleto rebaixa o candidato, jamais
    o remove da rotação.

A tabela é deste banco e as chaves são desta conta (ver .env.example), então
    o que ela registra é a cota do PathR — nunca a de outro app.
    """

    __tablename__ = "pathr_ai_provider_cooldown"

    provider: str = Field(sa_column=Column(sa.Text, primary_key=True))
    until: datetime = Field(sa_type=sa.DateTime(timezone=True))
    reason: str
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))


class PathrAiProviderUsage(SQLModel, table=True):
    """Tokens gastos por candidato e por dia — a contagem real que o próprio
    provedor reporta, não estimativa. Alimenta o painel de custo e responde
    "qual chave está sustentando o app hoje?"."""

    __tablename__ = "pathr_ai_provider_usage"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    usage_date: date = Field(sa_type=sa.Date(), index=True)
    requests: int = Field(default=0)
    tokens: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    __table_args__ = (sa.UniqueConstraint("provider", "usage_date", name="uq_pathr_ai_provider_usage"),)


# ---------------------------------------------------------------------------
# Defaults: do Python para o banco
# ---------------------------------------------------------------------------


def _sql_literal(value: Any) -> Optional[str]:
    """O valor Python escrito como literal SQL, ou None se não der para
    traduzir com segurança."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return None


def _mirror_defaults_to_database() -> None:
    """Copia todo default do Python para o banco.

    Isto existe por causa da frase no topo deste arquivo: em runtime os
    routers falam com o Postgres via PostgREST, não por sessão SQLAlchemy. Um
    `default_factory=uuid.uuid4` só roda quando o SQLAlchemy monta o INSERT —
    e ele nunca monta. Pelo PostgREST a coluna simplesmente não é enviada,
    chega NULL, e o banco recusa com "violates not-null constraint".

    O sintoma é traiçoeiro: o modelo diz que a coluna tem default, os testes
    de modelo passam, e a falha só aparece no primeiro INSERT real — que foi
    exatamente onde ela apareceu (o seed do catálogo de tags).

    Fazer isso aqui, e não anotando 196 colunas à mão, tem duas razões: a
    tradução é mecânica e derivável (se o Python tem default, o banco precisa
    do mesmo), e uma coluna nova criada no futuro herda a correção sem
    ninguém precisar lembrar dela.

    Colunas SEM default continuam sem: `slug`, `name`, `email` e afins são
    obrigatórias de propósito, e inventar um valor para elas esconderia um
    dado que o chamador esqueceu de mandar.
    """
    for table in SQLModel.metadata.tables.values():
        if not table.name.startswith("pathr_"):
            continue
        for column in table.columns:
            # Já declarado à mão (_jsonb, _uuid_array) — respeita.
            if column.server_default is not None or column.default is None:
                continue

            if column.default.is_callable:
                # Despacha pelo python_type, não pela classe SQLAlchemy: uma
                # FK declarada à mão usa `postgresql.UUID` e um id inferido
                # pelo SQLModel usa `sa.Uuid`, e os dois precisam do mesmo
                # default. Checar a classe pegaria só um deles — foi
                # exatamente o erro da primeira versão disto.
                try:
                    python_type = column.type.python_type
                except NotImplementedError:
                    continue
                if python_type is uuid.UUID:
                    column.server_default = sa.DefaultClause(sa.text("gen_random_uuid()"))
                # datetime ANTES de date: datetime é subclasse de date, e a
                # ordem invertida daria current_date a uma coluna de timestamp.
                elif python_type is datetime:
                    column.server_default = sa.DefaultClause(sa.text("now()"))
                elif python_type is date:
                    column.server_default = sa.DefaultClause(sa.text("current_date"))
                continue

            literal = _sql_literal(column.default.arg)
            if literal is not None:
                column.server_default = sa.DefaultClause(sa.text(literal))


_mirror_defaults_to_database()
