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
from app.routers.tags import list_mine
from app.services import code_lab, code_lab_projeto
from app.services.progress import log_activity

router = APIRouter(prefix="/walkthroughs", tags=["laboratório de código"])

WALKTHROUGH_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "resumo": {"type": "STRING"},
        "cenario": {"type": "STRING"},
        "linguagem": {"type": "STRING"},
        "arquivos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "caminho": {"type": "STRING"},
                    "conteudo": {"type": "STRING"},
                },
                "required": ["caminho", "conteudo"],
            },
        },
        "conceitos": {"type": "ARRAY", "items": {"type": "STRING"}},
        "passos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "arquivo": {"type": "STRING"},
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
    "required": ["titulo", "resumo", "arquivos", "passos"],
}

SYSTEM_PROMPT = """Você escreve exemplos de código e de configuração comentados passo a passo, em português do Brasil.

Quem lê está aprendendo e NÃO tem ambiente montado nem sabe usar um depurador.
O valor do que você entrega está em ver a coisa RODAR: qual linha, de qual
arquivo, executa agora; o que cada variável ou contexto vale nesse instante; e
o que já saiu no terminal ou no log.

CONTEÚDO REAL — a regra que vale acima das outras:
1. Entregue o que se usa DE VERDADE para aquele assunto, do jeito que está num
   projeto real hoje. O assunto manda na forma:
   - GitHub Actions, CI/CD, "testes automatizados no GitHub": o workflow em
     `.github/workflows/<nome>.yml` E o teste que ele roda (na linguagem que a
     pessoa estuda), mais o arquivo de build quando o comando precisa dele;
   - Docker: `Dockerfile` (e `compose.yaml` quando há mais de um serviço);
     Kubernetes: manifestos YAML; Terraform: `.tf`;
   - Git: os comandos no terminal (`.sh`) com a saída real do git;
   - uma API ou aplicação "completa": as camadas em arquivos separados — em
     Java/Spring Boot, Controller, Service, Repository, Entity (e DTO quando
     fizer sentido), cada um no seu pacote em `src/main/java/...`;
   - um conceito de linguagem (laço, closure, generics): um arquivo só, curto.
   NUNCA escreva um programa numa linguagem para "simular" uma ferramenta que
   na vida real é configuração (um workflow do GitHub é YAML, não Java).
2. Só o que EXISTE, nas versões atuais estáveis: actions oficiais nas versões
   em uso (actions/checkout@v4, actions/setup-java@v4, actions/setup-node@v4,
   actions/setup-python@v5, actions/cache@v4); Spring Boot 3 com `jakarta.*`
   (nunca `javax.persistence`); JUnit 5 (`org.junit.jupiter`); Node LTS; Java 21
   ou 17. Nunca invente action, anotação, método, flag de comando ou chave de
   configuração. Na dúvida sobre algo existir, use o que você TEM certeza.
3. Caminhos e nomes como num repositório de verdade. Em Java: classe pública
   com o nome do arquivo e `package` igual às pastas depois de `src/main/java`
   (ou `src/test/java`).
4. Sintaxe válida: YAML com indentação certa, JSON/XML que abrem e fecham,
   chaves e parênteses fechados.

OS ARQUIVOS (`arquivos`):
5. Entre 1 e 6 arquivos; cada um até 80 linhas; o conjunto até 250. Um
   arquivo: entre 8 e 40 linhas. O PRIMEIRO arquivo é o principal do assunto
   (o workflow, o Controller, o Dockerfile).
6. `caminho` relativo à raiz do projeto, sem `./` (ex.: `.github/workflows/ci.yml`,
   `src/main/java/com/exemplo/produto/ProdutoController.java`).
7. Comentários curtos só onde o nome não basta; nomes de domínio em português
   quando fizer sentido (Produto, Pedido), palavras da ferramenta como são.
8. `linguagem`: o id da linguagem principal, um destes: {linguagens}.

O CENÁRIO (`cenario`), para a execução ser uma só:
9. Nada pode variar entre duas execuções: sem entrada digitada, data/hora
   atual, número aleatório. O que vem de fora é FIXADO e dito aqui em uma ou
   duas frases: "um push na branch main com um teste que passa", "a requisição
   POST /produtos com corpo {"nome": "Teclado", "preco": 150}",
   "banco começa vazio". Programa simples sem nada de fora: deixe vazio.

O TRAÇO (`passos`), que é a parte que importa:
10. Um passo por execução, na ORDEM REAL em que acontece — não na ordem em que
    as linhas aparecem. Laço que roda três vezes gera as três voltas. Chamada
    salta para o corpo (em outro arquivo, se for o caso) e VOLTA.
    Configuração também executa: no workflow, o evento dispara, o runner sobe,
    cada step roda na ordem (e o `run` do teste leva ao arquivo de teste); no
    Dockerfile, cada instrução gera uma etapa do build; no compose, os serviços
    sobem na ordem de `depends_on`.
11. `arquivo` é o `caminho` exato de um dos arquivos; `linha` é o número da
    linha DENTRO dele, começando em 1, contando linhas em branco e
    comentários. Nunca aponte para linha em branco.
12. `acao` diz o que ACONTECE naquela execução, com os valores daquele
    instante ("o Service recebe o produto Teclado e chama o save"), nunca o que
    a linha faz em tese.
13. `estado`: as variáveis vivas ao FIM do passo, como texto; em configuração,
    o contexto que importa (github.ref, a imagem da etapa, a variável de
    ambiente definida).
14. `saida`: só o que aquele passo imprimiu ou escreveu no log, exatamente
    como aparece de verdade (a linha do log do Actions, a saída do Maven/Jest,
    a resposta HTTP), sem repetir o que veio antes. O traço precisa ter saída.
15. No máximo 50 passos. Se passaria disso, diminua o EXEMPLO — não corte o
    traço pela metade.

Confira arquivo por arquivo e passo por passo antes de responder. Conteúdo
inventado ou traço que não bate com o arquivo ensina errado com cara de
certeza, que é pior que não existir."""


