"""Envia as credenciais do .env.local para a Fly, sem imprimir valor nenhum.

Digitar doze segredos à mão num painel é como a DATABASE_URL do Render foi
parar no banco com o próprio nome colado no valor. Aqui o texto vai do arquivo
para o `fly secrets import` por um cano, sem passar pela tela nem pela lista de
argumentos do processo (onde qualquer `ps` leria).

O que é público — região, URLs, nome do remetente — mora no fly.toml e não
passa por aqui.

Uso:
    python scripts/fly_secrets.py --check   # confere sem enviar
    python scripts/fly_secrets.py           # envia
"""

from __future__ import annotations

import argparse
import base64
import pathlib
import subprocess
import sys

# As chaves que o app precisa e que não podem ficar no fly.toml. A ordem é a
# do config.py, para facilitar a conferência lado a lado.
SEGREDOS = (
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
    "DATABASE_URL",
    "JWT_SECRET_KEY",
    "MFA_ENCRYPTION_KEY",
    "BREVO_API_KEY",
    "BREVO_FROM_EMAIL",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "MISTRAL_API_KEY",
    "CEREBRAS_API_KEY",
    "YOUTUBE_API_KEY",
    "TAVILY_API_KEY",
    "BRAVE_API_KEY",
)

# Segredos que podem faltar sem o app ficar quebrado — a ausência desliga uma
# fonte, não uma função. Tavily e Brave são ou-um-ou-outro (services/
# resource_search.py usa o Tavily quando os dois existem), e sem YOUTUBE a
# busca cai na reserva por IA. Uma lista onde tudo é obrigatório reprovaria o
# envio inteiro por causa de uma chave que ninguém precisa ter.
OPCIONAIS = frozenset({"YOUTUBE_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY"})

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def carrega(caminho: pathlib.Path) -> dict[str, str]:
    """Lê um .env simples. Não expande variáveis nem interpreta aspas soltas —
    o objetivo é transportar o texto literal, igual ao que o pydantic lê."""
    valores: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, _, valor = linha.partition("=")
        valores[nome.strip()] = valor.strip().strip('"').strip("'")
    return valores


def problemas(valores: dict[str, str]) -> list[str]:
    """Defeitos que só apareceriam depois do deploy, quando o app já subiu."""
    achados: list[str] = []

    for nome in SEGREDOS:
        valor = valores.get(nome, "")
        if not valor:
            if nome not in OPCIONAIS:
                achados.append(f"{nome}: ausente ou vazia")
            continue
        # O defeito que derrubou dois deploys no Render: a linha inteira do
        # .env colada no campo de valor do painel.
        cabeca, igual, _ = valor.partition("=")
        if igual and cabeca == cabeca.upper() and cabeca.replace("_", "").isalnum():
            achados.append(f"{nome}: o valor começa com '{cabeca}=' — o nome ficou colado nele")

    # RFC 7518 exige 32 bytes para HS256. Uma chave curta funciona em teste e
    # deixa a assinatura mais fácil de quebrar do que o algoritmo promete.
    jwt = valores.get("JWT_SECRET_KEY", "")
    if jwt:
        try:
            bruto = base64.urlsafe_b64decode(jwt + "=" * (-len(jwt) % 4))
        except Exception:
            bruto = jwt.encode()
        if max(len(bruto), len(jwt.encode())) < 32:
            achados.append("JWT_SECRET_KEY: menos de 32 bytes (RFC 7518 pede 32 para HS256)")

    return achados


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--check", action="store_true", help="confere sem enviar")
    argumentos.add_argument("--app", default="pathr-backend")
    argumentos.add_argument("--env-file", default=str(RAIZ / ".env.local"))
    opcoes = argumentos.parse_args()

    caminho = pathlib.Path(opcoes.env_file)
    if not caminho.exists():
        print(f"nao encontrei {caminho}", file=sys.stderr)
        return 1

    valores = carrega(caminho)

    print(f"{len(SEGREDOS)} segredos a enviar para o app '{opcoes.app}':")
    for nome in SEGREDOS:
        valor = valores.get(nome, "")
        # Só o comprimento. O valor nunca chega à tela.
        estado = f"{len(valor)} chars" if valor else "AUSENTE"
        print(f"   {nome:24} {estado}")

    achados = problemas(valores)
    if achados:
        print("\nproblemas:")
        for achado in achados:
            print(f"   - {achado}")
        return 1

    if opcoes.check:
        print("\ntudo certo. rode sem --check para enviar.")
        return 0

    # O texto vai por stdin: não aparece na tela nem na linha de comando do
    # processo, onde um `ps` de outro usuário poderia lê-lo.
    # Só o que tem valor: `valores[nome]` daria KeyError num opcional ausente,
    # e mandar `NOME=` vazio criaria na Fly um segredo em branco que sombreia
    # o default do config.py em vez de deixá-lo valer.
    enviaveis = [nome for nome in SEGREDOS if valores.get(nome)]
    payload = "".join(f"{nome}={valores[nome]}\n" for nome in enviaveis)
    processo = subprocess.run(
        ["fly", "secrets", "import", "--app", opcoes.app],
        input=payload,
        text=True,
    )
    if processo.returncode != 0:
        print("\no fly recusou o envio.", file=sys.stderr)
        return processo.returncode

    print("\nenviados. a Fly reinicia o app sozinha para aplicá-los.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
