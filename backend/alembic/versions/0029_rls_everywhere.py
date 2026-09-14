"""RLS ligado em TODAS as tabelas pathr_*, não só nas criadas a partir da 0020.

Revision ID: 0029_rls_everywhere
Revises: 0028_user_ban
Create Date: 2026-09-13

A 0020 tirou todo privilégio de `anon` e `authenticated` no schema inteiro —
é isso que hoje impede a chave pública do Supabase de ler qualquer tabela.
Mas RLS só foi ligado nas tabelas novas daquela migração em diante. Com RLS
ligado e nenhuma política, uma tabela nega tudo a esses papéis MESMO que um
GRANT volte a existir por engano (um clique no painel, uma extensão, um
`grant all` numa migração futura): são duas travas independentes, e a segunda
não custa nada.

O app não é afetado: fala com o banco pela chave service_role (que ignora
RLS), e as migrações rodam com o dono das tabelas.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0029_rls_everywhere"
down_revision: Union[str, None] = "0028_user_ban"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE t record;
        BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'pathr\\_%'
          LOOP
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    # Desligar RLS não desfaz nada útil e só abriria a segunda trava.
    pass