class NovoWalkthrough(BaseModel):
    language: str
    topic: str = Field(min_length=2, max_length=120)
    level: str = "iniciante"


def _valida(payload: NovoWalkthrough) -> None:
    if not code_lab.pode_pedir(payload.language):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Linguagem '{payload.language}' não está na lista.",
        )
    if payload.level not in code_lab.NIVEIS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nível '{payload.level}' não existe.",
        )


_NOME_PADRAO: dict[str, str] = {
    "python": "main.py", "javascript": "index.js", "typescript": "index.ts", "java": "Main.java",
    "csharp": "Program.cs", "go": "main.go", "rust": "main.rs", "c": "main.c", "cpp": "main.cpp",
    "php": "index.php", "ruby": "main.rb", "kotlin": "Main.kt", "swift": "main.swift", "dart": "main.dart",
    "sql": "consulta.sql", "bash": "script.sh", "powershell": "script.ps1", "html": "index.html",
    "css": "estilo.css", "yaml": "config.yml", "dockerfile": "Dockerfile", "json": "dados.json",
    "xml": "config.xml", "terraform": "main.tf",
}


def _arquivos_da_linha(linha: dict[str, Any]) -> list[dict[str, Any]]:
    """Os arquivos para a tela. Exemplo antigo (sem `files`) vira um arquivo só,
    com o nome de costume da linguagem."""
    brutos = linha.get("files") or []
    if not brutos:
        linguagem = str(linha.get("language") or "")
        brutos = [{"caminho": _NOME_PADRAO.get(linguagem, "exemplo.txt"), "linguagem": linguagem, "conteudo": linha.get("code") or ""}]
    arquivos = []
    for arquivo in brutos:
        linguagem = str(arquivo.get("linguagem") or "texto")
        arquivos.append({
            "caminho": str(arquivo.get("caminho") or ""),
            "linguagem": linguagem,
            "rotulo": code_lab.rotulo(linguagem),
            "realce": code_lab.realce(linguagem),
            "linhas": code_lab.linhas_de(str(arquivo.get("conteudo") or "")),
        })
    return arquivos


