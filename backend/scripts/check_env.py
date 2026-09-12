"""Testa as credenciais do .env.local de verdade — sem imprimir nenhuma.

Diferente de scripts/bootstrap.py, que só confere se os campos estão
preenchidos, este script USA cada credencial numa chamada real e barata, e
reporta apenas se funcionou. É a diferença entre "a variável existe" e "a
chave é válida".

Regra que o arquivo inteiro respeita: **nada de valor secreto na saída.** Nem
truncado, nem mascarado, nem em mensagem de erro — mensagens de provedor
costumam ecoar a chave enviada, então o que sai daqui é a classe do erro e o
código HTTP, nunca o corpo. A URL do projeto também fica de fora: ela
identifica o projeto e não acrescenta nada ao diagnóstico.

    python -m scripts.check_env
    python -m scripts.check_env --skip-ai   # sem tocar nos provedores de IA
"""

import argparse
import sys
from dataclasses import dataclass, field
from typing import Callable

import httpx

# Curto de propósito: isto é um teste de credencial, não de disponibilidade.
# Um provedor lento não deve travar a verificação inteira.
_TIMEOUT = 12


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""
    #  Avisos não reprovam a verificação, mas aparecem no relatório.
    warnings: list[str] = field(default_factory=list)


def _ok(name: str, detail: str = "") -> Result:
    return Result(name, True, detail)


def _fail(name: str, detail: str) -> Result:
    return Result(name, False, detail)


def _http_reason(response: httpx.Response) -> str:
    """O motivo, a partir do STATUS — nunca do corpo.

    O corpo de um 400/401 de provedor frequentemente inclui a chave enviada
    ou trechos do prompt.
    """
    if response.status_code in (401, 403):
        return "chave recusada (não autorizada)"
    if response.status_code == 404:
        return "endpoint ou modelo inexistente"
    if response.status_code == 429:
        return "chave válida, mas sem cota agora"
    return f"HTTP {response.status_code}"


# Variáveis que o app lê. Um nome fora desta lista, mas parecido com um dela,
# é quase sempre erro de digitação — e o sintoma é a variável simplesmente não
# existir, que é indistinguível de "esqueci de preencher".
_KNOWN_KEYS = frozenset(
    {
        "ENVIRONMENT", "DEBUG",
        "SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY",
        "DATABASE_URL", "RESUME_BUCKET",
        "FRONTEND_URL", "API_URL", "CORS_ORIGINS",
        "COOKIE_SAMESITE", "COOKIE_DOMAIN",
        "JWT_SECRET_KEY", "MFA_ENCRYPTION_KEY",
        "ACCESS_TOKEN_MINUTES", "REFRESH_TOKEN_DAYS",
        "MAX_FAILED_ATTEMPTS", "LOCKOUT_MINUTES", "MAX_RESUME_MB",
        "BREVO_API_KEY", "BREVO_FROM_EMAIL", "BREVO_SENDER_NAME",
        "GEMINI_API_KEY", "GROQ_API_KEY", "GROQ_MODEL",
        "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
        "MISTRAL_API_KEY", "MISTRAL_MODEL",
        "CEREBRAS_API_KEY", "CEREBRAS_MODEL",
        "YOUTUBE_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY", "JOBS_SECRET",
    }
)

