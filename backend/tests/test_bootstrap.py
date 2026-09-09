"""A verificação prévia do bootstrap.

Ela existe para falhar ANTES de qualquer escrita. O caso ruim que este teste
protege é metade dos passos aplicados num banco errado porque uma credencial
tinha ficado com o valor de exemplo.
"""

import pytest

from app.config import settings
from scripts.bootstrap import check_settings

_VALIDAS = {
    "supabase_url": "https://abcdefgh.supabase.co",
    "supabase_service_role_key": "chave",
    "database_url": "postgresql+psycopg://u:p@aws-0-sa-east-1.pooler.supabase.com:5432/postgres",
    "jwt_secret_key": "segredo",
    "mfa_encryption_key": "fernet",
}


@pytest.fixture
def config(monkeypatch):
    """Aplica um conjunto de valores sobre as settings, restaurando depois."""

    def apply(**overrides):
        for field, value in {**_VALIDAS, **overrides}.items():
            monkeypatch.setattr(settings, field, value)

    return apply


def test_passa_com_tudo_preenchido(config):
    config()
    assert check_settings() == []


def test_acusa_o_placeholder_do_exemplo(config):
    """Copiar o .env.example e esquecer de trocar é o erro mais comum."""
    config(supabase_url="https://SEU-PROJETO.supabase.co")
    assert any("SUPABASE_URL" in problem for problem in check_settings())


def test_acusa_credencial_vazia(config):
    config(supabase_service_role_key="")
    assert any("SERVICE_ROLE" in problem for problem in check_settings())


def test_avisa_sobre_o_host_direto_do_postgres(config):
    """O host direto db.<ref>.supabase.co resolve só em IPv6 — o Render e a
    maioria das hospedagens não alcançam, e o erro que aparece lá não diz
    isso."""
    config(database_url="postgresql+psycopg://u:p@db.abcdefgh.supabase.co:5432/postgres")
    problems = check_settings()
    assert any("pooler" in problem for problem in problems)


def test_acusa_chaves_de_auth_faltando(config):
    """Sem elas o app sobe e só quebra no primeiro login — tarde demais."""
    config(jwt_secret_key="", mfa_encryption_key="")
    problems = check_settings()
    assert any("JWT_SECRET_KEY" in problem for problem in problems)
    assert any("MFA_ENCRYPTION_KEY" in problem for problem in problems)


class TestUrlsTrocadas:
    """A confusão entre SUPABASE_URL e DATABASE_URL.

    São duas coisas diferentes no painel do Supabase (API vs Database) e o
    erro que aparece quando se troca uma pela outra não diz isso — o cliente
    morre com um SupabaseException genérico. Estes testes existem para o
    diagnóstico continuar apontando o dedo no lugar certo.
    """

    def test_acusa_a_string_do_postgres_em_supabase_url(self, config):
        from scripts.check_env import check_swapped_urls

        config(supabase_url="postgresql://postgres.abc:senha@aws-0.pooler.supabase.com:5432/postgres")
        problems = [r for r in check_swapped_urls() if not r.ok]
        assert problems and "SUPABASE_URL" in problems[0].detail

    def test_acusa_a_url_da_api_em_database_url(self, config):
        from scripts.check_env import check_swapped_urls

        config(database_url="https://abcdefgh.supabase.co")
        problems = [r for r in check_swapped_urls() if not r.ok]
        assert problems and "DATABASE_URL" in problems[0].detail

    def test_nao_reclama_da_string_que_o_painel_entrega(self, config):
        """O app normaliza o driver sozinho (config.py's
        _force_psycopg_driver), então cobrar o `+psycopg` do usuário virou
        ruído sobre um valor que funciona."""
        from scripts.check_env import check_swapped_urls

        config(database_url="postgresql+psycopg://u:p@aws-0.pooler.supabase.com:5432/postgres")
        assert all(result.ok for result in check_swapped_urls())

    def test_aceita_as_duas_no_lugar_certo(self, config):
        from scripts.check_env import check_swapped_urls

        config()
        assert all(result.ok for result in check_swapped_urls())


