"""As rotas da PathR Extension — a extensão que preenche formulário de vaga.

## O que a extensão faz, e o que ela não faz

Ela roda no navegador da pessoa, na aba que a pessoa abriu, quando a pessoa
clica no ícone. Lê os rótulos do formulário, preenche o que o app já sabe e
mostra numa lista o que não soube. **Quem envia é a pessoa** — a extensão não
aperta "enviar", não entra em conta nenhuma e não navega sozinha por site de
emprego. Essa linha é de propósito e não é detalhe de implementação: preencher
formulário no navegador de quem se candidata é ajuda; operar a conta de alguém
num site de terceiro, em nome dela, é outra coisa.

## As duas metades daqui

- `/extensao/chaves`: a tela do app, com sessão por cookie, cria e revoga a
  chave. Fica atrás da mesma trava de recurso das candidaturas.
- o resto: a extensão, com a chave no cabeçalho `X-Pathr-Extensao`. Sem cookie,
  porque outra origem — o porquê está em `services/extensao.py`.

## Por que a chave não usa `Authorization`

`Authorization: Bearer` já quer dizer "sessão do app" em `deps.py`. Se a chave
entrasse por ali, um bug de roteamento faria uma credencial de alcance pequeno
valer como sessão inteira. Cabeçalho próprio, alcance próprio.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services import candidaturas as servico
from app.services import extensao as servico_da_extensao
from app.services import features, limites, perguntas

router = APIRouter(prefix="/extensao", tags=["extensao"])

# A extensão conversa muito (uma chamada por página aberta). O teto é alto o
# bastante para um dia de uso normal e baixo o bastante para que uma chave
# vazada não vire raspagem do banco de respostas em escala.
LEITURA_DA_EXTENSAO = limites.Regra(
    "extensao-leitura",
    400,
    timedelta(days=1),
    "A extensão fez muitos pedidos hoje. O limite volta amanhã.",
)

# As formas sensíveis viajam para a extensão porque a decisão de não responder
# precisa acontecer LÁ, antes de preencher — não aqui, depois.
SENSIVEIS_EM_TEXTO = sorted(
    {forma for formas in perguntas.SENSIVEIS.values() for forma in formas}
)


def pessoa_da_chave(
    supabase: Client = Depends(get_supabase),
    x_pathr_extensao: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Quem está do outro lado da chave — ou 401."""
    pessoa = servico_da_extensao.dono(supabase, x_pathr_extensao)
    if not pessoa:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave da extensão inválida ou revogada.",
        )
    if not features.habilitadas_para(pessoa, supabase).get("candidaturas", False):
        # Mesma trava da aba: desligar o recurso desliga a extensão junto.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso indisponível.")
    limites.consumir(supabase, LEITURA_DA_EXTENSAO, str(pessoa["id"]))
    return pessoa


def dona_da_tela(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """A pessoa logada no app, com o recurso de candidaturas ligado."""
    if not features.habilitadas_para(current_user, supabase).get("candidaturas", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso indisponível.")
    return current_user


# ---------------------------------------------------------------------------
# A tela do app: criar, listar e revogar a chave
# ---------------------------------------------------------------------------


class PedidoDeChave(BaseModel):
    nome: str = Field(default="Extensão", max_length=80)


@router.get("/chaves")
def listar_chaves(
    current_user: dict = Depends(dona_da_tela),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    return {"chaves": servico_da_extensao.listar(supabase, str(current_user["id"]))}


@router.post("/chaves", status_code=status.HTTP_201_CREATED)
def criar_chave(
    pedido: PedidoDeChave,
    current_user: dict = Depends(dona_da_tela),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    """Cria a chave. `chave` vem aqui e em lugar nenhum depois."""
    try:
        chave, linha = servico_da_extensao.criar(supabase, str(current_user["id"]), pedido.nome)
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro)) from erro
    return {"chave": chave, **linha}


@router.delete("/chaves/{chave_id}", status_code=status.HTTP_204_NO_CONTENT)
def revogar_chave(
    chave_id: str,
    current_user: dict = Depends(dona_da_tela),
    supabase: Client = Depends(get_supabase),
) -> None:
    if not servico_da_extensao.revogar(supabase, str(current_user["id"]), chave_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chave não encontrada.")


# ---------------------------------------------------------------------------
# A extensão: o que preencher, o currículo e o que ela aprendeu
# ---------------------------------------------------------------------------


@router.get("/dados")
def dados_para_preencher(
    pessoa: dict = Depends(pessoa_da_chave),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    """Tudo o que a extensão precisa para preencher um formulário.

    Vai em UMA chamada, no começo: se cada campo perguntasse ao servidor, um
    formulário de trinta campos viraria trinta idas e vindas, e o preenchimento
    aconteceria na frente da pessoa, campo a campo, em vez de de uma vez.

    `respostas` são as guardadas no banco (já decifradas) e `perfil` o que o app
    sabe de cadastro e currículo. Duas listas e não uma porque a extensão avisa
    de onde veio cada valor — "do seu perfil" e "você respondeu isto antes" não
    querem dizer a mesma coisa para quem confere.
    """
    user_id = str(pessoa["id"])
    perfil = (
        supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data
        or [{}]
    )[0]
    _, curriculo_lido = servico._curriculo(supabase, user_id)

    return {
        "pessoa": {"nome": pessoa.get("name") or "", "email": pessoa.get("email") or ""},
        "respostas": servico.banco_de_respostas(supabase, user_id),
        "perfil": perguntas.do_perfil(perfil, pessoa, curriculo_lido),
        # A extensão usa isto para marcar o campo como "não respondo sozinho" em
        # vez de deixar em branco sem explicação.
        "sensiveis": SENSIVEIS_EM_TEXTO,
    }


@router.get("/curriculo")
def curriculo(
    pessoa: dict = Depends(pessoa_da_chave),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    """O PDF do currículo, em base64, para a extensão anexar no campo de arquivo.

    Em chamada separada de `/dados` porque é o pedaço pesado: a maioria dos
    formulários não tem campo de arquivo, e quem não tem não paga por ele.
    """
    nome, conteudo = servico.curriculo_em_anexo(supabase, str(pessoa["id"]))
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum currículo enviado."
        )
    return {
        "nome": nome,
        "tipo": "application/pdf",
        "base64": conteudo,
        "bytes": len(base64.b64decode(conteudo)),
    }


class RespostaNova(BaseModel):
    pergunta: str = Field(max_length=300)
    resposta: str = Field(max_length=2000)


class RespostasDaExtensao(BaseModel):
    respostas: list[RespostaNova] = Field(default_factory=list, max_length=40)


@router.post("/respostas")
def guardar(
    corpo: RespostasDaExtensao,
    pessoa: dict = Depends(pessoa_da_chave),
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    """O que a pessoa respondeu no site volta para o banco.

    É isto que faz a extensão melhorar: a pergunta que ela não soube hoje, na
    próxima vaga ela já sabe — inclusive em outro site, porque o que se guarda é
    a CHAVE da pergunta, e "Nome completo" e "Full name" têm a mesma.

    `origem="extensao"` para a tela poder mostrar de onde veio, e o filtro de
    pergunta sensível continua sendo o de `guardar_respostas`: não é porque
    chegou pela extensão que passa a ser gravável.
    """
    user_id = str(pessoa["id"])
    quantas = servico.guardar_respostas(
        supabase,
        user_id,
        [{"pergunta": item.pergunta, "resposta": item.resposta} for item in corpo.respostas],
        origem="extensao",
    )
    return {"guardadas": quantas, "respostas": servico.banco_de_respostas(supabase, user_id)}
