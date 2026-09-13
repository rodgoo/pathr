"""Leitura do currículo: arquivo -> competências que o app entende.

O objetivo não é transcrever o currículo, é responder uma pergunta: quais
tecnologias esta pessoa domina, e quão bem? O resto (cargo, anos, projetos)
entra porque calibra a resposta — "React" num estágio de seis meses e "React"
em três anos liderando frontend não são a mesma proficiência.

Dois caminhos, nesta ordem:

1. **Arquivo direto para o modelo** (`generate_json_with_media`). Currículo é
   um documento visual: duas colunas, barrinhas de proficiência, tabela de
   skills. A extração de texto embaralha tudo isso — a coluna lateral se
   intercala com a principal e "React ████░ Avançado" vira "React". Mandar o
   PDF inteiro preserva o layout e ainda resolve o PDF escaneado de graça,
   via OCR do próprio modelo.

2. **Texto extraído** (`generate_json`), quando o formato não é PDF ou quando
   nenhum provedor com visão está configurado. Perde layout, mas usa a
   rotação inteira de provedores em vez de só o Gemini.

A proficiência devolvida é uma ESTIMATIVA e entra em `pathr_user_tag` com
`confidence` baixa e `source='cv'`: o currículo diz o que a pessoa escreveu
sobre si. Um quiz respondido depois sobe essa confiança. É por isso que a
tela de revisão existe — a pessoa corrige antes de o roadmap ser gerado.
"""

from typing import Any, Optional

from app.ai_providers import AiResult, generate_json, generate_json_with_media
from app.services.text_extract import Extraction

# O dialeto de schema do próprio Gemini (tipos em maiúsculas). Só ele usa;
# os demais provedores recebem modo JSON solto mais o texto do prompt, que
# descreve o mesmo formato.
RESUME_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "nome": {"type": "STRING"},
        "email": {"type": "STRING"},
        "telefone": {"type": "STRING"},
        "cidade": {"type": "STRING"},
        "cargo_atual": {"type": "STRING"},
        "senioridade": {"type": "STRING"},
        "anos_experiencia": {"type": "NUMBER"},
        "resumo": {"type": "STRING"},
        "linkedin": {"type": "STRING"},
        "github": {"type": "STRING"},
        "tecnologias": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nome": {"type": "STRING"},
                    "categoria": {"type": "STRING"},
                    "proficiencia": {"type": "INTEGER"},
                    "anos": {"type": "NUMBER"},
                    "evidencia": {"type": "STRING"},
                },
                "required": ["nome", "proficiencia"],
            },
        },
        "experiencias": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "empresa": {"type": "STRING"},
                    "cargo": {"type": "STRING"},
                    "periodo": {"type": "STRING"},
                    "descricao": {"type": "STRING"},
                    "tecnologias": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "formacao": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "instituicao": {"type": "STRING"},
                    "curso": {"type": "STRING"},
                    "periodo": {"type": "STRING"},
                },
            },
        },
        "idiomas": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "idioma": {"type": "STRING"},
                    "nivel": {"type": "STRING"},
                },
            },
        },
        "projetos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nome": {"type": "STRING"},
                    "descricao": {"type": "STRING"},
                    "tecnologias": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
    },
    "required": ["tecnologias"],
}


SYSTEM_PROMPT = """Você lê currículos de profissionais de tecnologia e extrai, em JSON, o que a pessoa sabe fazer.

Regras que não podem ser quebradas:

1. Extraia SOMENTE o que está no documento. Nunca invente tecnologia, empresa,
   data ou nível. Campo sem informação vem como string vazia ou lista vazia.
2. `proficiencia` é um inteiro de 0 a 5, estimado assim:
   0 = citada como interesse ou "desejável", sem uso comprovado
   1 = contato inicial, curso ou projeto pessoal pequeno
   2 = usa com apoio de documentação; menos de 1 ano em projeto real
   3 = autônomo; 1 a 3 anos, entregou em produção
   4 = referência no time; mais de 3 anos ou liderança técnica no assunto
   5 = especialista reconhecido; palestra, publica ou define arquitetura
   Na dúvida entre dois níveis, escolha o MENOR. Superestimar faz o plano
   pular fundamentos que a pessoa não tem.
3. `evidencia` é a frase do currículo que sustenta a nota, copiada literalmente
   e curta. Se não houver frase, deixe vazio — isso é o que permite ao usuário
   conferir a estimativa.
4. Normalize o nome da tecnologia para a forma canônica do mercado:
   "react.js"/"ReactJS" -> "React"; "postgres"/"psql" -> "PostgreSQL";
   "node"/"nodejs" -> "Node.js"; "js" -> "JavaScript"; "k8s" -> "Kubernetes".
   Não traduza nomes próprios de tecnologia.
5. `categoria` deve ser uma destas: linguagem, framework, banco, cloud, devops,
   dados, ia, arquitetura, testes, seguranca, mobile, frontend, backend,
   ferramenta, metodologia, soft-skill, idioma, dominio (setor de negócio em que
   a pessoa trabalhou: bancário e financeiro, varejo, saúde, e-commerce...).
6. Não inclua como tecnologia: nome de empresa, cargo, cidade, faculdade, nem
   habilidade genérica ("proatividade") — exceto se for claramente uma
   soft-skill relevante, e aí use categoria "soft-skill".
7. `anos_experiencia` é o tempo TOTAL na área de tecnologia, somando os
   períodos profissionais. Estágio conta pela metade. Sem datas, deixe 0.
8. Responda apenas o JSON, sem comentário ou cerca de código."""