class TestNomesDeVariavel:
    """Erro de digitação em nome de variável.

    O sintoma é cruel: o arquivo tem a linha preenchida e o app relata a
    variável como ausente. As duas coisas verdadeiras, nenhuma apontando para
    a letra que falta.
    """

    def test_distancia_de_edicao_pega_letra_faltando(self):
        from scripts.check_env import _edit_distance, _similar

        # O caso real que motivou isto.
        assert _edit_distance("DATABSE_URL", "DATABASE_URL") == 1
        assert _similar("DATABSE_URL", "DATABASE_URL")

    def test_pega_letra_trocada_e_duplicada(self):
        from scripts.check_env import _similar

        assert _similar("DATABASE_URI", "DATABASE_URL")
        assert _similar("JWT_SECRET_KEYY", "JWT_SECRET_KEY")

    def test_nao_sugere_variavel_de_outro_assunto(self):
        """Sugerir GROQ_MODEL para quem escreveu GROQ_API_KEY seria pior que
        não sugerir nada."""
        from scripts.check_env import _similar

        assert not _similar("GROQ_API_KEY", "GROQ_MODEL")
        assert not _similar("SUPABASE_URL", "DATABASE_URL")

    def test_nao_reclama_das_chaves_que_o_painel_entrega_e_o_app_ignora(self, tmp_path, monkeypatch):
        """SUPABASE_PUBLISHABLE_KEY e SUPABASE_JWKS_URL vêm do painel do
        Supabase e este backend não usa nenhuma das duas — reclamar delas
        seria ruído em cima de um arquivo correto."""
        from scripts.check_env import check_unknown_keys

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env.local").write_text(
            "SUPABASE_URL=https://x.supabase.co\n"
            "SUPABASE_PUBLISHABLE_KEY=sb_publishable_x\n"
            "SUPABASE_JWKS_URL=https://x/jwks\n",
            encoding="utf-8",
        )
        assert all(result.ok for result in check_unknown_keys())


class TestDriverDoPostgres:
    """A normalização do prefixo da DATABASE_URL.

    O painel do Supabase entrega `postgresql://`, e com ele o SQLAlchemy
    procura o psycopg2 — que não está nas dependências. O erro resultante é um
    ModuleNotFoundError no meio de uma migration, que não diz a ninguém que
    faltava escrever `+psycopg` numa variável de ambiente.
    """

    def _url(self, raw: str) -> str:
        from app.config import Settings

        return Settings(database_url=raw).database_url

    def test_aceita_a_string_como_o_painel_entrega(self):
        assert self._url("postgresql://u:p@host:5432/db").startswith("postgresql+psycopg://")

    def test_aceita_o_formato_legado_postgres(self):
        """Vários provedores ainda entregam `postgres://`, que o SQLAlchemy 2
        recusa de saída."""
        assert self._url("postgres://u:p@host:5432/db").startswith("postgresql+psycopg://")

    def test_preserva_o_resto_da_string_intacto(self):
        url = self._url("postgresql://u:p@aws-0.pooler.supabase.com:5432/postgres")
        assert url.endswith("u:p@aws-0.pooler.supabase.com:5432/postgres")

    def test_nao_mexe_num_driver_escolhido_de_proposito(self):
        assert self._url("postgresql+asyncpg://u:p@host/db").startswith("postgresql+asyncpg://")

    def test_deixa_vazio_como_vazio(self):
        assert self._url("") == ""


class TestSenhaDoBanco:
    """O marcador de senha que o painel do Supabase entrega.

    A string vem com a senha entre colchetes, e quem copia sem trocar recebe
    um OperationalError que não explica nada. Pior: os colchetes fazem o
    urlsplit do Python tratar o host como IPv6 e levantar um ValueError sobre
    endereço inválido, que aponta para o lugar errado.
    """

    def test_acusa_o_marcador_entre_colchetes(self, config):
        from scripts.check_env import check_database_url

        config(database_url="postgresql+psycopg://postgres.abc:[YOUR-PASSWORD]@aws-0.pooler.supabase.com:5432/postgres")
        result = check_database_url()
        assert not result.ok
        assert "colchetes" in result.detail

    def test_nao_confunde_senha_real_com_marcador(self, config):
        """Uma senha legítima passa desta checagem e segue para a tentativa de
        conexão de verdade — que falha aqui por o host não existir, e é o que
        se espera de um teste offline."""
        from scripts.check_env import check_database_url

        config(
            database_url=(
                "postgresql+psycopg://postgres.abc:s3nh4Real"
                "@host-que-nao-existe.invalid:5432/postgres"
            )
        )
        result = check_database_url()
        assert not result.ok
        assert "colchetes" not in result.detail