def _para_api(linha: dict[str, Any]) -> dict[str, Any]:
    codigo = linha.get("code") or ""
    arquivos = _arquivos_da_linha(linha)
    principal = arquivos[0]["caminho"] if arquivos else ""
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
        "files": arquivos,
        # Passo de exemplo antigo não diz o arquivo: é o único que existe.
        "steps": [{**passo, "arquivo": passo.get("arquivo") or principal} for passo in (linha.get("steps") or [])],
        "concepts": linha.get("concepts") or [],
        "created_at": linha.get("created_at"),
    }


@router.get("/languages")
def linguagens():
    """O que dá para pedir. Lista fechada: o prompt promete código idiomático,
    e não dá para prometer isso em linguagem que ninguém pensou a respeito."""
    return {"languages": code_lab.catalogo(), "levels": list(code_lab.NIVEIS)}


@router.get("/para-mim")
def para_mim(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """As linguagens do perfil e vários exemplos para abrir agora, pelo roadmap,
    pelo nível em cada linguagem e pelo que a pessoa já gerou. Sem IA: a tela
    abre com as sugestões na hora, e a IA só roda quando uma é escolhida.

    Declarada antes de `/{walkthrough_id}`, senão "para-mim" viraria um id."""
    user_id = str(current_user["id"])
    gerados = (
        supabase.table("pathr_walkthrough").select("topic").eq("user_id", user_id).execute().data or []
    )
    return code_lab.sugerir(
        list_mine(current_user, supabase),
        _modulos_do_plano(supabase, user_id),
        {str(linha.get("topic") or "") for linha in gerados},
    )


def _modulos_do_plano(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    """Os módulos do plano principal, em ordem, com as tags já em slug."""
    planos = (
        supabase.table("pathr_roadmap").select("id").eq("user_id", user_id).eq("is_primary", True)
        .limit(1).execute().data
    )
    if not planos:
        return []
    nos = (
        supabase.table("pathr_roadmap_node")
        .select("title,kind,status,objectives,tag_ids,order_index")
        .eq("roadmap_id", str(planos[0]["id"]))
        .order("order_index")
        .execute()
        .data
        or []
    )
    nos = [no for no in nos if no.get("kind") != "phase"]
    ids = list({str(tag_id) for no in nos for tag_id in (no.get("tag_ids") or [])})
    slug_de = (
        {str(t["id"]): str(t["slug"]) for t in supabase.table("pathr_tag").select("id,slug").in_("id", ids).execute().data or []}
        if ids
        else {}
    )
    return [
        {
            "titulo": no.get("title") or "",
            "status": no.get("status"),
            "objetivos": no.get("objectives") or [],
            "tags": [slug_de[str(t)] for t in (no.get("tag_ids") or []) if str(t) in slug_de],
        }
        for no in nos
    ]


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
    return _para_api(
        await gerar_exemplo(supabase, current_user, payload.language, payload.topic, payload.level)
    )


async def gerar_exemplo(
    supabase: Client, current_user: dict, language: str, topic: str, level: str = "iniciante"
) -> dict[str, Any]:
    """Gera, confere, grava e devolve a linha de um exemplo com passo a passo.

    Uma função e não só a rota: o "Perguntar" (routers/duvidas.py) gera exemplo
    pelo MESMO caminho — as tentativas e as conferências valem igual para o
    exemplo pedido numa dúvida.

    `language` pode ser "auto": o modelo escolhe os arquivos que o assunto usa
    de verdade, sabendo as linguagens que a pessoa estuda (o teste que o
    workflow roda sai na linguagem dela).
    """
    sistema = SYSTEM_PROMPT.replace("{linguagens}", ", ".join(l["id"] for l in code_lab.catalogo()))
    base = [
        f"Linguagem ou formato principal: {'escolha pelo assunto' if language == code_lab.AUTO else code_lab.rotulo(language)}",
        f"Assunto: {topic.strip()}",
        f"Nível de quem vai ler: {level}",
    ]
    do_perfil = _linguagens_que_estuda(supabase, current_user)
    if do_perfil:
        base.append(f"Linguagens que a pessoa estuda (use-as quando o assunto pedir código de apoio, como o teste): {', '.join(do_perfil)}")
    base.append("\nEscreva os arquivos, o cenário e o traço de execução completo.")

    # Três tentativas no máximo, e cada recusa volta para o modelo com o motivo.
    #
    # Medido em dez gerações de um arquivo só: uma em seis voltava com traço que
    # não bate com o código. Com vários arquivos e a conferência de conteúdo
    # real (services/code_lab_projeto.problemas), recusa-se mais — e dizer ao
    # modelo O QUE estava errado ("actions/checkout@v2 está desatualizada")
    # conserta na tentativa seguinte muito mais que sortear de novo.
    #
    # Conteúdo que não passa na conferência NUNCA é gravado: exemplo inventado
    # ensina errado. Já um conteúdo bom com traço incoerente vale como código
    # comentado, e a tela diz que o passo a passo não saiu.
    arquivos: list[dict[str, str]] = []
    passos: list[dict[str, Any]] = []
    dados: dict[str, Any] = {}
    recusas: list[str] = []

    for _tentativa in range(3):
        pedido = "\n".join(base)
        if recusas:
            pedido += (
                "\n\nA tentativa anterior foi RECUSADA pela conferência, por isto:\n- "
                + "\n- ".join(recusas[-6:])
                + "\nCorrija esses pontos e devolva o exemplo inteiro de novo."
            )
        try:
            resultado = await generate_json(sistema, pedido, WALKTHROUGH_SCHEMA)
        except AiProviderError as erro:
            # Se uma tentativa anterior já trouxe arquivos bons, uma falha de
            # provedor agora não pode apagar o que estava na mão.
            if arquivos:
                break
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)
            ) from erro

        conteudo = resultado.content if isinstance(resultado.content, dict) else {}
        candidatos, motivo = code_lab_projeto.normalizar(conteudo.get("arquivos"))
        if motivo:
            recusas = [motivo]
            continue
        achados = code_lab_projeto.problemas(candidatos)
        if achados:
            recusas = achados
            continue

        conferido = code_lab_projeto.conferir_traco(candidatos, conteudo.get("passos"))
        if conferido or not arquivos:
            arquivos, passos, dados = candidatos, conferido, conteudo
        if conferido:
            break
        recusas = [
            "o traço não bate com os arquivos: todo passo precisa de `arquivo` igual a um `caminho`, "
            "`linha` que exista e não esteja em branco naquele arquivo, e o traço precisa ter saída"
        ]

    if not arquivos:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA não conseguiu um exemplo fiel ao que se usa de verdade neste assunto. Tente de novo ou detalhe o assunto.",
        )

    linguagem_final = language
    if language == code_lab.AUTO:
        escolhida = str(dados.get("linguagem") or "").strip().lower()
        linguagem_final = escolhida if code_lab.existe(escolhida) else next(
            (a["linguagem"] for a in arquivos if code_lab.existe(a["linguagem"])), "bash"
        )

    resumo = str(dados.get("resumo") or "").strip()
    cenario = str(dados.get("cenario") or "").strip()
    if cenario:
        resumo = f"{resumo}\n\nCenário: {cenario}" if resumo else f"Cenário: {cenario}"

    novo = {
        "user_id": str(current_user["id"]),
        "language": linguagem_final,
        "topic": topic.strip(),
        "level": level,
        "title": str(dados.get("titulo") or topic)[:160],
        "summary": resumo[:1000],
        "code": arquivos[0]["conteudo"],
        "files": arquivos,
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
        detail={"language": language, "topic": novo["topic"]},
    )
    return gravado[0]


def _linguagens_que_estuda(supabase: Client, current_user: dict) -> list[str]:
    """Os nomes das linguagens do perfil, para o modelo escolher o código de
    apoio. Falhar aqui não impede de gerar: só perde a preferência."""
    try:
        return [l["rotulo"] for l in code_lab.linguagens_do_perfil(list_mine(current_user, supabase))][:4]
    except Exception:  # noqa: BLE001
        return []


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
