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

import base64
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.services import cifra, vagas
from app.services import email as emails

logger = logging.getLogger(__name__)

# Quantas vagas entram na fila por dia. Cinco é o que uma pessoa consegue
# tratar com atenção num dia — vinte viram uma lista que ninguém abre.
POR_DIA = 5
MAXIMO_POR_DIA = 10

ESTADOS = ("sugerida", "enviada", "descartada")

# --- envio automático ------------------------------------------------------
#
# O app só envia sozinho o que consegue enviar DE VERDADE: vaga cujo anúncio
# traz um e-mail de contato. O resto (Gupy, LinkedIn, formulário da empresa)
# pede login e faz perguntas próprias — lá quem se candidata é a pessoa, com as
# respostas prontas que este módulo escreve.
#
# O corte por nota existe por reputação, não por economia: currículo disparado
# para tudo que aparece é o que faz recrutador parar de ler. Abaixo do corte, a
# vaga fica na fila para a pessoa decidir.
LIMIAR_AUTOMATICO = 70
MAXIMO_AUTOMATICO = 5

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Caixas que não recebem candidatura: mandar para elas é jogar o currículo fora.
_EMAIL_PROIBIDO = re.compile(r"(no[-_.]?reply|nao[-_.]?responda|donotreply|example\.(com|org)|sentry)", re.IGNORECASE)
# Com mais de um endereço no anúncio, o de recrutamento é o certo.
_EMAIL_DE_VAGA = re.compile(r"(vaga|rh|recrut|talent|selecao|curricul|\bcv\b|job|carreira|career|people)", re.IGNORECASE)

# Provedor de e-mail pessoal. Um endereço destes no anúncio quase nunca é "a
# empresa": é a caixa de uma pessoa — às vezes de outro candidato, que colou o
# próprio e-mail num comentário. Currículo tem nome, telefone e histórico;
# mandar para a caixa errada é vazamento, e não tem volta. Nunca no automático.
_PROVEDOR_PESSOAL = frozenset(
    """
    gmail.com googlemail.com hotmail.com hotmail.com.br outlook.com outlook.com.br live.com msn.com
    yahoo.com yahoo.com.br ymail.com icloud.com me.com proton.me protonmail.com pm.me tutanota.com
    bol.com.br uol.com.br terra.com.br ig.com.br globo.com r7.com zipmail.com.br aol.com gmx.com
    """.split()
)


