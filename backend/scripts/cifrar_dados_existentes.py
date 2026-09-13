"""Cifra os dados sensíveis gravados antes da cifra existir.

Depois do deploy que liga `services/cifra.py`, o que é gravado sai cifrado,
mas o que já estava no banco e no armazenamento continua em claro (a leitura
aceita as duas formas). Este script cifra o que sobrou:

- `pathr_profile.birth_date`
- `pathr_resume.raw_text` e `pathr_resume.parsed`
- `pathr_report.message` e `pathr_report.moderator_note`
- os arquivos de currículo, foto de perfil e foto de relato

Idempotente: o que já está cifrado é pulado. Sem `--aplicar`, só conta o que
faria e não escreve nada.

    python -m scripts.cifrar_dados_existentes            # simulação
    python -m scripts.cifrar_dados_existentes --aplicar  # grava

Precisa de DATA_ENCRYPTION_KEY igual à do servidor — com outra chave, o
servidor não conseguiria ler o que o script gravou.
"""

import argparse
import sys
from typing import Any

from app.config import settings
from app.database import get_supabase
from app.services import cifra


def _texto(supabase: Any, tabela: str, colunas: dict[str, Any], aplicar: bool, contagem: dict[str, int]) -> None:
    linhas = supabase.table(tabela).select("*").execute().data or []
    for linha in linhas:
        mudancas = {}
        for coluna, contexto in colunas.items():
            valor = linha.get(coluna)
            if coluna == "parsed":
                if valor and not (isinstance(valor, dict) and "_cifrado" in valor):
                    mudancas[coluna] = cifra.cifrar_json(valor, contexto(linha))
            elif isinstance(valor, str) and valor and not valor.startswith(cifra.PREFIXO):
                mudancas[coluna] = cifra.cifrar(valor, contexto(linha))
        for coluna in mudancas:
            contagem[f"{tabela}.{coluna}"] = contagem.get(f"{tabela}.{coluna}", 0) + 1
        if mudancas and aplicar:
            chave = "user_id" if tabela == "pathr_profile" else "id"
            supabase.table(tabela).update(mudancas).eq(chave, str(linha[chave])).execute()


def _arquivos(supabase: Any, bucket: str, caminhos: list[str], aplicar: bool, contagem: dict[str, int]) -> None:
    for caminho in caminhos:
        try:
            dados = supabase.storage.from_(bucket).download(caminho)
        except Exception as exc:  # noqa: BLE001
            print(f"  aviso: {bucket}/{caminho} não baixou ({type(exc).__name__})")
            continue
        if not dados or dados.startswith(cifra.MAGICO):
            continue
        contagem[f"arquivos:{bucket}"] = contagem.get(f"arquivos:{bucket}", 0) + 1
        if aplicar:
            cifrado = cifra.cifrar_bytes(dados, cifra.ctx_arquivo(bucket, caminho))
            supabase.storage.from_(bucket).update(caminho, cifrado, {"upsert": "true"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Cifra os dados sensíveis gravados em claro.")
    parser.add_argument("--aplicar", action="store_true", help="grava; sem isto só conta")
    args = parser.parse_args()

    if not cifra.ativa():
        print("DATA_ENCRYPTION_KEY não configurada: nada a fazer.", file=sys.stderr)
        return 1

    supabase = get_supabase()
    contagem: dict[str, int] = {}

    _texto(supabase, "pathr_profile", {"birth_date": lambda l: cifra.ctx_nascimento(str(l["user_id"]))},
           args.aplicar, contagem)
    _texto(supabase, "pathr_resume", {
        "raw_text": lambda l: cifra.ctx_curriculo_texto(str(l["user_id"])),
        "parsed": lambda l: cifra.ctx_curriculo_dados(str(l["user_id"])),
    }, args.aplicar, contagem)
    _texto(supabase, "pathr_report", {
        "message": lambda l: cifra.ctx_relato(str(l["user_id"]), "message"),
        "moderator_note": lambda l: cifra.ctx_relato(str(l["user_id"]), "moderator_note"),
    }, args.aplicar, contagem)

    usuarios = supabase.table("pathr_user").select("avatar_path").execute().data or []
    _arquivos(supabase, settings.avatar_bucket, [u["avatar_path"] for u in usuarios if u.get("avatar_path")],
              args.aplicar, contagem)
    curriculos = supabase.table("pathr_resume").select("storage_path").execute().data or []
    _arquivos(supabase, settings.resume_bucket, [c["storage_path"] for c in curriculos if c.get("storage_path")],
              args.aplicar, contagem)
    relatos = supabase.table("pathr_report").select("attachment_path").execute().data or []
    _arquivos(supabase, settings.report_bucket, [r["attachment_path"] for r in relatos if r.get("attachment_path")],
              args.aplicar, contagem)

    verbo = "cifrados" if args.aplicar else "a cifrar (simulação)"
    if not contagem:
        print("Nada em claro: tudo já está cifrado.")
    for item, total in sorted(contagem.items()):
        print(f"{item}: {total} {verbo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
