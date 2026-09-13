"""Vagas reais para o perfil da pessoa, e o que falta para cada uma.

A regra (fontes, compatibilidade, análise) mora em services/vagas.py. Aqui se
junta o que o serviço precisa saber da pessoa: competências, objetivo,
senioridade, estado e o roadmap.

O prefixo é `/vagas` e não `/jobs`: `/jobs` já é o disparo agendado de
e-mails (routers/jobs.py).
"""

import asyncio
import hashlib
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.routers.courses import _slugs_do_roadmap
from app.routers.tags import _objetivo_de, list_mine
from app.services import reader
from app.services import vagas as servico
from app.services.tag_catalog import _alias_keys, slugify

router = APIRouter(prefix="/vagas", tags=["vagas"])

# A descrição que a fonte devolve é curta demais para analisar quando é só um
# trecho (Adzuna, resultado de busca). Abaixo disto, lemos a página.
_TEXTO_MINIMO = 400

# Os requisitos que a IA extraiu, por texto do anúncio. Não dependem de quem
# pergunta — duas pessoas analisando a mesma vaga pagam uma chamada só.
_requisitos_por_texto: dict[str, dict[str, Any]] = {}


def _perfil(supabase: Client, user_id: str) -> dict[str, Any]:
    linhas = supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data
    return (linhas or [{}])[0]


def _catalogo(supabase: Client) -> list[dict[str, Any]]:
    return supabase.table("pathr_tag").select("id,slug,name,category,aliases").execute().data or []


def _minhas_por_slug(minhas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(tag["slug"]): tag for tag in minhas}


def _nivel_de_ingles(supabase: Client, user_id: str) -> Optional[str]:
    """O CEFR medido no módulo de Idiomas. Só lê: quem nunca abriu o módulo
    não ganha perfil de idioma criado por ter olhado vagas."""
    linhas = (
        supabase.table("pathr_english_profile")
        .select("cefr_level")
        .eq("user_id", user_id)
        .eq("language", "en")
        .limit(1)
        .execute()
        .data
        or []
    )
    return (linhas[0].get("cefr_level") if linhas else None) or None


def _senioridade(perfil: dict[str, Any]) -> Optional[str]:
    valor = str(perfil.get("seniority") or "").lower().replace("ê", "e").replace("ú", "u")
    return next((nivel for nivel in ("junior", "pleno", "senior") if nivel in valor), None)


@router.get("")
async def listar_vagas(
    q: str = "",
    remotas: bool = False,
    alcance: str = Query(default="todas", pattern="^(todas|nacionais|internacionais)$"),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Vagas das fontes confiáveis, ordenadas pelo quanto combinam com a pessoa.

    Sem `q`, os termos saem das competências (metas primeiro) e do objetivo.
    """
    user_id = str(current_user["id"])
    minhas = list_mine(current_user, supabase)
    perfil = _perfil(supabase, user_id)
    termos = [q.strip()[:60]] if q.strip() else servico.termos_de_busca(minhas, _objetivo_de(perfil))
    if not termos:
        return {"termos": [], "vagas": [], "fontes": {}, "sem_perfil": True}

    encontradas, fontes = await servico.buscar(termos)
    nivel_ingles = _nivel_de_ingles(supabase, user_id)
    lista = servico.para_tela(
        encontradas,
        _catalogo(supabase),
        _minhas_por_slug(minhas),
        senioridade=_senioridade(perfil),
        estado_uf=perfil.get("state"),
        so_remotas=remotas,
        alcance=alcance,
        nivel_ingles=nivel_ingles,
    )
    return {
        "termos": termos,
        "vagas": lista,
        "fontes": fontes,
        "sem_perfil": False,
        "nivel_ingles": nivel_ingles,
    }


class AnaliseVaga(BaseModel):
    # Um dos três: a vaga da listagem, o link de uma vaga, ou o texto colado.
    vaga_id: Optional[str] = Field(default=None, max_length=80)
    url: Optional[str] = Field(default=None, max_length=2000)
    texto: Optional[str] = Field(default=None, max_length=20000)


async def _ler_pagina(url: str) -> str:
    try:
        leitura = await asyncio.to_thread(reader.ler, url)
    except reader.LeituraIndisponivel as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{erro.motivo} Cole o texto do anúncio para analisar.",
        ) from erro
    return servico.texto_puro(leitura.html)


@router.post("/analise")
async def analisar_vaga(
    payload: AnaliseVaga,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O que a vaga pede, o que a pessoa já tem, e o caminho para cada lacuna."""
    texto = (payload.texto or "").strip()
    url = (payload.url or "").strip() or None
    titulo = empresa = None

    if payload.vaga_id:
        guardada = servico.vaga_guardada(payload.vaga_id)
        if guardada:
            texto, url = guardada.descricao, guardada.url
            titulo, empresa = guardada.titulo, guardada.empresa
    if len(texto) < _TEXTO_MINIMO and url:
        lida = await _ler_pagina(url)
        if len(lida) > len(texto):
            texto = lida
    if len(texto) < 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não há texto suficiente da vaga para analisar. Cole o anúncio completo.",
        )

    chave = hashlib.sha256(texto.encode()).hexdigest()
    extraido = _requisitos_por_texto.get(chave)
    usou_ia = True
    if extraido is None:
        try:
            resultado = await generate_json(
                servico.ANALISE_SYSTEM, servico.pedido_de_analise(texto), servico.ANALISE_SCHEMA
            )
            extraido = resultado.content or {}
            if extraido.get("requisitos"):
                _requisitos_por_texto[chave] = extraido
        except AiProviderError:
            # Sem IA a análise continua: as tecnologias citadas no texto, todas
            # como obrigatórias. Menos fina, mas não some.
            extraido = {}
            usou_ia = False

    user_id = str(current_user["id"])
    linhas = _catalogo(supabase)
    por_chave: dict[str, dict[str, Any]] = {}
    for tag in linhas:
        for chave_da_tag in _alias_keys(tag):
            por_chave.setdefault(chave_da_tag, tag)

    analise = servico.analisar(
        [r for r in (extraido.get("requisitos") or []) if isinstance(r, dict)],
        texto,
        linhas,
        lambda nome: por_chave.get(slugify(nome)),
        _minhas_por_slug(list_mine(current_user, supabase)),
        set(_slugs_do_roadmap(supabase, user_id)),
        nivel_ingles=_nivel_de_ingles(supabase, user_id),
    )
    return {
        "titulo": titulo or str(extraido.get("titulo") or "").strip() or "Vaga analisada",
        "empresa": empresa or str(extraido.get("empresa") or "").strip() or None,
        "senioridade": str(extraido.get("senioridade") or "").strip() or None,
        "resumo": str(extraido.get("resumo") or "").strip() or None,
        "url": url,
        "usou_ia": usou_ia and bool(extraido),
        **analise,
    }
