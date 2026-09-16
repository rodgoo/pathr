"""A fila diária de candidaturas: separar as vagas do dia e enviar o currículo.

## O que isto faz, e o que deliberadamente não faz

Todo dia, no servidor, as vagas que mais combinam com a pessoa entram numa
fila (`pathr_application`). Para cada uma, o app escreve uma carta de
apresentação sob medida e envia o currículo — por e-mail, quando o anúncio tem
para onde enviar; senão, abre a vaga com a carta pronta para colar e registra
que foi enviada.

O que NÃO é feito: robô que loga no Gupy ou no LinkedIn e preenche formulário
sozinho. Isso viola os termos desses sites, arrisca bloquear a conta de quem
está procurando emprego (o custo cai todo em cima da pessoa) e quebra a cada
mudança de tela deles. O ganho real — achar as vagas certas todo dia e ter
carta e currículo prontos — está aqui sem nada disso.

## Por que roda no servidor

O agendador (routers/jobs.py, chamado de hora em hora) monta a fila no
horário da manhã de cada pessoa, no fuso dela. Isso é o que faz a coisa
funcionar 24/7 com o computador de casa desligado: quem seleciona é o backend
que já está no ar, não uma máquina local.

## Onde a IA entra, e onde não entra

A ESCOLHA das vagas é determinística — o mesmo ranqueamento da tela de Vagas
(routers/vagas.vagas_da_pessoa). A IA escreve só a carta, e só quando a pessoa
vai mesmo se candidatar: gerar carta para vaga que ninguém abriu seria pagar
por texto que ninguém lê.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.services import cifra, vagas

logger = logging.getLogger(__name__)

# Quantas vagas entram na fila por dia. Cinco é o que uma pessoa consegue
# tratar com atenção num dia — vinte viram uma lista que ninguém abre.
POR_DIA = 5
MAXIMO_POR_DIA = 10

ESTADOS = ("sugerida", "enviada", "descartada")

CARTA_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "assunto": {"type": "STRING"},
        "carta": {"type": "STRING"},
    },
    "required": ["assunto", "carta"],
}

SISTEMA_DA_CARTA = """Você escreve cartas de apresentação para candidaturas a vagas de tecnologia.

A carta é da PESSOA para a empresa, em primeira pessoa, e vai junto com o
currículo dela.

Regras:
1. Escreva no idioma do anúncio: anúncio em inglês, carta em inglês; em
   português, carta em português do Brasil.
2. Entre 120 e 220 palavras, em 3 ou 4 parágrafos curtos. Ninguém lê mais que
   isso numa triagem.
3. Use só o que está no currículo e no anúncio. NUNCA invente experiência,
   empresa, tempo de casa, certificação ou número. Se o currículo não tem algo
   que a vaga pede, não mencione como se tivesse — mostre o que há de mais
   próximo.
4. Diga, concretamente: o que a pessoa faz hoje, duas ou três coisas do
   currículo que casam com o que a vaga pede (com a tecnologia pelo nome), e
   por que essa vaga interessa. Cite a empresa e o cargo pelo nome.
5. Sem bajulação ("sempre admirei a empresa"), sem clichê de template
   ("sou proativo e dinâmico"), sem promessa vazia.
6. Texto corrido, sem marcações de formatação, sem assinatura no fim (o app
   coloca o nome e o contato). Não escreva "Prezado(a) Recrutador(a)" se o
   anúncio não disser o nome de quem recebe — comece pelo motivo.
7. `assunto`: o assunto do e-mail, curto, no formato "Candidatura — <cargo>".