def _dominio(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def email_do_anuncio(texto: Optional[str]) -> Optional[str]:
    """O e-mail que o anúncio dá como contato, se der algum.

    A maioria das vagas não dá — manda aplicar no site. Quando dá, costuma ser
    em "envie seu currículo para vagas@empresa.com".

    Isto é SUGESTÃO para a tela: a pessoa vê o endereço, confere e decide. O
    que o envio automático aceita é mais estreito — ver `email_confiavel`.
    """
    candidatos = [e for e in _EMAIL.findall(texto or "") if not _EMAIL_PROIBIDO.search(e)]
    if not candidatos:
        return None
    de_vaga = [e for e in candidatos if _EMAIL_DE_VAGA.search(e)]
    return (de_vaga or candidatos)[0][:200]


def email_confiavel(email: Optional[str], empresa: Optional[str], url: Optional[str]) -> bool:
    """Dá para mandar o currículo para cá SEM a pessoa conferir?

    O extrator acima acerta na maioria, e erra de formas caras: o anúncio cita
    o e-mail de um fornecedor, de um jornalista, de outro candidato. No envio
    manual isso não é problema — a pessoa lê o endereço antes de clicar. No
    automático não há ninguém lendo, então o critério aqui é duro de propósito,
    e o que não passa continua na fila esperando um clique:

    1. nada de provedor pessoal (gmail, hotmail, …): não é caixa de empresa;
    2. o nome da caixa precisa ser de recrutamento (vagas@, rh@, jobs@…), OU
    3. o domínio precisa ser o do anúncio ou o da empresa — aí é a empresa
       falando de si mesma, ainda que a caixa se chame "contato".
    """
    if not email or "@" not in email:
        return False
    dominio = _dominio(email)
    if dominio in _PROVEDOR_PESSOAL:
        return False
    if _EMAIL_DE_VAGA.search(email):
        return True

    # O domínio do anúncio (o host da URL, sem "www.") e o nome da empresa sem
    # espaço nem acento: "Empresa Boa" casa com "empresaboa.com.br".
    host = ""
    if url:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    nome = re.sub(r"[^a-z0-9]", "", (empresa or "").lower())
    raiz = dominio.split(".")[0]
    if host and (dominio == host or host.endswith(f".{dominio}") or dominio.endswith(f".{host}")):
        return True
    return bool(nome) and len(nome) >= 4 and (raiz == nome or nome in dominio.replace(".", ""))

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
            "to_email": email_do_anuncio(_trecho_do_anuncio(vaga)),
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


def curriculo_em_anexo(supabase: Client, user_id: str) -> tuple[str, str]:
    """O arquivo do currículo principal, em base64 para o anexo do e-mail."""
    from app.routers.resumes import _load_file  # tarde: o router usa os serviços

    linhas = (
        supabase.table("pathr_resume").select("*").eq("user_id", user_id)
        .order("is_primary", desc=True).order("created_at", desc=True).limit(1).execute().data or []
    )
    if not linhas:
        return "", ""
    conteudo = _load_file(supabase, linhas[0])
    if not conteudo:
        return "", ""
    return str(linhas[0].get("filename") or "curriculo.pdf")[:120], base64.b64encode(conteudo).decode()


async def enviar_automaticamente(
    supabase: Client,
    current_user: dict[str, Any],
    linhas: list[dict[str, Any]],
    limite: int = MAXIMO_AUTOMATICO,
) -> list[dict[str, Any]]:
    """Envia, sem perguntar, as vagas que dá para enviar por e-mail.

    Só entra vaga com endereço de contato no anúncio e nota acima do corte. O
    que falhar (IA fora, e-mail recusado) fica como estava, na fila, para a
    pessoa resolver à mão — nunca é marcado como enviado sem ter saído.
    """
    user_id = str(current_user["id"])
    remetente = str(current_user.get("email") or "")
    if not remetente:
        return []
    anexo_nome, anexo = curriculo_em_anexo(supabase, user_id)
    if not anexo:
        return []

    enviadas: list[dict[str, Any]] = []
    for linha in linhas:
        if len(enviadas) >= limite:
            break
        destino = str(linha.get("to_email") or "").strip()
        if not destino or int(linha.get("score") or 0) < LIMIAR_AUTOMATICO:
            continue
        # O endereço veio do texto do anúncio: só sai sozinho se for mesmo da
        # empresa. O resto fica na fila, com o endereço à vista para a pessoa
        # conferir antes de mandar.
        if not email_confiavel(destino, linha.get("company"), linha.get("url")):
            logger.info("candidatura %s: e-mail do anúncio não é confiável para envio automático", linha.get("id"))
            continue
        try:
            com_carta = await escrever_carta(supabase, current_user, linha)
        except HTTPException:
            logger.info("carta não saiu para a candidatura %s; fica para a pessoa", linha.get("id"))
            continue
        carta = para_api(com_carta, user_id).get("letter") or ""
        if not carta:
            continue
        saiu = emails.send_application(
            to_email=destino,
            subject=str(com_carta.get("subject") or f"Candidatura — {linha.get('title')}")[:200],
            carta=carta,
            candidato_nome=str(current_user.get("name") or ""),
            candidato_email=remetente,
            anexo_nome=anexo_nome,
            anexo_base64=anexo,
        )
        if saiu:
            enviadas.append(marcar(supabase, user_id, str(linha["id"]), "enviada", {"to_email": destino}))
    return enviadas


# --- respostas do formulário da vaga ---------------------------------------

RESPOSTAS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "respostas": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"pergunta": {"type": "STRING"}, "resposta": {"type": "STRING"}},
                "required": ["pergunta", "resposta"],
            },
        }
    },
    "required": ["respostas"],
}

