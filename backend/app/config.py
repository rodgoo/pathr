"""Configuração do PathR.

Lido de variáveis de ambiente (e de `.env.local` em desenvolvimento). Todo
segredo tem default vazio de propósito: o app sobe sem eles e cada rota que
depende de um responde um erro claro, em vez de o processo morrer no import
e derrubar tudo por causa de uma integração opcional.

Tudo aqui é do PathR e só dele: projeto Supabase próprio, chaves de IA
próprias, remetente de e-mail próprio. O app não divide credencial nem banco
com nenhum outro — o Notter apenas oferece um link que abre este site numa
aba nova.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identidade do serviço ---
    app_name: str = "PathR"
    environment: str = "development"  # development|staging|production
    debug: bool = False

    # --- Supabase: projeto EXCLUSIVO do PathR ---
    supabase_url: str = ""
    # A chave secreta do servidor: ignora RLS, e o backend é o único chamador
    # confiável do Supabase neste app (o frontend só fala com esta API).
    #
    # Dois nomes aceitos de propósito. O Supabase renomeou as chaves em 2025 —
    # projetos novos entregam `sb_secret_...` sob o rótulo "secret key", e
    # projetos antigos têm o JWT `service_role`. Aceitar os dois evita que
    # alguém copie o valor certo do painel novo e o app não enxergue, que é um
    # erro sem sintoma útil: a variável parece preenchida e a conexão falha.
    supabase_service_role_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_SECRET_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
    )
    # URL direta do Postgres, usada SÓ pelo Alembic (o runtime vai por
    # PostgREST). Prefira o pooler (aws-…pooler.supabase.com) ao host direto,
    # que resolve só em IPv6.
    #
    # O prefixo é normalizado para `postgresql+psycopg://` — ver
    # `_force_psycopg_driver` abaixo.
    database_url: str = ""
    # Bucket do Supabase Storage onde o PDF/DOCX do currículo é guardado.
    resume_bucket: str = "pathr-resumes"
    # Bucket das fotos de perfil. Separado do de currículos porque o ciclo de
    # vida é outro: a foto é substituída no lugar, o currículo se acumula.
    avatar_bucket: str = "pathr-avatars"

    # --- Origens e cookies ---
    # O app vive em pathr.notter.com.br e a API em api.pathr.notter.com.br:
    # mesmo registrable domain (notter.com.br), então SameSite=Strict vale e
    # é o único valor aceitável em produção.
    frontend_url: str = "https://localhost:5173"
    api_url: str = "https://localhost:8031"
    cors_origins: list[str] = ["https://localhost:5173", "http://localhost:5173"]
    cookie_samesite: str = "strict"
    # Escopo do cookie de sessão. Vazio = host-only, e é assim que deve
    # ficar — inclusive em produção.
    #
    # O cookie é emitido por api.pathr.notter.com.br e TODA chamada da API vai
    # para esse mesmo host, então host-only já basta: o navegador o devolve
    # para quem o emitiu. Definir ".notter.com.br" aqui não conserta nada e
    # amplia o estrago — passaria a anexar a sessão do PathR também em
    # requisições para notter.com.br e financer.notter.com.br, que são outros
    # aplicativos, com outras contas.
    #
    # O que faz a sessão funcionar entre pathr.notter.com.br e
    # api.pathr.notter.com.br é o SameSite, não o Domain: os dois estão sob o
    # mesmo domínio registrável (notter.com.br), então a requisição é
    # same-site e o cookie Strict acompanha.
    #
    # Só preencha para um ambiente onde a API responda num host diferente do
    # que o navegador chama — o que não é o caso aqui.
    cookie_domain: str = ""

    # --- Auth ---
    jwt_secret_key: str = ""
    # Chave Fernet (32 bytes url-safe base64) que cifra o segredo TOTP em
    # repouso. Gere com: python -c "from cryptography.fernet import Fernet;
    # print(Fernet.generate_key().decode())"
    mfa_encryption_key: str = ""
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # Tentativas de senha erradas antes do bloqueio temporário da conta.
    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    # --- E-mail transacional (Brevo) ---
    # Conta e remetente próprios do PathR: o e-mail de confirmação sai em nome
    # deste app, e o domínio verificado no Brevo precisa ser o dele.
    brevo_api_key: str = ""
    brevo_from_email: str = ""
    brevo_sender_name: str = "PathR"

    # --- Provedores de IA ---
    # Todo *_API_KEY aceita uma LISTA separada por vírgula: cada chave vira um
    # candidato independente na rotação, com cota e cooldown próprios.
    # Ver app/ai_providers.py.
    gemini_api_key: str = ""  # https://aistudio.google.com/apikey
    groq_api_key: str = ""  # https://console.groq.com/keys
    groq_model: str = "openai/gpt-oss-120b"
    openrouter_api_key: str = ""  # https://openrouter.ai/keys
    # Escolhido por medicao, com o pedido real do roadmap em producao: ~30s e
    # 2/2 respostas validas, contra 63s do gpt-oss-20b que estava aqui antes
    # (e contra o slug ":free" anterior, que a OpenRouter tirou do catalogo e
    # respondia 404 a cada tentativa).
    #
    # O mistral-small-2603 media ~28s, um pouco melhor -- mas e do MESMO
    # fornecedor do Mistral direto que ja esta na rotacao, e a rotacao existe
    # para sobreviver a queda de um fornecedor. Um segundo e meio nao paga
    # perder um fornecedor independente.
    openrouter_model: str = "qwen/qwen3.8-flash"
    mistral_api_key: str = ""  # https://console.mistral.ai/api-keys
    mistral_model: str = "open-mistral-nemo"
    cerebras_api_key: str = ""  # https://cloud.cerebras.ai
    cerebras_model: str = "gpt-oss-120b"
    # Teto de tempo da rotação INTEIRA, em segundos. Precisa caber na janela
    # do proxy da borda: estourá-la troca a nossa mensagem de erro por um 502
    # mudo, depois de a pessoa ter esperado à toa. Ver `_BUDGET` em
    # app/ai_providers.py.
    ai_budget_seconds: int = 50

    # --- Busca de material (biblioteca) ---
    # Alimentam services/resource_search.py. Sem chave, a fonte correspondente
    # simplesmente não entra na busca — o mesmo contrato dos provedores de IA
    # acima. Com nenhuma das duas, sobra a curadoria por IA, que já funciona
    # com as chaves de LLM.
    #
    # A do YouTube é a que tem cota apertada de verdade: `search.list` custa
    # 100 das 10.000 unidades diárias, ou seja ~100 buscas por dia para o app
    # inteiro. Por isso a curadoria é por TAG (compartilhada entre todos os
    # usuários) e tem carência — ver pathr_tag.curated_at.
    youtube_api_key: str = ""  # https://console.cloud.google.com (YouTube Data API v3)
    # Um buscador para artigo. Preencha UM dos dois; se ambos vierem, o Tavily
    # ganha por já devolver resumo pronto e dispensar uma segunda chamada.
    tavily_api_key: str = ""  # https://app.tavily.com
    brave_api_key: str = ""  # https://brave.com/search/api

    # --- Limites de upload ---
    max_resume_mb: int = 10
    # A foto é exibida num quadrado de 64px. 5 MB é folga larga para qualquer
    # retrato de celular e ainda barra o upload acidental de uma imagem de
    # câmera profissional inteira.
    max_avatar_mb: int = 5

    @field_validator("database_url")
    @classmethod
    def _force_psycopg_driver(cls, value: str) -> str:
        """Aceita a string que o painel do Supabase entrega, como ela é.

        O painel dá `postgresql://...`, e com esse prefixo o SQLAlchemy procura
        o psycopg2 — que não está nas dependências (usamos psycopg 3). O erro
        que aparece é um `ModuleNotFoundError` no meio de uma migration, que
        não diz a ninguém que faltava escrever `+psycopg` na variável de
        ambiente.

        Exigir a edição manual seria um passo a mais para errar em cada
        ambiente — inclusive ao colar a variável no painel do host, onde o
        erro só aparece no log do primeiro deploy. Normalizar aqui é o lugar
        onde a correção vale para todos eles de uma vez.

        Um driver explicitamente escolhido (`+asyncpg`, por exemplo) é
        respeitado: só o caso sem driver é reescrito.
        """
        if value.startswith("postgres://"):
            # Formato legado de vários provedores; o SQLAlchemy 2 não o aceita.
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