# Nomes que o painel do Supabase entrega e este backend não usa. Ignorados de
# propósito: o frontend nunca fala com o Supabase direto, então a chave
# publishable e a URL de JWKS não têm papel aqui.
_IGNORED_KEYS = frozenset({"SUPABASE_PUBLISHABLE_KEY", "SUPABASE_JWKS_URL", "SUPABASE_ANON_KEY"})


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein, uma linha da matriz por vez.

    Comparar caracteres ordenados seria mais curto e estaria errado: em
    DATABSE_URL contra DATABASE_URL, a letra que falta desloca todo o resto e
    a contagem estoura, exatamente no caso que isto existe para pegar.
    """
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,          # remoção
                    current[j - 1] + 1,       # inserção
                    previous[j - 1] + (ca != cb),  # substituição
                )
            )
        previous = current
    return previous[-1]


def _similar(name: str, known: str) -> bool:
    """Perto o bastante para ser erro de digitação, e não outra variável."""
    if abs(len(name) - len(known)) > 2:
        return False
    return 0 < _edit_distance(name, known) <= 2


def check_unknown_keys() -> list[Result]:
    """Nomes de variável que o app não conhece.

    Sem isto, um `DATABSE_URL` fica preenchido no arquivo e o app relata
    "DATABASE_URL não preenchida" — as duas coisas verdadeiras, e nenhuma
    apontando para o erro.
    """
    import pathlib

    name = "Nomes das variáveis"
    path = pathlib.Path(".env.local")
    if not path.exists():
        return [_ok(name, ".env.local não encontrado (usando o ambiente)")]

    problems: list[Result] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.partition("=")[0].strip().upper()
        if key in _KNOWN_KEYS or key in _IGNORED_KEYS:
            continue
        suggestion = next((known for known in _KNOWN_KEYS if _similar(key, known)), None)
        problems.append(
            _fail(
                name,
                f"{key} não é lida pelo app"
                + (f" — você quis dizer {suggestion}?" if suggestion else ""),
            )
        )

    return problems or [_ok(name, "todos reconhecidos")]


def check_swapped_urls() -> list[Result]:
    """As duas URLs estão no campo certo?

    Confundi-las é fácil e o erro que aparece não ajuda: `SUPABASE_URL` é o
    endereço da API REST (https://<ref>.supabase.co, no painel em Settings ->
    API) e `DATABASE_URL` é a string de conexão do Postgres, com senha
    embutida (Settings -> Database). Colar a segunda na primeira faz o cliente
    morrer com um SupabaseException genérico, que não diz qual é o problema.

    Detectar pelo ESQUEMA, não pelo comprimento: postgresql:// numa variável
    que deveria ser https:// é inequívoco.
    """
    from app.config import settings

    results: list[Result] = []
    name = "Formato das URLs"

    if settings.supabase_url.startswith(("postgres://", "postgresql")):
        results.append(
            _fail(
                name,
                "SUPABASE_URL contém a string de conexão do Postgres — ela vai em "
                "DATABASE_URL. Em SUPABASE_URL vai https://<ref>.supabase.co "
                "(Settings -> API)",
            )
        )
    elif settings.supabase_url and not settings.supabase_url.startswith("https://"):
        results.append(_fail(name, "SUPABASE_URL não começa com https://"))

    if settings.database_url.startswith("https://"):
        results.append(
            _fail(
                name,
                "DATABASE_URL contém a URL da API — ela vai em SUPABASE_URL. Em "
                "DATABASE_URL vai a string de conexão do Postgres "
                "(Settings -> Database)",
            )
        )

    return results or [_ok(name, "cada URL no campo certo")]


def check_supabase_rest() -> Result:
    """A service_role key funciona no PostgREST?

    Consulta uma tabela do app com limit(0): interessa a autorização e a
    existência do schema, não o conteúdo.
    """
    name = "Supabase (PostgREST)"
    try:
        from app.database import get_supabase

        get_supabase().table("pathr_tag").select("*").limit(0).execute()
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        # A tabela ausente é um diagnóstico diferente de credencial inválida,
        # e a diferença muda o que a pessoa deve fazer.
        if "pathr_tag" in text or "does not exist" in text or "PGRST205" in text:
            return _fail(name, "credencial aceita, mas o schema ainda não existe — rode o bootstrap")
        return _fail(name, f"{exc.__class__.__name__} — verifique URL e service_role key")
    return _ok(name, "autenticado e schema visível")


def check_storage() -> Result:
    """A mesma chave alcança o Storage, e o bucket dos currículos é privado?"""
    from app.config import settings

    name = "Supabase (Storage)"
    try:
        from app.database import get_supabase

        buckets = get_supabase().storage.list_buckets()
    except Exception as exc:  # noqa: BLE001
        return _fail(name, f"{exc.__class__.__name__} — a chave não alcança o Storage")

    target = next((b for b in buckets if b.id == settings.resume_bucket), None)
    if target is None:
        return _fail(name, f"bucket ausente — rode o bootstrap para criá-lo")

    result = _ok(name, "bucket presente")
    if getattr(target, "public", False):
        # Currículo tem nome, telefone e histórico de alguém, e o caminho do
        # arquivo é previsível (user_id/hash.pdf).
        result.warnings.append(
            "o bucket está PÚBLICO — torne-o privado no painel do Supabase"
        )
    return result


def check_database_url() -> Result:
    """A URL do Alembic conecta de verdade?

    É a credencial mais fácil de errar: a string do host direto
    (db.<ref>.supabase.co) parece certa, funciona em algumas máquinas e falha
    em qualquer host sem IPv6 — inclusive no Render.
    """
    from app.config import settings

    name = "Postgres (DATABASE_URL)"
    if not settings.database_url:
        return _fail(name, "não preenchida")

    # A string do painel vem com a senha entre colchetes, como marcador. Sem
    # esta checagem o sintoma é um OperationalError opaco — e pior, a senha
    # entre colchetes faz o próprio urlsplit do Python tratar o host como
    # IPv6 e levantar um ValueError sem relação aparente com o problema.
    if "[" in settings.database_url or "]" in settings.database_url:
        return _fail(
            name,
            "a senha ainda é o marcador entre colchetes — substitua pela senha real "
            "do banco (Settings -> Database) e tire os colchetes",
        )

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(settings.database_url, pool_pre_ping=False)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        engine.dispose()
    except Exception as exc:  # noqa: BLE001
        return _fail(name, f"{exc.__class__.__name__} — não conectou")

    result = _ok(name, "conectado")
    if "pooler" not in settings.database_url:
        result.warnings.append(
            "não é a string do pooler — conectou aqui, mas o host direto resolve "
            "só em IPv6 e falha no Render"
        )
    return result


def check_fernet() -> Result:
    """A MFA_ENCRYPTION_KEY é uma chave Fernet válida?

    Um valor aleatório qualquer passa na verificação de "está preenchida" e só
    explode quando alguém ativa o segundo fator. Um ciclo cifra/decifra
    resolve isso agora.
    """
    name = "MFA_ENCRYPTION_KEY"
    try:
        from app.security import decrypt_secret, encrypt_secret

        if decrypt_secret(encrypt_secret("teste")) != "teste":
            return _fail(name, "ciclo de cifra não fechou")
    except Exception as exc:  # noqa: BLE001
        return _fail(name, f"{exc.__class__.__name__} — não é uma chave Fernet válida")
    return _ok(name, "cifra e decifra")


def check_jwt() -> Result:
    """A JWT_SECRET_KEY assina e valida?"""
    name = "JWT_SECRET_KEY"
    try:
        import uuid

        from app.security import create_access_token, decode_access_token

        user_id, session_id = uuid.uuid4(), uuid.uuid4()
        payload = decode_access_token(create_access_token(user_id, session_id))
        if not payload or payload.get("sub") != str(user_id):
            return _fail(name, "token assinado não validou")
    except Exception as exc:  # noqa: BLE001
        return _fail(name, f"{exc.__class__.__name__}")

    result = _ok(name, "assina e valida")
    # HS256 usa a chave como segredo HMAC-SHA256: abaixo de 32 bytes ela tem
    # menos entropia que o próprio hash, o que é o que a RFC 7518 (seção 3.2)
    # manda evitar. Assina e valida do mesmo jeito — por isso é aviso e não
    # falha —, mas é gratuito de corrigir agora e caro depois: trocar a chave
    # invalida toda sessão viva.
    from app.config import settings

    if len(settings.jwt_secret_key.encode()) < 32:
        result.warnings.append(
            f"chave de {len(settings.jwt_secret_key.encode())} bytes — a RFC 7518 pede "
            "ao menos 32 para HS256. Gere com: openssl rand -hex 32"
        )
    return result


def check_ai_providers() -> list[Result]:
    """Testa cada CANDIDATO da rotação, um por chave.

    Usa o endpoint de LISTAGEM de modelos, não uma geração: listar é gratuito
    e não consome a cota que o app precisa. O objetivo aqui é saber se a chave
    é aceita, não se o modelo responde bem.

    O nome reportado é o mesmo da rotação ("Gemini #2"), então um problema
    aponta direto para a chave certa sem ninguém precisar vê-la.
    """
    from app.ai_providers import _OPENAI_COMPATIBLE, _keys, _named
    from app.config import settings

    results: list[Result] = []

    gemini_keys = _keys(settings.gemini_api_key)
    for index, key in enumerate(gemini_keys):
        name = _named("Gemini", index, len(gemini_keys))
        try:
            response = httpx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key},
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            results.append(_fail(name, f"{exc.__class__.__name__} — sem resposta"))
            continue
        results.append(
            _ok(name, "chave aceita")
            if response.status_code == 200
            else _fail(name, _http_reason(response))
        )

    for provider, key_attr, base_url, _model_attr in _OPENAI_COMPATIBLE:
        keys = _keys(getattr(settings, key_attr, "") or "")
        for index, key in enumerate(keys):
            name = _named(provider, index, len(keys))
            try:
                response = httpx.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=_TIMEOUT,
                )
            except httpx.HTTPError as exc:
                results.append(_fail(name, f"{exc.__class__.__name__} — sem resposta"))
                continue
            results.append(
                _ok(name, "chave aceita")
                if response.status_code == 200
                else _fail(name, _http_reason(response))
            )

    if not results:
        return [
            _fail(
                "Provedores de IA",
                "nenhuma chave configurada — a leitura de currículo não funciona",
            )
        ]

    # O Gemini é o único com visão: sem ele, o PDF do currículo cai para o
    # texto extraído, que perde layout de duas colunas e não lê PDF escaneado.
    if not gemini_keys:
        results.append(
            Result(
                "Gemini (visão)",
                True,
                "ausente",
                warnings=["sem GEMINI_API_KEY o currículo é lido só pelo texto extraído"],
            )
        )
    return results


def check_brevo() -> Result:
    """A chave do Brevo é aceita? O endpoint /v3/account é gratuito e não envia
    nenhum e-mail."""
    from app.config import settings

    name = "Brevo (e-mail)"
    if not settings.brevo_api_key:
        return Result(
            name,
            True,
            "não configurado",
            warnings=[
                "sem BREVO_API_KEY o cadastro funciona, mas o link de confirmação "
                "só aparece no log do servidor"
            ],
        )
    try:
        response = httpx.get(
            "https://api.brevo.com/v3/account",
            headers={"api-key": settings.brevo_api_key},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        return _fail(name, f"{exc.__class__.__name__} — sem resposta")

    if response.status_code != 200:
        return _fail(name, _http_reason(response))

    result = _ok(name, "chave aceita")
    if not settings.brevo_from_email:
        result.warnings.append("BREVO_FROM_EMAIL vazio — o envio falha sem remetente")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Testa as credenciais do .env.local sem imprimir nenhuma.",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="não chama os provedores de IA (útil offline)",
    )
    args = parser.parse_args()

    print("PathR — verificação de credenciais")
    print("(nenhum valor secreto é impresso)\n")

    checks: list[Callable[[], Result]] = [
        check_supabase_rest,
        check_storage,
        check_database_url,
        check_fernet,
        check_jwt,
        check_brevo,
    ]

    # A troca de URLs vem primeiro: ela explica falhas que, sem esse
    # diagnóstico, aparecem como erro genérico de credencial mais abaixo.
    results = check_unknown_keys()
    results += check_swapped_urls()
    results += [check() for check in checks]
    if not args.skip_ai:
        results.extend(check_ai_providers())

    width = max(len(result.name) for result in results)
    for result in results:
        mark = "ok  " if result.ok else "FALHA"
        print(f"  {mark} {result.name.ljust(width)}  {result.detail}")
        for warning in result.warnings:
            print(f"        aviso: {warning}")

    failed = [result for result in results if not result.ok]
    warned = sum(len(result.warnings) for result in results)

    print()
    if failed:
        print(f"{len(failed)} credencial(is) com problema. Nada foi alterado.")
        return 1
    if warned:
        print(f"Todas as credenciais funcionam. {warned} aviso(s) acima.")
        return 0
    print("Todas as credenciais funcionam.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
