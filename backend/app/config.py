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
    # Fotos anexadas a relatos (reclamação/sugestão). Privado como os outros:
    # a imagem só sai pela API, para o autor e para a moderação.
    report_bucket: str = "pathr-reports"
    # Quem modera os relatos, pelo e-mail da conta. Lista para caber mais de
    # um moderador sem mudar código; comparado sem distinção de caixa.
    #
    # VAZIO por padrão, e é importante que seja: com um e-mail fixo aqui, toda
    # instalação nova — inclusive um fork — nasceria dando moderação e
    # administração ao dono da instalação ORIGINAL. Quem opera declara os seus
    # em MODERATOR_EMAILS / SUPER_ADMIN_EMAILS.
    moderator_emails: list[str] = []
    # Quem administra CONTAS (ver a lista de usuários, banir). Separado de
    # moderar: responder relatos não deve dar o poder de tirar alguém do app.
    super_admin_emails: list[str] = []

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
    # AES-256-GCM dos dados sensíveis (services/cifra.py): 32 bytes em base64
    # url-safe. Gere com: python -c "import os,base64;
    # print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    # Guarde uma cópia fora do Fly: perder a chave é perder os dados cifrados.
    data_encryption_key: str = ""
    # Chaves anteriores, separadas por vírgula, só para LER o que foi cifrado
    # antes de uma troca de chave.
    data_encryption_keys_old: str = ""
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # Tentativas de senha erradas antes do bloqueio temporário da conta.
    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    # --- E-mail transacional (Brevo) ---
    # Conta e remetente próprios do PathR: o e-mail de confirmação sai em nome
    # deste app, e o domínio verificado no Brevo precisa ser o dele.
    # Cloudflare Turnstile (desafio anti-robô do cadastro). Vazio: desligado, e
    # o cadastro segue com os outros mecanismos (services/antirrobo.py).
    turnstile_secret_key: str = ""
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

    # --- Vagas ---
    # Gupy e Remotive não pedem chave. A Adzuna (agregador com API oficial para
    # o Brasil) pede as duas; vazias, a fonte fica de fora. O Tavily/Brave de
    # cima também procura vagas em sites confiáveis. Ver services/vagas.py.
    adzuna_app_id: str = ""  # https://developer.adzuna.com
    # O painel da Adzuna chama de "app_key", mas quem copia escreve
    # ADZUNA_API_KEY com a mesma frequência. Aceitar os dois evita a chave
    # preenchida que o app não enxerga.
    adzuna_app_key: str = Field(default="", validation_alias=AliasChoices("ADZUNA_APP_KEY", "ADZUNA_API_KEY"))

    # --- Tradução (módulo de idioma) ---
    # Vazio desliga o DeepL e a tradução do modelo de IA vale sozinha. Chave
    # terminada em ":fx" é do plano Free (api-free.deepl.com). Ver
    # services/traducao.py.
    deepl_api_key: str = ""

    # --- Disparo de avisos por e-mail ---
    # O segredo que o cron externo apresenta em X-Pathr-Jobs-Secret. Vazio
    # desliga o disparo inteiro: melhor não mandar nada do que deixar a rota
    # aberta para qualquer um acionar e-mail em nome do app.
    jobs_secret: str = ""

    # --- Varredura diária ---
    # Segredo PRÓPRIO da rotina que alimenta o Notion, separado do JOBS_SECRET
    # de propósito: ele só abre /jobs/varredura, que lê relatos sem autor e
    # manda no máximo um e-mail por dia para a moderação. Vazaria menos do que
    # o outro, que dispara e-mail para todas as contas.
    scan_secret: str = ""

    # --- Chave de acesso (WebAuthn) ---
    # O domínio a que as chaves ficam presas. Vazio = o host de FRONTEND_URL
    # (pathr.notter.com.br), e é de propósito que NÃO seja notter.com.br: no
    # domínio de cima a chave valeria também para o Notter e o FinanceR, e o
    # PathR tem contas próprias. Só se preenche para desenvolvimento local.
    webauthn_rp_id: str = ""
    webauthn_rp_name: str = "PathR"

    # --- Limites de upload ---
    max_resume_mb: int = 10
    # A foto é exibida num quadrado de 64px. 5 MB é folga larga para qualquer
    # retrato de celular e ainda barra o upload acidental de uma imagem de
    # câmera profissional inteira.
    max_avatar_mb: int = 5
    # Teto de QUALQUER requisição (app/limite_corpo.py): o maior envio legítimo
    # é o currículo de 10 MB, mais a embalagem do formulário.
    max_request_mb: int = 12

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

    def problemas_de_producao(self) -> list[str]:
        """O que impede a produção de subir com segurança — só NOMES, nunca valores.

        Sem isto, um segredo esquecido na Fly deixava o app subir normalmente:
        com `JWT_SECRET_KEY` vazia, todo token de sessão seria assinado com a
        string vazia, e qualquer um forjaria o cookie de qualquer conta. Falhar
        no boot é o único jeito de o erro aparecer antes de alguém explorá-lo.
        """
        if not self.is_production:
            return []
        problemas: list[str] = []
        if len(self.jwt_secret_key.encode()) < 32:
            problemas.append("JWT_SECRET_KEY ausente ou curta (mínimo 32 bytes)")
        if not self.mfa_encryption_key:
            problemas.append("MFA_ENCRYPTION_KEY ausente")
        if not self.data_encryption_key:
            problemas.append("DATA_ENCRYPTION_KEY ausente")
        return problemas


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
