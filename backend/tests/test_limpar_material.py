"""A limpeza do catálogo: o que apagar, o que só desanexar, e o que NUNCA destruir.

`pathr_user_resource.resource_id` é ON DELETE CASCADE, então apagar um recurso leva o "concluído", as notas e o
progresso de quem interagiu com ele. O que estes testes seguram é que o script só apaga o que ninguém tocou.
"""

from scripts.limpar_material_fora_do_tema import planejar

DOCKER, KUBE, GIT = "t-docker", "t-kube", "t-git"
NOMES = {DOCKER: "Docker", KUBE: "Kubernetes", GIT: "Git"}


def _recurso(rid, titulo, tags, kind="article", url="https://exemplo.com/x", descricao=None):
    return {"id": rid, "kind": kind, "title": titulo, "url": url, "description": descricao, "tag_ids": tags}


CRIPTO = _recurso(
    "r-cripto", "Um Guia Para Iniciantes Sobre Como Investir Em Criptomoedas", [DOCKER],
    url="https://coinmarketcap.com/pt-br/academy/article/guia", descricao="Comprar Bitcoin com segurança.",
)


def test_lixo_que_ninguem_tocou_e_apagado():
    [acao] = planejar([CRIPTO], NOMES, com_interacao=set())
    assert acao.resource_id == "r-cripto" and acao.apagar is True
    assert acao.tags_removidas == ["Docker"] and acao.tag_ids_finais == []


def test_lixo_que_alguem_marcou_nunca_e_apagado():
    """O "concluído" e as notas de quem interagiu não podem ir embora junto: só sai da tela do módulo."""
    [acao] = planejar([CRIPTO], NOMES, com_interacao={"r-cripto"})
    assert acao.apagar is False
    assert acao.tag_ids_finais == [], "desanexado: some do módulo, o progresso da pessoa continua"


def test_recurso_de_duas_tags_perde_so_a_que_nao_e_dele():
    docker_e_kube = _recurso("r-2", "Docker para iniciantes", [DOCKER, KUBE], url="https://exemplo.com/docker")
    [acao] = planejar([docker_e_kube], NOMES, com_interacao=set())
    assert acao.tags_removidas == ["Kubernetes"]
    assert acao.tag_ids_finais == [DOCKER]
    assert acao.apagar is False, "ainda serve a outra tag"


def test_material_certo_nao_aparece_no_plano():
    bom = _recurso("r-3", "Get started with Docker", [DOCKER], url="https://docs.docker.com/get-started/", kind="doc")
    assert planejar([bom], NOMES, com_interacao=set()) == []


def test_video_nao_e_julgado():
    video = _recurso("r-4", "Containers na prática", [DOCKER], kind="video", url="https://youtube.com/watch?v=1")
    assert planejar([video], NOMES, com_interacao=set()) == []


def test_tag_desconhecida_e_deixada_em_paz():
    """Sem o nome da tag não há com o que comparar: melhor não mexer do que apagar por engano."""
    orfa = _recurso("r-5", "Qualquer coisa", ["t-sumiu"])
    assert planejar([orfa], NOMES, com_interacao=set()) == []


def test_recurso_sem_tag_nenhuma_nao_muda():
    assert planejar([_recurso("r-6", "Sem tag", [])], NOMES, com_interacao=set()) == []


def test_o_plano_so_lista_o_que_muda():
    bom = _recurso("r-7", "Git para equipes", [GIT], url="https://git-scm.com/book")
    acoes = planejar([CRIPTO, bom], NOMES, com_interacao=set())
    assert [a.resource_id for a in acoes] == ["r-cripto"]
