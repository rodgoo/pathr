"""Procura credenciais reais nos arquivos que vão para o repositório.

Escrito depois de um susto: as cinco chaves de IA acabaram coladas dentro do
`.env.example`, que É versionado — a um `git push` de virarem públicas. O
`.gitignore` não protege contra isso, porque o arquivo deve mesmo ser
versionado; o que não devia estar ali era o conteúdo.

Roda antes de commitar:

    python -m scripts.check_secrets          # varre os arquivos rastreáveis
    python -m scripts.check_secrets --staged # só o que está no índice

Só reporta o ARQUIVO e o padrão que casou — nunca o trecho, para o próprio
relatório não virar o vazamento.
"""

import argparse
import pathlib
import re
import subprocess
import sys

# Prefixos que só existem em credencial de verdade. Deliberadamente
# específicos: um padrão genérico como "[A-Za-z0-9]{32}" acusaria hash de
# commit, chave de CSS e id de teste, e um verificador que grita sempre é um
# verificador que ninguém lê.
PADROES = {
    "Supabase (secret)": r"sb_secret_[A-Za-z0-9_-]{10,}",
    "Supabase (publishable)": r"sb_publishable_[A-Za-z0-9_-]{10,}",
    "JWT/Supabase legado": r"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
    "Brevo": r"xkeysib-[A-Za-z0-9]{20,}",
    "Google/Gemini": r"AIza[A-Za-z0-9_-]{30,}",
    "Groq": r"gsk_[A-Za-z0-9]{30,}",
    "OpenRouter": r"sk-or-v1-[a-f0-9]{40,}",
    "OpenAI": r"sk-[A-Za-z0-9]{40,}",
    "Cerebras": r"csk-[a-z0-9]{30,}",
    "Senha em URL de banco": r"postgres(?:ql)?(?:\+\w+)?://[^:\s]+:(?!SENHA|\[)[^@\s]{6,}@",
}

# Extensões que nunca contêm credencial e inflam a varredura.
IGNORAR_SUFIXOS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2"}


def _raiz_do_repo() -> pathlib.Path:
    """A raiz do repositório, não o diretório de onde o script foi chamado.

    Sem isto, rodar de dentro de backend/ varreria só backend/ e daria um
    "nenhuma credencial encontrada" que não vale nada — foi o que aconteceu na
    primeira execução.
    """
    saida = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return pathlib.Path(saida) if saida else pathlib.Path.cwd()


def _arquivos(apenas_staged: bool) -> list[pathlib.Path]:
    raiz = _raiz_do_repo()
    comando = (
        ["git", "diff", "--cached", "--name-only"]
        if apenas_staged
        else ["git", "ls-files", "-co", "--exclude-standard"]
    )
    saida = subprocess.run(comando, capture_output=True, text=True, check=False, cwd=raiz).stdout
    return [
        p
        for nome in saida.splitlines()
        if (p := raiz / nome.strip()).is_file() and p.suffix.lower() not in IGNORAR_SUFIXOS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Procura credenciais em arquivos versionáveis.")
    parser.add_argument("--staged", action="store_true", help="varre só o índice do git")
    args = parser.parse_args()

    achados: list[tuple[str, str]] = []
    arquivos = _arquivos(args.staged)
    for caminho in arquivos:
        try:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rotulo, padrao in PADROES.items():
            if re.search(padrao, texto):
                achados.append((str(caminho), rotulo))

    print(f"varridos: {len(arquivos)} arquivos")
    if not achados:
        print("nenhuma credencial encontrada.")
        return 0

    print(f"\n{len(achados)} ocorrência(s):\n")
    for caminho, rotulo in achados:
        print(f"  {caminho}  ->  {rotulo}")
    print("\nNÃO commite. Mova o valor para .env.local (que é ignorado).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
