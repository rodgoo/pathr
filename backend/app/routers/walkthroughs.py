"""Códigos prontos que a pessoa percorre linha a linha.

O porquê e a regra de conferência estão em services/code_lab.py. Aqui fica o
que fala com o modelo e com o banco.

## Por que o traço é guardado

Gerar custa segundos e uma chamada de IA. Quem está estudando volta ao mesmo
exemplo várias vezes — é o uso ESPERADO, não o excepcional. Regerar a cada
abertura daria um programa diferente a cada visita, o que apaga justamente o
que a pessoa estava construindo na cabeça sobre aquele código.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.services import code_lab
from app.services.progress import log_activity

router = APIRouter(prefix="/walkthroughs", tags=["laboratório de código"])

WALKTHROUGH_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "resumo": {"type": "STRING"},
        "codigo": {"type": "STRING"},
        "conceitos": {"type": "ARRAY", "items": {"type": "STRING"}},
        "passos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "linha": {"type": "INTEGER"},
                    "acao": {"type": "STRING"},
                    "saida": {"type": "STRING"},
                    "estado": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "nome": {"type": "STRING"},
                                "valor": {"type": "STRING"},
                            },
                            "required": ["nome", "valor"],
                        },
                    },
                },
                "required": ["linha", "acao"],
            },
        },
    },
    "required": ["titulo", "resumo", "codigo", "passos"],
}

SYSTEM_PROMPT = """Você escreve exemplos de código comentados passo a passo, em português do Brasil.

Quem lê está aprendendo e NÃO tem ambiente montado nem sabe usar um depurador.
O valor do que você entrega está no traço de execução: ver qual linha roda
agora, o que cada variável vale nesse instante e o que já foi impresso.

O PROGRAMA:
1. Curto: entre 8 e 30 linhas de código. Nada de arquivo de projeto.
2. DETERMINÍSTICO e fechado. Proibido: entrada do usuário, data/hora atual,
   número aleatório, rede, arquivo, banco, variável de ambiente, concorrência.
   Se o resultado puder mudar entre duas execuções, o traço vira mentira.
3. Idiomático na linguagem pedida, com nomes em português quando fizer sentido
   e comentários curtos só onde o nome não basta.
4. Ele precisa IMPRIMIR coisas. Programa sem saída não mostra execução.

O TRAÇO (campo `passos`), que é a parte que importa:
5. Um passo por execução de linha, na ORDEM REAL em que a máquina executa —
   não na ordem em que as linhas aparecem no arquivo. Laço que roda três
   vezes gera os passos das três voltas. Chamada de função salta para o corpo
   dela e depois VOLTA para a linha que chamou.
6. `linha` é o número da linha dentro de `codigo`, começando em 1. Contando
   TODAS as linhas, inclusive as em branco e as de comentário. Nunca aponte
   para uma linha em branco: ela não executa.
7. `acao` diz o que ACONTECE naquela execução, com os valores daquele
   instante ("soma 3 ao total, que passa de 7 para 10"), nunca o que a linha
   faz em tese ("soma um valor ao total").
8. `estado` traz as variáveis vivas com o valor ao FIM do passo, como texto.
9. `saida` só quando aquela linha imprimiu algo — e exatamente o que ela
   imprimiu, sem repetir o que veio antes.
10. No máximo 40 passos. Se o programa passaria disso, encurte o PROGRAMA —
    não corte o traço pela metade.

