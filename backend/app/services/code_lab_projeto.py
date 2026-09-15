"""Exemplo com vários arquivos, e a conferência de que ele é de verdade.

## Por que mais de um arquivo

"GitHub e testes automatizados" não se aprende num programa Java solto: na
vida real isso é um `.github/workflows/ci.yml` que o GitHub executa, chamando o
`mvn test` que roda um teste JUnit. Uma API Spring de verdade é Controller,
Service, Repository e Entity, cada um no seu arquivo e no seu pacote. Espremer
isso em um arquivo ensina uma estrutura que ninguém usa.

Então o exemplo é um conjunto pequeno de arquivos, e o traço diz em QUAL
arquivo cada passo acontece — a requisição entra no Controller, desce ao
Service, chega ao Repository, e volta.

## Por que conferir o conteúdo

O modelo inventa com a mesma cara de certeza com que acerta: action que não
existe, `javax.persistence` num Spring Boot 3, classe pública com nome diferente
do arquivo (que nem compila), YAML com indentação quebrada. Quem está
aprendendo copia isso. O que dá para conferir sem rodar nada é conferido aqui,
e o exemplo que falha volta para o modelo com o motivo — ou não é mostrado.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from pathlib import PurePosixPath
from typing import Any, Optional

import yaml

MAXIMO_DE_ARQUIVOS = 6
MAXIMO_DE_LINHAS_POR_ARQUIVO = 120
MAXIMO_DE_LINHAS_NO_TOTAL = 320

# Caminho relativo de projeto: sem barra no começo, sem `..`, só caracteres que
# aparecem em nome de arquivo de código. O caminho vai para a tela como texto,
# mas não precisa aceitar nada além disso.
_CAMINHO = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9_.\-/]{1,160}$")

_POR_EXTENSAO: dict[str, str] = {
    ".java": "java", ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript", ".cs": "csharp", ".go": "go",
    ".rs": "rust", ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".php": "php",
    ".rb": "ruby", ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift", ".dart": "dart", ".sql": "sql",
    ".sh": "bash", ".bash": "bash", ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".xml": "xml",
    ".html": "html", ".css": "css", ".tf": "terraform", ".ps1": "powershell",
}

# Linguagens de chaves: parêntese, colchete e chave precisam fechar.
_DE_CHAVES = frozenset(
    {"java", "javascript", "typescript", "csharp", "go", "rust", "c", "cpp", "php", "kotlin", "swift", "dart", "css", "terraform"}
)

# As actions oficiais mais usadas e a versão principal que é a atual. Versão
# anterior roda com aviso de descontinuada (ou nem roda mais), e é exatamente o
# que um exemplo antigo da internet — e o modelo — repete.
_ACTIONS_MINIMAS: dict[str, int] = {
    "actions/checkout": 4,
    "actions/setup-node": 4,
    "actions/setup-java": 4,
    "actions/setup-python": 5,
    "actions/setup-go": 5,
    "actions/setup-dotnet": 4,
    "actions/cache": 4,
    "actions/upload-artifact": 4,
    "actions/download-artifact": 4,
    "docker/login-action": 3,
    "docker/build-push-action": 5,
    "docker/setup-buildx-action": 3,
}
_USES = re.compile(r"^(?:\./[\w./-]+|docker://\S+|[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[\w./-]+)$")

_INSTRUCOES_DOCKERFILE = frozenset(
    "FROM RUN CMD LABEL EXPOSE ENV ADD COPY ENTRYPOINT VOLUME USER WORKDIR ARG ONBUILD STOPSIGNAL HEALTHCHECK SHELL".split()
)


def linguagem_do_arquivo(caminho: str) -> str:
    """O id de linguagem pelo nome do arquivo — o nome manda, não o que o
    modelo disse que era. "texto" para o que não tem realce próprio."""
    nome = PurePosixPath(caminho).name
    if nome == "Dockerfile" or nome.startswith("Dockerfile.") or nome.endswith(".dockerfile"):
        return "dockerfile"
    return _POR_EXTENSAO.get(PurePosixPath(nome).suffix.lower(), "texto")


def linhas_de(conteudo: str) -> list[str]:
    return conteudo.replace("\r\n", "\n").rstrip("\n").split("\n")


def normalizar(brutos: Any) -> tuple[list[dict[str, str]], Optional[str]]:
    """Os arquivos limpos, ou o motivo de não servirem."""
    if not isinstance(brutos, list) or not brutos:
        return [], "nenhum arquivo"
    if len(brutos) > MAXIMO_DE_ARQUIVOS:
        return [], f"mais de {MAXIMO_DE_ARQUIVOS} arquivos"
    arquivos: list[dict[str, str]] = []
    vistos: set[str] = set()
    total = 0
    for bruto in brutos:
        if not isinstance(bruto, dict):
            return [], "arquivo em formato inválido"
        caminho = str(bruto.get("caminho") or "").strip().removeprefix("./")
        conteudo = str(bruto.get("conteudo") or "").replace("\r\n", "\n").rstrip("\n")
        if not _CAMINHO.match(caminho):
            return [], f"caminho de arquivo inválido: {caminho[:60]!r}"
        if caminho in vistos:
            return [], f"arquivo repetido: {caminho}"
        if not conteudo.strip():
            return [], f"arquivo vazio: {caminho}"
        quantas = len(linhas_de(conteudo))
        if quantas > MAXIMO_DE_LINHAS_POR_ARQUIVO:
            return [], f"{caminho} passa de {MAXIMO_DE_LINHAS_POR_ARQUIVO} linhas"
        total += quantas
        vistos.add(caminho)
        arquivos.append({"caminho": caminho, "linguagem": linguagem_do_arquivo(caminho), "conteudo": conteudo})
    if total > MAXIMO_DE_LINHAS_NO_TOTAL:
        return [], f"o conjunto passa de {MAXIMO_DE_LINHAS_NO_TOTAL} linhas"
    return arquivos, None


# ---------------------------------------------------------------------------
# O conteúdo é de verdade?
# ---------------------------------------------------------------------------


def problemas(arquivos: list[dict[str, str]]) -> list[str]:
    """O que impede os arquivos de valerem num projeto real. Lista vazia: ok."""
    achados: list[str] = []
    for arquivo in arquivos:
        caminho, linguagem, conteudo = arquivo["caminho"], arquivo["linguagem"], arquivo["conteudo"]
        if linguagem == "yaml":
            achados += _problemas_yaml(caminho, conteudo)
        elif linguagem == "json":
            try:
                json.loads(conteudo)
            except ValueError as erro:
                achados.append(f"{caminho}: JSON inválido ({getattr(erro, 'msg', erro)})")
        elif linguagem == "xml":
            try:
                ElementTree.fromstring(conteudo)
            except ElementTree.ParseError as erro:
                achados.append(f"{caminho}: XML inválido ({erro})")
        elif linguagem == "dockerfile":
            achados += _problemas_dockerfile(caminho, conteudo)
        elif linguagem == "java":
            achados += _problemas_java(caminho, conteudo)
        if linguagem in _DE_CHAVES and not _equilibrado(conteudo, linguagem):
            achados.append(f"{caminho}: parênteses, colchetes ou chaves não fecham")
    return achados


def _problemas_yaml(caminho: str, conteudo: str) -> list[str]:
    try:
        documentos = [d for d in yaml.safe_load_all(conteudo) if d is not None]
    except yaml.YAMLError as erro:
        marca = getattr(erro, "problem_mark", None)
        onde = f" na linha {marca.line + 1}" if marca is not None else ""
        return [f"{caminho}: YAML inválido{onde}"]
    if not documentos:
        return [f"{caminho}: YAML vazio"]
    achados: list[str] = []
    if caminho.startswith(".github/workflows/"):
        achados += _problemas_workflow(caminho, documentos[0])
    nome = PurePosixPath(caminho).name
    if nome in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        if not isinstance(documentos[0], dict) or not isinstance(documentos[0].get("services"), dict):
            achados.append(f"{caminho}: Compose sem `services`")
    for documento in documentos:
        if isinstance(documento, dict) and "apiVersion" in documento and "kind" not in documento:
            achados.append(f"{caminho}: manifesto Kubernetes sem `kind`")
    return achados


def _problemas_workflow(caminho: str, dado: Any) -> list[str]:
    if not isinstance(dado, dict):
        return [f"{caminho}: workflow precisa ser um mapa"]
    achados: list[str] = []
    # YAML 1.1 lê a chave `on` como o booleano True; o GitHub aceita as duas.
    if "on" not in dado and True not in dado:
        achados.append(f"{caminho}: workflow sem `on` (o evento que dispara)")
    jobs = dado.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return achados + [f"{caminho}: workflow sem `jobs`"]
    for nome, job in jobs.items():
        if not isinstance(job, dict):
            achados.append(f"{caminho}: job {nome} inválido")
            continue
        if "uses" in job:  # workflow reutilizável: não tem runs-on nem steps
            continue
        if "runs-on" not in job:
            achados.append(f"{caminho}: job {nome} sem `runs-on`")
        passos = job.get("steps")
        if not isinstance(passos, list) or not passos:
            achados.append(f"{caminho}: job {nome} sem `steps`")
            continue
        for passo in passos:
            if not isinstance(passo, dict) or not ("uses" in passo or "run" in passo):
                achados.append(f"{caminho}: step do job {nome} sem `uses` nem `run`")
                continue
            if passo.get("uses") is None:
                continue
            uses = str(passo["uses"]).strip()
            if not _USES.match(uses):
                achados.append(f"{caminho}: `uses: {uses[:60]}` não é uma referência de action válida")
                continue
            achados += _versao_da_action(caminho, uses)
    return achados


def _versao_da_action(caminho: str, uses: str) -> list[str]:
    if "@" not in uses:
        return []
    nome, versao = uses.split("@", 1)
    minima = _ACTIONS_MINIMAS.get(nome.lower())
    casou = re.match(r"^v(\d+)", versao)
    if minima is None or not casou or int(casou.group(1)) >= minima:
        return []
    return [f"{caminho}: {nome}@{versao} está desatualizada; a versão atual é v{minima}"]


def _problemas_dockerfile(caminho: str, conteudo: str) -> list[str]:
    achados: list[str] = []
    primeira: Optional[str] = None
    continua = False
    for numero, linha in enumerate(linhas_de(conteudo), start=1):
        texto = linha.strip()
        if not texto or texto.startswith("#"):
            continue
        if continua:
            continua = texto.endswith("\\")
            continue
        instrucao = texto.split()[0].upper()
        if instrucao not in _INSTRUCOES_DOCKERFILE:
            achados.append(f"{caminho}: linha {numero} não começa com uma instrução do Dockerfile")
        primeira = primeira or instrucao
        continua = texto.endswith("\\")
    if primeira not in ("FROM", "ARG"):
        achados.append(f"{caminho}: Dockerfile precisa começar com FROM")
    return achados


def _problemas_java(caminho: str, conteudo: str) -> list[str]:
    achados: list[str] = []
    arquivo = PurePosixPath(caminho)
    publica = re.search(
        r"^\s*public\s+(?:(?:abstract|final|sealed|non-sealed|static)\s+)*(?:class|interface|enum|record|@interface)\s+(\w+)",
        conteudo,
        re.MULTILINE,
    )
    # Regra do compilador: a classe pública tem o nome do arquivo.
    if publica and publica.group(1) != arquivo.stem:
        achados.append(f"{caminho}: a classe pública {publica.group(1)} precisa estar em {publica.group(1)}.java")
    partes = arquivo.parts
    for inicio in range(max(len(partes) - 3, 0)):
        if partes[inicio] == "src" and partes[inicio + 1] in ("main", "test") and partes[inicio + 2] == "java":
            esperado = ".".join(partes[inicio + 3:-1])
            pacote = re.search(r"^\s*package\s+([\w.]+)\s*;", conteudo, re.MULTILINE)
            if esperado and (not pacote or pacote.group(1) != esperado):
                achados.append(f"{caminho}: o pacote precisa ser `package {esperado};`, pelo caminho do arquivo")
            break
    # Spring Boot 3 e Jakarta EE 9+ trocaram javax.* por jakarta.*: import javax
    # dessas especificações não compila num projeto atual.
    if re.search(r"^\s*import\s+javax\.(persistence|validation|servlet|transaction)\b", conteudo, re.MULTILINE):
        achados.append(f"{caminho}: use jakarta.* no lugar de javax.* (Spring Boot 3 / Jakarta EE)")
    return achados


def _equilibrado(texto: str, linguagem: str) -> bool:
    """Parênteses, colchetes e chaves fecham, ignorando textos e comentários."""
    pares = {")": "(", "]": "[", "}": "{"}
    pilha: list[str] = []
    i, n = 0, len(texto)
    while i < n:
        caractere, dois = texto[i], texto[i:i + 2]
        # `//` de comentário, mas não o de `https://`.
        if dois == "//" and (i == 0 or texto[i - 1] != ":"):
            fim = texto.find("\n", i)
            i = n if fim == -1 else fim
            continue
        if dois == "/*":
            fim = texto.find("*/", i + 2)
            if fim == -1:
                return False
            i = fim + 2
            continue
        if caractere == "#" and linguagem in ("terraform", "php"):
            fim = texto.find("\n", i)
            i = n if fim == -1 else fim
            continue
        if caractere in "\"'`":
            # Em Rust o apóstrofo também marca lifetime ('a), que não fecha.
            if caractere == "'" and linguagem == "rust":
                i += 1
                continue
            fim = i + 1
            while fim < n and texto[fim] != caractere:
                if texto[fim] == "\\":
                    fim += 1
                elif texto[fim] == "\n" and caractere != "`":
                    break
                fim += 1
            i = fim + 1
            continue
        if caractere in "([{":
            pilha.append(caractere)
        elif caractere in ")]}":
            if not pilha or pilha.pop() != pares[caractere]:
                return False
        i += 1
    return not pilha


# ---------------------------------------------------------------------------
# O traço entre arquivos
# ---------------------------------------------------------------------------


def conferir_traco(arquivos: list[dict[str, str]], passos: Any) -> list[dict[str, Any]]:
    """Como `code_lab.conferir`, mas cada passo aponta para um arquivo.

    Com um arquivo só, o passo sem `arquivo` vale para ele. Com vários, passo
    sem arquivo ou com arquivo que não existe recusa o traço inteiro — pela
    mesma razão de lá: mover em silêncio ensinaria uma ordem falsa.
    """
    from app.services import code_lab

    if not arquivos or not isinstance(passos, list):
        return []
    linhas_por = {a["caminho"]: linhas_de(a["conteudo"]) for a in arquivos}
    unico = arquivos[0]["caminho"] if len(arquivos) == 1 else None
    limpos: list[dict[str, Any]] = []
    for passo in passos[: code_lab.MAXIMO_DE_PASSOS]:
        if not isinstance(passo, dict):
            return []
        arquivo = str(passo.get("arquivo") or "").strip().removeprefix("./") or unico
        if arquivo not in linhas_por:
            return []
        linhas = linhas_por[arquivo]
        try:
            numero = int(passo.get("linha"))
        except (TypeError, ValueError):
            return []
        if not 1 <= numero <= len(linhas) or not linhas[numero - 1].strip():
            return []
        acao = str(passo.get("acao") or "").strip()
        if not acao:
            return []
        limpos.append({
            "arquivo": arquivo,
            "linha": numero,
            "acao": acao,
            "estado": code_lab.estado_limpo(passo.get("estado")),
            "saida": str(passo.get("saida") or ""),
        })
    if len(limpos) < code_lab.MINIMO_DE_PASSOS or not any(p["saida"] for p in limpos):
        return []
    return limpos