USER_PROMPT_MEDIA = """Este é o currículo de uma pessoa. Leia o documento inteiro, inclusive colunas laterais, tabelas e barras de nível, e devolva o JSON no formato combinado.

Se o documento estiver digitalizado (imagem sem texto), leia visualmente."""

USER_PROMPT_TEXT = """Texto extraído de um currículo. A extração pode ter embaralhado a ordem de colunas e perdido barras de nível — considere isso e não invente o que não está escrito.

--- INÍCIO DO CURRÍCULO ---
{text}
--- FIM DO CURRÍCULO ---"""

# Limite do texto mandado ao modelo. Um currículo real cabe folgado em 20 mil
# caracteres; passar disso é quase sempre um PDF com lixo de extração, e
# mandar tudo só gasta cota e piora a resposta.
_MAX_TEXT_CHARS = 20_000


def _coerce_proficiency(raw: Any) -> int:
    """A escala é 0..5 e é usada como índice em vários lugares. Qualquer coisa
    fora disso vira 0, que é o valor seguro: significa "a aprender" e faz o
    plano cobrir o assunto do começo."""
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, value))


def _clean_technologies(raw: Any) -> list[dict[str, Any]]:
    """Filtra e normaliza a lista de tecnologias vinda do modelo.

    Revalidar aqui é o que permite usar modo JSON solto nos provedores que não
    são o Gemini: a garantia deles é "JSON válido", não "este formato".
    """
    if not isinstance(raw, list):
        return []

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nome") or "").strip()
        if not name or len(name) > 60:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "nome": name,
                "categoria": str(item.get("categoria") or "").strip().lower() or "ferramenta",
                "proficiencia": _coerce_proficiency(item.get("proficiencia")),
                "anos": _coerce_years(item.get("anos")),
                "evidencia": str(item.get("evidencia") or "").strip()[:300],
            }
        )
    return cleaned


def _coerce_years(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    # 60 anos de carreira em uma tecnologia é erro de leitura, não currículo.
    return max(0.0, min(60.0, round(value, 1)))


def _text_field(raw: Any, limit: int = 200) -> str:
    return str(raw or "").strip()[:limit]


def _list_field(raw: Any, limit: int = 20) -> list[Any]:
    return raw[:limit] if isinstance(raw, list) else []


def normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    """O que o resto do app pode confiar, vindo de uma resposta que pode ter
    qualquer forma."""
    return {
        "nome": _text_field(parsed.get("nome")),
        "email": _text_field(parsed.get("email")),
        "telefone": _text_field(parsed.get("telefone"), 40),
        "cidade": _text_field(parsed.get("cidade")),
        "cargo_atual": _text_field(parsed.get("cargo_atual")),
        "senioridade": _text_field(parsed.get("senioridade"), 40),
        "anos_experiencia": _coerce_years(parsed.get("anos_experiencia")),
        "resumo": _text_field(parsed.get("resumo"), 1200),
        "linkedin": _text_field(parsed.get("linkedin"), 300),
        "github": _text_field(parsed.get("github"), 300),
        "tecnologias": _clean_technologies(parsed.get("tecnologias")),
        "experiencias": _list_field(parsed.get("experiencias")),
        "formacao": _list_field(parsed.get("formacao"), 10),
        "idiomas": _list_field(parsed.get("idiomas"), 10),
        "projetos": _list_field(parsed.get("projetos"), 15),
    }


# Formatos que o Gemini aceita como mídia inline. DOCX/ODT/RTF não estão aqui
# — para eles o caminho é sempre o texto extraído.
_MEDIA_MIME = {"pdf": "application/pdf"}


async def parse_resume(
    *,
    data: bytes,
    kind: str,
    extraction: Extraction,
    prefer_media: bool = True,
) -> tuple[dict[str, Any], AiResult]:
    """Lê o currículo e devolve (dados normalizados, metadados da chamada).

    Levanta `AiProviderError` se todos os provedores falharem, e `ValueError`
    se não houver nem arquivo que o modelo leia nem texto extraído — nesse
    caso não há o que mandar, e tentar seria gastar cota à toa.
    """
    mime = _MEDIA_MIME.get(kind)
    has_text = bool(extraction.text.strip())

    if prefer_media and mime:
        result = await generate_json_with_media(
            SYSTEM_PROMPT,
            USER_PROMPT_MEDIA,
            data,
            mime,
            RESUME_SCHEMA,
        )
        return normalize(result.content), result

    if not has_text:
        raise ValueError(
            extraction.note or "não foi possível ler o conteúdo do arquivo"
        )

    result = await generate_json(
        SYSTEM_PROMPT,
        USER_PROMPT_TEXT.format(text=extraction.text[:_MAX_TEXT_CHARS]),
        RESUME_SCHEMA,
    )
    return normalize(result.content), result


async def parse_resume_with_fallback(
    *,
    data: bytes,
    kind: str,
    extraction: Extraction,
) -> tuple[dict[str, Any], AiResult]:
    """`parse_resume` com a segunda tentativa que faz o recurso não morrer por
    falta de uma chave.

    O caminho de mídia depende do Gemini (único provedor com visão
    configurado). Se ele estiver sem cota, o PDF ainda pode ser lido pelo
    texto extraído em qualquer um dos outros quatro provedores — pior
    qualidade, mas responder pior é melhor que não responder.
    """
    from app.ai_providers import AiProviderError

    try:
        return await parse_resume(data=data, kind=kind, extraction=extraction)
    except AiProviderError:
        if not extraction.text.strip():
            raise
        return await parse_resume(
            data=data, kind=kind, extraction=extraction, prefer_media=False
        )