Confira o traço linha por linha antes de responder. Um traço que não bate com
o código ensina errado com cara de certeza, que é pior que não existir."""


class NovoWalkthrough(BaseModel):
    language: str
    topic: str = Field(min_length=2, max_length=120)
    level: str = "iniciante"


def _valida(payload: NovoWalkthrough) -> None:
    if not code_lab.existe(payload.language):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Linguagem '{payload.language}' não está na lista.",
        )
    if payload.level not in code_lab.NIVEIS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nível '{payload.level}' não existe.",
        )


def _para_api(linha: dict[str, Any]) -> dict[str, Any]:
    codigo = linha.get("code") or ""
    return {
        "id": str(linha["id"]),
        "language": linha["language"],
        "language_label": code_lab.rotulo(linha["language"]),
        "highlight": code_lab.realce(linha["language"]),
        "topic": linha.get("topic") or "",
        "level": linha.get("level") or "iniciante",
        "title": linha.get("title") or "",
        "summary": linha.get("summary") or "",
        "code": codigo,
        "lines": code_lab.linhas_de(codigo),
        "steps": linha.get("steps") or [],
        "concepts": linha.get("concepts") or [],
        "created_at": linha.get("created_at"),
    }


@router.get("/languages")
def linguagens():
    """O que dá para pedir. Lista fechada: o prompt promete código idiomático,
    e não dá para prometer isso em linguagem que ninguém pensou a respeito."""
    return {"languages": code_lab.catalogo(), "levels": list(code_lab.NIVEIS)}


@router.get("")
def listar(
    language: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    consulta = (
        supabase.table("pathr_walkthrough")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True)
        .limit(60)
    )
    if language:
        consulta = consulta.eq("language", language)
    return [_para_api(linha) for linha in (consulta.execute().data or [])]


@router.get("/{walkthrough_id}")
def obter(
    walkthrough_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    linhas = (
        supabase.table("pathr_walkthrough")
        .select("*")
        .eq("id", walkthrough_id)
        .eq("user_id", str(current_user["id"]))
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exemplo não encontrado.")
    return _para_api(linhas[0])


@router.post("", status_code=status.HTTP_201_CREATED)
async def criar(
    payload: NovoWalkthrough,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _valida(payload)

    pedido = (
        f"Linguagem: {code_lab.rotulo(payload.language)}\n"
        f"Assunto: {payload.topic.strip()}\n"
        f"Nível de quem vai ler: {payload.level}\n\n"
        "Escreva o exemplo e o traço de execução completo."
    )
    # Duas tentativas, e não uma.
    #
    # Medido em dez gerações: das que o provedor respondeu, uma em seis voltou
    # com traço que não bate com o próprio código — passo apontando para linha
    # que não existe, ou traço que para antes do primeiro print. A recusa é
    # deliberada (services/code_lab.conferir), mas uma tela que diz "o passo a
    # passo não saiu" num sexto das vezes ensina a pessoa a não usar o recurso.
    # A segunda chamada é independente da primeira e quase sempre sai boa; uma
    # terceira seria pagar muito por pouco.
    #
    # Sem traço coerente nas duas, o exemplo ainda vale como código comentado
    # e a tela diz que o passo a passo não saiu. Mostrar um traço que não bate
    # com o código seria pior que não ter passo a passo nenhum.
    codigo: str = ""
    passos: list[dict[str, Any]] = []
    dados: dict[str, Any] = {}

    for tentativa in range(2):
        try:
            resultado = await generate_json(SYSTEM_PROMPT, pedido, WALKTHROUGH_SCHEMA)
        except AiProviderError as erro:
            # Se a primeira já trouxe código, uma falha de provedor na segunda
            # não pode apagar o que estava na mão.
            if codigo:
                break
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)
            ) from erro

        conteudo = resultado.content if isinstance(resultado.content, dict) else {}
        candidato = str(conteudo.get("codigo") or "").replace("\r\n", "\n").rstrip("\n")
        if not candidato.strip():
            continue

        conferido = code_lab.conferir(candidato, conteudo.get("passos") or [])
        if conferido or not codigo:
            codigo, passos, dados = candidato, conferido, conteudo
        if conferido:
            break

    if not codigo.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA não devolveu código. Tente de novo ou mude o assunto.",
        )

    novo = {
        "user_id": str(current_user["id"]),
        "language": payload.language,
        "topic": payload.topic.strip(),
        "level": payload.level,
        "title": str(dados.get("titulo") or payload.topic)[:160],
        "summary": str(dados.get("resumo") or "")[:600],
        "code": codigo,
        "steps": passos,
        "concepts": [str(conceito)[:60] for conceito in (dados.get("conceitos") or [])][:8],
    }
    gravado = supabase.table("pathr_walkthrough").insert(novo).execute().data
    if not gravado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não consegui guardar o exemplo.",
        )

    log_activity(
        supabase,
        user=current_user,
        kind="walkthrough",
        title=novo["title"],
        ref_id=str(gravado[0]["id"]),
        minutes=5,
        detail={"language": payload.language, "topic": novo["topic"]},
    )
    return _para_api(gravado[0])


@router.delete("/{walkthrough_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    walkthrough_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    alvo = (
        supabase.table("pathr_walkthrough")
        .select("id")
        .eq("id", walkthrough_id)
        .eq("user_id", str(current_user["id"]))
        .limit(1)
        .execute()
        .data
    )
    if not alvo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exemplo não encontrado.")
    supabase.table("pathr_walkthrough").delete().eq("id", walkthrough_id).execute()