Responda apenas o JSON."""


def _fuso(user: dict[str, Any]) -> ZoneInfo:
    try:
        return ZoneInfo(str(user.get("timezone_name") or "America/Sao_Paulo"))
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("America/Sao_Paulo")


def hoje_de(user: dict[str, Any], agora: Optional[datetime] = None) -> date:
    """O dia de hoje no fuso da pessoa — quem está em Lisboa não recebe a fila
    de hoje ainda de madrugada."""
    return (agora or datetime.now(timezone.utc)).astimezone(_fuso(user)).date()


def _urls_ja_conhecidas(supabase: Client, user_id: str) -> set[str]:
    linhas = supabase.table("pathr_application").select("url").eq("user_id", user_id).limit(500).execute().data or []
    return {str(linha.get("url") or "") for linha in linhas}


def fila(supabase: Client, user_id: str, desde: date, limite: int = 120) -> list[dict[str, Any]]:
    """As candidaturas a partir de um dia, as mais novas primeiro."""
    return (
        supabase.table("pathr_application")
        .select("*")
        .eq("user_id", user_id)
        .gte("day", desde.isoformat())
        .order("day", desc=True)
        .order("score", desc=True)
        .limit(limite)
        .execute()
        .data
        or []
    )


def quantas_hoje(supabase: Client, user_id: str, dia: date) -> int:
    linhas = (
        supabase.table("pathr_application").select("id").eq("user_id", user_id).eq("day", dia.isoformat())
        .execute().data or []
    )
    return len(linhas)


async def montar_fila(
    supabase: Client,
    current_user: dict[str, Any],
    quantas: int = POR_DIA,
    agora: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """As vagas de hoje desta pessoa, já gravadas. Lista vazia: não havia nova.

    Usa o MESMO ranqueamento da tela de Vagas, e nunca repete uma vaga que já
    esteve na fila — inclusive uma que a pessoa descartou.
    """
    from app.routers.vagas import vagas_da_pessoa  # tarde: o router usa os serviços

    user_id = str(current_user["id"])
    dia = hoje_de(current_user, agora)
    faltam = max(0, min(quantas, MAXIMO_POR_DIA) - quantas_hoje(supabase, user_id, dia))
    if faltam == 0:
        return []

    try:
        dados = await vagas_da_pessoa(supabase, current_user)
    except Exception:  # noqa: BLE001 — uma fonte fora não pode derrubar o agendador
        logger.warning("não consegui buscar vagas para a fila de candidaturas", exc_info=True)
        return []
    if dados.get("sem_perfil"):
        return []

    conhecidas = _urls_ja_conhecidas(supabase, user_id)
    novas: list[dict[str, Any]] = []
    for vaga in dados.get("vagas") or []:
        url = str(vaga.get("url") or "").strip()
        if not url or url in conhecidas:
            continue
        conhecidas.add(url)
        novas.append({
            "user_id": user_id,
            "day": dia.isoformat(),
            "source": str(vaga.get("fonte") or "")[:20],
            "title": str(vaga.get("titulo") or "")[:300],
            "company": str(vaga.get("empresa") or "")[:200],
            "url": url[:2000],
            "location": (str(vaga.get("local") or "") or None),
            "remote": bool(vaga.get("remota")),
            "score": int(vaga.get("combina") or 0),
            "snippet": _trecho_do_anuncio(vaga),
            "status": "sugerida",
        })
        if len(novas) >= faltam:
            break
    if not novas:
        return []

    return supabase.table("pathr_application").insert(novas).execute().data or []


def _trecho_do_anuncio(vaga: dict[str, Any]) -> Optional[str]:
    """O que der para guardar do anúncio: é o material da carta, depois.

    A vaga sai do cache das fontes em horas, e algumas saem do ar. Sem isto, a
    carta seria escrita só com o título.
    """
    sobre = vaga.get("sobre")
    partes = (
        [str(sobre.get(chave) or "") for chave in ("intro", "faz", "pede", "diferenciais")]
        if isinstance(sobre, dict)
        else []
    )
    texto = "\n".join(p for p in partes if p) or str(vaga.get("resumo") or "")
    return texto[:4000] or None


def _curriculo(supabase: Client, user_id: str) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    """O currículo principal já analisado: a linha e os dados decifrados."""
    linhas = (
        supabase.table("pathr_resume").select("*").eq("user_id", user_id).eq("status", "parsed")
        .order("is_primary", desc=True).order("parsed_at", desc=True).limit(1).execute().data or []
    )
    if not linhas:
        return None, None
    dados = cifra.decifrar_json(linhas[0].get("parsed"), cifra.ctx_curriculo_dados(user_id))
    return linhas[0], (dados if isinstance(dados, dict) else None)


def _resumo_do_curriculo(dados: dict[str, Any]) -> str:
    """O currículo em texto curto para o modelo. Só o que ajuda a escrever."""
    pedacos: list[str] = []
    for chave, rotulo in (
        ("headline", "Resumo"), ("summary", "Perfil"), ("seniority", "Senioridade"),
        ("target_role", "Objetivo"), ("years_experience", "Anos de experiência"),
    ):
        valor = dados.get(chave)
        if valor:
            pedacos.append(f"{rotulo}: {valor}")
    competencias = dados.get("skills") or dados.get("technologies") or []
    nomes = [str(c.get("name") if isinstance(c, dict) else c) for c in competencias][:25]
    if nomes:
        pedacos.append("Competências: " + ", ".join(nomes))
    for experiencia in (dados.get("experiences") or dados.get("experience") or [])[:5]:
        if not isinstance(experiencia, dict):
            continue
        linha = " · ".join(
            str(experiencia.get(chave))
            for chave in ("role", "title", "company", "period", "start", "end")
            if experiencia.get(chave)
        )
        descricao = str(experiencia.get("description") or experiencia.get("summary") or "")[:300]
        pedacos.append(f"Experiência: {linha}. {descricao}".strip())
    for formacao in (dados.get("education") or [])[:3]:
        if isinstance(formacao, dict):
            pedacos.append(
                "Formação: "
                + " · ".join(str(formacao.get(c)) for c in ("degree", "course", "school", "year") if formacao.get(c))
            )
    return "\n".join(pedacos)[:4000]


async def escrever_carta(supabase: Client, current_user: dict[str, Any], linha: dict[str, Any]) -> dict[str, Any]:
    """A carta desta candidatura, escrita agora e guardada cifrada na linha."""
    user_id = str(current_user["id"])
    _, dados = _curriculo(supabase, user_id)
    if not dados:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Envie e analise seu currículo antes: é dele que sai a carta.",
        )

    anuncio = "\n".join(
        parte for parte in [
            f"Cargo: {linha.get('title')}",
            f"Empresa: {linha.get('company')}",
            f"Local: {linha.get('location') or ('Remota' if linha.get('remote') else '')}",
            str(linha.get("snippet") or ""),
        ] if parte
    )[:5000]
    em_ingles = vagas.escrita_em_ingles(f"{linha.get('title')}\n{linha.get('snippet') or ''}")
    pedido = (
        f"--- CURRÍCULO DE {str(current_user.get('name') or '').strip()} ---\n{_resumo_do_curriculo(dados)}\n\n"
        f"--- ANÚNCIO DA VAGA ---\n{anuncio}\n\n"
        f"Escreva a carta em {'inglês' if em_ingles else 'português do Brasil'}."
    )
    try:
        resultado = await generate_json(SISTEMA_DA_CARTA, pedido, CARTA_SCHEMA)
    except AiProviderError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro

    conteudo = resultado.content if isinstance(resultado.content, dict) else {}
    carta = str(conteudo.get("carta") or "").strip()
    if not carta:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA não devolveu a carta. Tente de novo.",
        )
    assunto = str(conteudo.get("assunto") or f"Candidatura — {linha.get('title')}").strip()[:200]
    atualizada = (
        supabase.table("pathr_application")
        .update({"letter": cifra.cifrar(carta[:6000], cifra.ctx_carta(user_id)), "subject": assunto})
        .eq("id", str(linha["id"]))
        .eq("user_id", user_id)
        .execute()
        .data
    )
    return (atualizada or [{**linha, "letter": carta, "subject": assunto}])[0]


def para_api(linha: dict[str, Any], user_id: str) -> dict[str, Any]:
    """A linha como a tela precisa dela, com a carta já decifrada."""
    return {
        "id": str(linha["id"]),
        "day": linha.get("day"),
        "source": linha.get("source") or "",
        "title": linha.get("title") or "",
        "company": linha.get("company") or "",
        "url": linha.get("url") or "",
        "location": linha.get("location"),
        "remote": bool(linha.get("remote")),
        "score": int(linha.get("score") or 0),
        "snippet": (linha.get("snippet") or "")[:600] or None,
        "letter": cifra.decifrar(linha.get("letter"), cifra.ctx_carta(user_id)),
        "subject": linha.get("subject"),
        "to_email": linha.get("to_email"),
        "status": linha.get("status") or "sugerida",
        "sent_at": linha.get("sent_at"),
        "created_at": linha.get("created_at"),
    }


def uma(supabase: Client, user_id: str, application_id: str) -> dict[str, Any]:
    linhas = (
        supabase.table("pathr_application").select("*")
        .eq("id", application_id).eq("user_id", user_id).limit(1).execute().data or []
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura não encontrada.")
    return linhas[0]


def marcar(
    supabase: Client,
    user_id: str,
    application_id: str,
    novo_status: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if novo_status not in ESTADOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Situação inválida.")
    campos: dict[str, Any] = {"status": novo_status, **(extra or {})}
    if novo_status == "enviada":
        campos["sent_at"] = datetime.now(timezone.utc).isoformat()
    linhas = (
        supabase.table("pathr_application").update(campos)
        .eq("id", application_id).eq("user_id", user_id).execute().data
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura não encontrada.")
    return linhas[0]
