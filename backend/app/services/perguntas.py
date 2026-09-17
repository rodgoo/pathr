"""As perguntas dos formulários de vaga, e como uma resposta serve para várias.

## O problema

Cada site pergunta a mesma coisa com um nome diferente: "Nome completo", "Nome",
"Full name"; "Currículo", "CV", "Resume"; "Endereço", "Logradouro"; "Pretensão
salarial", "Salary expectation", "Remuneração desejada". Tratadas como
perguntas distintas, a pessoa responderia as mesmas cinco coisas em cada vaga —
que é exatamente o trabalho que ela quer parar de fazer.

## Como isto resolve

Toda pergunta vira uma CHAVE canônica (`chave()`): as variações acima caem na
mesma, e a resposta guardada no banco (`pathr_answer_bank`) vale para todas.
Pergunta que não casa com nenhum sinônimo conhecido vira uma chave própria,
derivada do texto — ela também é reaproveitada, só que apenas quando a mesma
pergunta reaparecer.

## O que o app NÃO responde sozinho

Duas famílias ficam sempre com a pessoa, mesmo havendo resposta guardada:

- **dados sensíveis** (gênero, raça, deficiência, orientação): são opcionais por
  lei, e a resposta é escolha de quem se candidata, não do app;
- **pergunta aberta sobre a vaga** ("por que você quer trabalhar aqui?"): a
  resposta muda a cada empresa, e reaproveitar a de ontem é como mandar carta
  em branco — o recrutador percebe.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Optional

# Cada entrada: a chave canônica e as formas em que a pergunta aparece. Basta a
# forma estar CONTIDA na pergunta normalizada ("qual o seu nome completo?" casa
# com "nome completo").
_SINONIMOS: dict[str, tuple[str, ...]] = {
    "nome": ("nome completo", "nome e sobrenome", "full name", "your name", "nombre completo", "nome"),
    "email": ("e mail", "email", "correio eletronico", "endereco de e mail"),
    "telefone": ("telefone", "celular", "whatsapp", "phone", "mobile", "contato telefonico"),
    "endereco": ("endereco", "logradouro", "rua", "address", "street"),
    "cidade": ("cidade", "municipio", "city", "onde voce mora", "localidade"),
    "estado": ("estado", "uf", "state", "provincia"),
    "pais": ("pais", "country"),
    "cep": ("cep", "codigo postal", "zip", "postal code"),
    "linkedin": ("linkedin", "perfil do linkedin"),
    "github": ("github", "portfolio de codigo", "repositorio"),
    "portfolio": ("portfolio", "site pessoal", "website"),
    "curriculo": ("curriculo", "curriculum", "cv", "resume", "anexe seu curriculo", "upload do curriculo"),
    "carta": ("carta de apresentacao", "cover letter", "carta de motivacao"),
    "pretensao": (
        "pretensao salarial", "pretensao", "remuneracao desejada", "salario desejado",
        "salary expectation", "expected salary", "quanto voce espera receber",
    ),
    "salario_atual": ("salario atual", "remuneracao atual", "current salary"),
    "disponibilidade": (
        "disponibilidade", "quando pode comecar", "aviso previo", "notice period",
        "start date", "data de inicio",
    ),
    "modelo_trabalho": ("modelo de trabalho", "remoto", "hibrido", "presencial", "work model", "onsite"),
    "ingles": ("ingles", "english level", "nivel de ingles", "fluencia em ingles"),
    "outros_idiomas": ("outros idiomas", "idiomas", "languages"),
    "experiencia_anos": ("anos de experiencia", "tempo de experiencia", "years of experience"),
    "escolaridade": ("escolaridade", "formacao academica", "education", "graduacao"),
    "autorizacao": ("autorizacao para trabalhar", "work authorization", "visto", "visa", "elegivel para trabalhar"),
    "mudanca": ("disponibilidade para mudanca", "willing to relocate", "mudar de cidade"),
    "referencias": ("referencias", "references"),
}

# Nunca respondidas pelo app: a escolha é da pessoa, sempre.
SENSIVEIS: dict[str, tuple[str, ...]] = {
    "genero": ("genero", "gender", "sexo"),
    "raca": ("raca", "cor", "etnia", "race", "ethnicity"),
    "deficiencia": ("deficiencia", "pcd", "disability", "laudo"),
    "orientacao": ("orientacao sexual", "sexual orientation", "lgbt"),
    "idade": ("idade", "data de nascimento", "age", "birth date"),
}

# Abertas sobre a vaga: a resposta é daquela empresa, não serve para a próxima.
_ABERTAS = (
    "por que", "porque", "why do you", "why are you", "o que te motiva",
    "conte sobre", "descreva", "tell us", "fale sobre", "como voce",
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).split())


def e_sensivel(pergunta: str) -> bool:
    limpo = _normalizar(pergunta)
    return any(forma in limpo for formas in SENSIVEIS.values() for forma in formas)


def e_aberta(pergunta: str) -> bool:
    limpo = _normalizar(pergunta)
    return any(limpo.startswith(inicio) or f" {inicio}" in limpo for inicio in _ABERTAS)


def chave(pergunta: str) -> str:
    """A chave canônica da pergunta — o que faz "CV" e "Currículo" serem uma só.

    Sem sinônimo conhecido, a chave sai do próprio texto ("livre:...") e ainda
    assim reaproveita: a mesma pergunta, no mesmo site ou em outro, encontra a
    resposta de antes.
    """
    limpo = _normalizar(pergunta)
    if not limpo:
        return "livre:vazio"
    for canonica, formas in SENSIVEIS.items():
        if any(forma in limpo for forma in formas):
            return f"sensivel:{canonica}"
    # A forma mais longa primeiro: "nome completo" ganha de "nome", e
    # "salario atual" não é confundido com "pretensao".
    melhor: Optional[tuple[int, str]] = None
    for canonica, formas in _SINONIMOS.items():
        for forma in formas:
            if forma in limpo and (melhor is None or len(forma) > melhor[0]):
                melhor = (len(forma), canonica)
    if melhor:
        return melhor[1]
    return "livre:" + re.sub(r"\s+", "-", limpo)[:60]


def reutilizavel(pergunta: str) -> bool:
    """A resposta desta pergunta serve para a próxima vaga?

    Dado pessoal serve (o telefone é o mesmo em toda vaga). Pergunta aberta
    sobre a empresa, não. Sensível também não — nem se guarda.
    """
    return not e_sensivel(pergunta) and not e_aberta(pergunta)


def do_perfil(perfil: dict[str, Any], user: dict[str, Any], curriculo: Optional[dict[str, Any]]) -> dict[str, str]:
    """O que o app já sabe da pessoa, pronto para responder formulário.

    Sai do perfil e do currículo lido — nada aqui é inventado, e o que não
    existe simplesmente não entra.
    """
    dados = curriculo or {}
    respostas = {
        "nome": str(user.get("name") or "").strip(),
        "email": str(user.get("email") or "").strip(),
        "cidade": str(perfil.get("city") or "").strip(),
        "estado": str(perfil.get("state") or "").strip(),
        "linkedin": str(perfil.get("linkedin_url") or "").strip(),
        "github": str(perfil.get("github_url") or "").strip(),
        "pretensao": str(perfil.get("salary_expectation") or "").strip(),
        "disponibilidade": str(perfil.get("availability") or "").strip(),
        "experiencia_anos": str(perfil.get("years_experience") or dados.get("years_experience") or "").strip(),
    }
    return {canonica: valor for canonica, valor in respostas.items() if valor}


def responder(
    perguntas: Iterable[str],
    banco: dict[str, str],
    conhecido: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Separa o que dá para responder do que precisa da pessoa.

    Devolve `(respondidas, pendentes)`. `banco` são as respostas já guardadas
    (por chave) e `conhecido` o que veio do perfil e do currículo.

    Pendente traz `motivo`: "sensivel" (a pessoa é quem responde), "aberta"
    (muda a cada vaga) ou "desconhecida" (o app nunca viu esta pergunta).
    """
    respondidas: list[dict[str, str]] = []
    pendentes: list[dict[str, str]] = []
    vistas: set[str] = set()

    for pergunta in perguntas:
        texto = " ".join(str(pergunta or "").split())[:300]
        if not texto:
            continue
        canonica = chave(texto)
        if canonica in vistas:
            continue  # o mesmo campo perguntado duas vezes no formulário
        vistas.add(canonica)

        if e_sensivel(texto):
            pendentes.append({"pergunta": texto, "chave": canonica, "motivo": "sensivel"})
            continue
        resposta = banco.get(canonica) or conhecido.get(canonica) or ""
        if resposta and not e_aberta(texto):
            respondidas.append({"pergunta": texto, "chave": canonica, "resposta": resposta})
            continue
        pendentes.append(
            {"pergunta": texto, "chave": canonica, "motivo": "aberta" if e_aberta(texto) else "desconhecida"}
        )
    return respondidas, pendentes