SISTEMA_DAS_RESPOSTAS = """Você prepara as respostas que a pessoa vai colar no formulário de candidatura.

Escreva na primeira pessoa, como ela responderia — o texto vai direto no campo
do formulário da empresa.

Regras:
1. Responda estas perguntas, nesta ordem, adaptando ao que a vaga pede:
   "Por que você quer esta vaga?", "Pretensão salarial", "Disponibilidade para
   início", "Nível de inglês", "Conte uma experiência relevante para esta vaga",
   "Modelo de trabalho". Se o anúncio deixar clara outra pergunta importante,
   acrescente no fim (no máximo 8 no total).
2. Cada resposta entre 15 e 70 palavras, direta, sem rodeio e sem clichê.
3. Use SÓ o currículo e os dados do perfil. NUNCA invente experiência, número,
   certificação, salário ou nível de idioma.
4. Pretensão salarial e disponibilidade: use exatamente o que o perfil informa.
   Se o perfil não informar, escreva uma resposta honesta que devolva a pergunta
   ("aberto a conversar sobre a faixa da vaga") e não invente valor.
5. Nível de inglês: use o nível medido no perfil, se houver; senão, diga o que o
   currículo sustenta, sem inflar.
6. Texto simples, sem marcação, sem saudação e sem assinatura.

Responda apenas o JSON."""


async def escrever_respostas(
    supabase: Client, current_user: dict[str, Any], linha: dict[str, Any]
) -> dict[str, Any]:
    """As respostas prontas para o formulário desta vaga, guardadas na linha.

    O app escreve; quem responde continua sendo a pessoa. É a diferença entre
    adiantar o trabalho e responder um recrutador no lugar dela.
    """
    user_id = str(current_user["id"])
    _, dados = _curriculo(supabase, user_id)
    if not dados:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Envie e analise seu currículo antes: é dele que saem as respostas.",
        )
    perfil = (
        supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data or [{}]
    )[0]
    ingles = (
        supabase.table("pathr_english_profile").select("cefr_level").eq("user_id", user_id)
        .eq("language", "en").limit(1).execute().data or [{}]
    )[0].get("cefr_level")

    pedido = "\n".join([
        f"--- CURRÍCULO DE {str(current_user.get('name') or '').strip()} ---",
        _resumo_do_curriculo(dados),
        "",
        "--- PERFIL ---",
        f"Pretensão salarial: {perfil.get('salary_expectation') or 'não informada'}",
        f"Disponibilidade: {perfil.get('availability') or 'não informada'}",
        f"Nível de inglês medido: {ingles or 'não medido'}",
        f"Cidade: {perfil.get('city') or '—'}/{perfil.get('state') or '—'}",
        f"Objetivo: {perfil.get('target_role') or '—'}",
        "",
        "--- ANÚNCIO DA VAGA ---",
        f"Cargo: {linha.get('title')}",
        f"Empresa: {linha.get('company')}",
        str(linha.get("snippet") or "")[:4000],
    ])
    try:
        resultado = await generate_json(SISTEMA_DAS_RESPOSTAS, pedido, RESPOSTAS_SCHEMA)
    except AiProviderError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro

    conteudo = resultado.content if isinstance(resultado.content, dict) else {}
    respostas = [
        {
            "pergunta": str(item.get("pergunta") or "").strip()[:200],
            "resposta": str(item.get("resposta") or "").strip()[:1200],
        }
        for item in (conteudo.get("respostas") or [])
        if isinstance(item, dict) and item.get("pergunta") and item.get("resposta")
    ][:8]
    if not respostas:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA não devolveu as respostas. Tente de novo.",
        )
    atualizada = (
        supabase.table("pathr_application").update({"answers": respostas})
        .eq("id", str(linha["id"])).eq("user_id", user_id).execute().data
    )
    return (atualizada or [{**linha, "answers": respostas}])[0]


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
        "answers": linha.get("answers") or [],
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
