"""Schema inicial do PathR.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-08

Esta migration cria as 28 tabelas que existiam no dia em que o projeto
ganhou migrations, com `op.create_table` explícito — uma chamada por
tabela, cada coluna escrita à mão —, e não mais a partir do metadata
vivo de `app/models.py` (que foi como esta migration nasceu).

O atalho original (`SQLModel.metadata.create_all(tables=_pathr_tables())`)
parecia seguro porque "a 0001 É o schema inteiro", mas tinha um defeito: ele
lia o metadata de HOJE, não o de 2026-09-08. Toda vez que uma coluna nova
entrava em `app/models.py`, um banco criado do zero (`alembic upgrade head`
numa instalação nova, ver scripts/bootstrap.py) passava a nascer com essa
coluna já na 0001 — e a migration seguinte que a adiciona de verdade
(0003, 0004, 0006, 0016, 0019, 0020, 0028, 0032, 0033, 0035, 0037, 0044...)
batia de frente com "column already exists". Quem já migrou (o banco de
produção, que rodou a 0001 antiga e depois todas as seguintes em ordem)
nunca viu o problema — o estado final é o mesmo dos dois jeitos. Só uma
instalação nova, rodando a 0001 de hoje, sofria.

A REGRA para decidir o que entra aqui: uma coluna pertence à 0001 se, e só
se, nenhuma migration 0002+ faz `op.add_column` dela. Se uma migration
posterior adiciona a coluna, ela nasce SÓ lá — nunca aqui, mesmo que
`app/models.py` já a tenha hoje. O mesmo vale para tabela inteira: das 52
que `app/models.py` descreve hoje, 28 são destas; as outras 24 nasceram
depois com `op.create_table` na própria migration que as criou (passkeys,
atividade prática, inglês conversacional, amizades, denúncias, varredura
de erro, feature flag, banco de respostas, notícias, chave da extensão...)
e continuam de responsabilidade exclusiva dela.

Índice, constraint de unicidade e FK seguem a mesma regra: só entram aqui
se nenhuma migration posterior os cria — senão duplicariam o que a
migration dona já faz.

As migrations SEGUINTES a esta continuam sendo geradas normalmente com
`alembic revision --autogenerate`, que produz o diff explícito contra o
banco real — o jeito errado era só para o marco zero, onde não havia banco
real contra o qual gerar diff.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _fk(name: str, target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> sa.Column:
    return sa.Column(name, PGUUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    # -- Identidade e sessão -------------------------------------------------

    op.create_table(
        "pathr_user",
        _uuid_pk(),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_secret_encrypted", sa.String(), nullable=True),
        sa.Column("mfa_pending_secret_encrypted", sa.String(), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locale", sa.String(), nullable=False, server_default="pt-BR"),
        sa.Column("timezone_name", sa.String(), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("theme", sa.String(), nullable=False, server_default="system"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_pathr_user_email", "pathr_user", ["email"], unique=True)

    op.create_table(
        "pathr_refresh_token",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from", PGUUID(as_uuid=True), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_refresh_token_user_id", "pathr_refresh_token", ["user_id"])
    op.create_index("ix_pathr_refresh_token_token_hash", "pathr_refresh_token", ["token_hash"], unique=True)

    op.create_table(
        "pathr_mfa_backup_code",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_mfa_backup_code_user_id", "pathr_mfa_backup_code", ["user_id"])

    op.create_table(
        "pathr_email_token",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_email_token_user_id", "pathr_email_token", ["user_id"])
    op.create_index("ix_pathr_email_token_purpose", "pathr_email_token", ["purpose"])
    op.create_index("ix_pathr_email_token_token_hash", "pathr_email_token", ["token_hash"], unique=True)

    op.create_table(
        "pathr_security_event",
        _uuid_pk(),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("detail", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_security_event_user_id", "pathr_security_event", ["user_id"])
    op.create_index("ix_pathr_security_event_event_type", "pathr_security_event", ["event_type"])
    op.create_index("ix_pathr_security_event_created_at", "pathr_security_event", ["created_at"])

    # -- Perfil de estudo e currículo ----------------------------------------

    op.create_table(
        "pathr_profile",
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("headline", sa.String(), nullable=True),
        sa.Column("current_role", sa.String(), nullable=True),
        sa.Column("target_role", sa.String(), nullable=True),
        sa.Column("seniority", sa.String(), nullable=True),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.Column("weekly_hours", sa.Integer(), nullable=False, server_default=sa.text("8")),
        sa.Column("learning_style", sa.String(), nullable=True),
        sa.Column("goals", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("bio", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("github_url", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "pathr_resume",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("raw_text", sa.String(), nullable=True),
        sa.Column("parsed", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_resume_user_id", "pathr_resume", ["user_id"])
    op.create_index("ix_pathr_resume_content_hash", "pathr_resume", ["content_hash"])

    # -- Taxonomia de tecnologia ----------------------------------------------

    op.create_table(
        "pathr_tag",
        _uuid_pk(),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("parent_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("aliases", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("popularity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_tag_slug", "pathr_tag", ["slug"], unique=True)
    op.create_index("ix_pathr_tag_category", "pathr_tag", ["category"])
    op.create_index("ix_pathr_tag_parent_id", "pathr_tag", ["parent_id"])

    op.create_table(
        "pathr_user_tag",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        _fk("tag_id", "pathr_tag.id"),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("proficiency", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("is_target", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "tag_id", name="uq_pathr_user_tag"),
    )
    op.create_index("ix_pathr_user_tag_user_id", "pathr_user_tag", ["user_id"])
    op.create_index("ix_pathr_user_tag_tag_id", "pathr_user_tag", ["tag_id"])

    # -- Roadmap ---------------------------------------------------------------

    op.create_table(
        "pathr_roadmap",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("target_role", sa.String(), nullable=True),
        sa.Column("horizon_weeks", sa.Integer(), nullable=False, server_default=sa.text("12")),
        sa.Column("weekly_hours", sa.Integer(), nullable=False, server_default=sa.text("8")),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("generated_by", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("meta", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_roadmap_user_id", "pathr_roadmap", ["user_id"])

    op.create_table(
        "pathr_roadmap_node",
        _uuid_pk(),
        _fk("roadmap_id", "pathr_roadmap.id"),
        sa.Column("parent_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False, server_default="skill"),
        sa.Column("tag_ids", ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("depends_on", ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("level", sa.String(), nullable=True),
        sa.Column("estimated_hours", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("week_start", sa.Integer(), nullable=True),
        sa.Column("week_end", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="todo"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("objectives", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_roadmap_node_roadmap_id", "pathr_roadmap_node", ["roadmap_id"])
    op.create_index("ix_pathr_roadmap_node_parent_id", "pathr_roadmap_node", ["parent_id"])

    # -- Biblioteca de conteúdo ------------------------------------------------

    op.create_table(
        "pathr_resource",
        _uuid_pk(),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("thumbnail_url", sa.String(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(), nullable=False, server_default="pt"),
        sa.Column("level", sa.String(), nullable=True),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tag_ids", ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("added_by", PGUUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_resource_url", "pathr_resource", ["url"], unique=True)
    op.create_index("ix_pathr_resource_kind", "pathr_resource", ["kind"])

    op.create_table(
        "pathr_user_resource",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        _fk("resource_id", "pathr_resource.id"),
        sa.Column("status", sa.String(), nullable=False, server_default="saved"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("minutes_spent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_pathr_user_resource"),
    )
    op.create_index("ix_pathr_user_resource_user_id", "pathr_user_resource", ["user_id"])
    op.create_index("ix_pathr_user_resource_resource_id", "pathr_user_resource", ["resource_id"])

    op.create_table(
        "pathr_node_resource",
        _uuid_pk(),
        _fk("node_id", "pathr_roadmap_node.id"),
        _fk("resource_id", "pathr_resource.id"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_node_resource_node_id", "pathr_node_resource", ["node_id"])
    op.create_index("ix_pathr_node_resource_resource_id", "pathr_node_resource", ["resource_id"])

    # -- Quiz, atividades e repetição espaçada ---------------------------------

    op.create_table(
        "pathr_quiz",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="practice"),
        sa.Column("node_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("tag_ids", ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("difficulty", sa.String(), nullable=False, server_default="medio"),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("time_limit_s", sa.Integer(), nullable=True),
        sa.Column("generated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_quiz_user_id", "pathr_quiz", ["user_id"])
    op.create_index("ix_pathr_quiz_node_id", "pathr_quiz", ["node_id"])

    op.create_table(
        "pathr_question",
        _uuid_pk(),
        _fk("quiz_id", "pathr_quiz.id"),
        sa.Column("type", sa.String(), nullable=False, server_default="single"),
        sa.Column("prompt", sa.String(), nullable=False),
        sa.Column("code_snippet", sa.String(), nullable=True),
        sa.Column("code_language", sa.String(), nullable=True),
        sa.Column("options", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("correct", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("explanation", sa.String(), nullable=True),
        sa.Column("difficulty", sa.String(), nullable=False, server_default="medio"),
        sa.Column("tag_ids", ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_question_quiz_id", "pathr_question", ["quiz_id"])

    op.create_table(
        "pathr_attempt",
        _uuid_pk(),
        _fk("quiz_id", "pathr_quiz.id"),
        _fk("user_id", "pathr_user.id"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_s", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("answers", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tag_breakdown", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_pathr_attempt_quiz_id", "pathr_attempt", ["quiz_id"])
    op.create_index("ix_pathr_attempt_user_id", "pathr_attempt", ["user_id"])

    op.create_table(
        "pathr_review_item",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("kind", sa.String(), nullable=False, server_default="concept"),
        sa.Column("tag_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("question_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("front", sa.String(), nullable=False),
        sa.Column("back", sa.String(), nullable=False),
        sa.Column("ease", sa.Float(), nullable=False, server_default=sa.text("2.5")),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_review_item_user_id", "pathr_review_item", ["user_id"])
    op.create_index("ix_pathr_review_item_tag_id", "pathr_review_item", ["tag_id"])
    op.create_index("ix_pathr_review_item_due_at", "pathr_review_item", ["due_at"])

    # -- Inglês corporativo (módulo ativável) ----------------------------------
    #
    # `language` só entra para estas quatro tabelas na migração 0007 — aqui o
    # módulo ainda é ingles-só, e a chave de pathr_english_profile é só
    # `user_id` (a composta com `language` também é coisa da 0007).

    op.create_table(
        "pathr_english_profile",
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cefr_level", sa.String(), nullable=True),
        sa.Column("target_level", sa.String(), nullable=False, server_default="B2"),
        sa.Column("sub_scores", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("focus_areas", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("daily_goal_min", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("last_assessment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "pathr_english_assessment",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("kind", sa.String(), nullable=False, server_default="placement"),
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default=sa.text("20")),
        sa.Column("answered_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cefr_result", sa.String(), nullable=True),
        sa.Column("sub_scores", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("feedback", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_english_assessment_user_id", "pathr_english_assessment", ["user_id"])

    op.create_table(
        "pathr_english_item",
        _uuid_pk(),
        sa.Column("assessment_id", PGUUID(as_uuid=True), nullable=True),
        _fk("user_id", "pathr_user.id"),
        sa.Column("skill", sa.String(), nullable=False, server_default="grammar"),
        sa.Column("type", sa.String(), nullable=False, server_default="mcq"),
        sa.Column("cefr_band", sa.String(), nullable=False, server_default="B1"),
        sa.Column("prompt", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("audio_url", sa.String(), nullable=True),
        sa.Column("options", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("correct", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("user_answer", sa.String(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("feedback", sa.String(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_english_item_assessment_id", "pathr_english_item", ["assessment_id"])
    op.create_index("ix_pathr_english_item_user_id", "pathr_english_item", ["user_id"])

    op.create_table(
        "pathr_english_session",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("mode", sa.String(), nullable=False, server_default="roleplay"),
        sa.Column("scenario", sa.String(), nullable=False),
        sa.Column("persona", sa.String(), nullable=True),
        sa.Column("cefr_band", sa.String(), nullable=False, server_default="B1"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("transcript", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("feedback", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_english_session_user_id", "pathr_english_session", ["user_id"])

    op.create_table(
        "pathr_english_vocab",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("translation", sa.String(), nullable=True),
        sa.Column("definition", sa.String(), nullable=True),
        sa.Column("example", sa.String(), nullable=True),
        sa.Column("phonetic", sa.String(), nullable=True),
        sa.Column("domain", sa.String(), nullable=False, server_default="business"),
        sa.Column("cefr_band", sa.String(), nullable=False, server_default="B1"),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("ease", sa.Float(), nullable=False, server_default=sa.text("2.5")),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "term", name="uq_pathr_english_vocab"),
    )
    op.create_index("ix_pathr_english_vocab_user_id", "pathr_english_vocab", ["user_id"])
    op.create_index("ix_pathr_english_vocab_due_at", "pathr_english_vocab", ["due_at"])

    # -- Progresso e operação ---------------------------------------------------

    op.create_table(
        "pathr_activity",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("ref_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tag_ids", ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("detail", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_activity_user_id", "pathr_activity", ["user_id"])
    op.create_index("ix_pathr_activity_kind", "pathr_activity", ["kind"])
    op.create_index("ix_pathr_activity_activity_date", "pathr_activity", ["activity_date"])

    op.create_table(
        "pathr_streak",
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("current", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("longest", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.Column("total_xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "pathr_ai_job",
        _uuid_pk(),
        _fk("user_id", "pathr_user.id"),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("input_ref", PGUUID(as_uuid=True), nullable=True),
        sa.Column("output", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_ai_job_user_id", "pathr_ai_job", ["user_id"])
    op.create_index("ix_pathr_ai_job_kind", "pathr_ai_job", ["kind"])

    op.create_table(
        "pathr_ai_provider_cooldown",
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "pathr_ai_provider_usage",
        _uuid_pk(),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "usage_date", name="uq_pathr_ai_provider_usage"),
    )
    op.create_index("ix_pathr_ai_provider_usage_provider", "pathr_ai_provider_usage", ["provider"])
    op.create_index("ix_pathr_ai_provider_usage_usage_date", "pathr_ai_provider_usage", ["usage_date"])


def downgrade() -> None:
    # Ordem reversa: filho antes do pai, senão a FK barra o drop.
    op.drop_table("pathr_ai_provider_usage")
    op.drop_table("pathr_ai_provider_cooldown")
    op.drop_table("pathr_ai_job")
    op.drop_table("pathr_streak")
    op.drop_table("pathr_activity")
    op.drop_table("pathr_english_vocab")
    op.drop_table("pathr_english_session")
    op.drop_table("pathr_english_item")
    op.drop_table("pathr_english_assessment")
    op.drop_table("pathr_english_profile")
    op.drop_table("pathr_review_item")
    op.drop_table("pathr_attempt")
    op.drop_table("pathr_question")
    op.drop_table("pathr_quiz")
    op.drop_table("pathr_node_resource")
    op.drop_table("pathr_user_resource")
    op.drop_table("pathr_resource")
    op.drop_table("pathr_roadmap_node")
    op.drop_table("pathr_roadmap")
    op.drop_table("pathr_user_tag")
    op.drop_table("pathr_tag")
    op.drop_table("pathr_resume")
    op.drop_table("pathr_profile")
    op.drop_table("pathr_security_event")
    op.drop_table("pathr_email_token")
    op.drop_table("pathr_mfa_backup_code")
    op.drop_table("pathr_refresh_token")
    op.drop_table("pathr_user")
