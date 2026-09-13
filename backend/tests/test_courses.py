"""Cursos com certificado.

Offline. O que se segura aqui é a promessa da tela: todo curso tem
certificado com gratuidade declarada, o gratuito vem SEMPRE antes do pago, e
só aparece curso do que a pessoa disse que quer aprender.
"""

from urllib.parse import urlparse

from app.routers.courses import list_courses
from app.services import courses
from app.services.tag_catalog import slugify
from app.services.tag_seed import SEED
from tests.fake_supabase import FakeSupabase


def _tag(name: str, proficiency: int = 0, is_target: bool = False) -> dict:
    return {"slug": slugify(name), "name": name, "proficiency": proficiency, "is_target": is_target}


# ── O catálogo ────────────────────────────────────────────────────────────


def test_todo_curso_declara_certificado_e_custo():
    for curso in courses.CURSOS:
        assert isinstance(curso.gratuito, bool), curso.id
        assert curso.custo.strip(), curso.id
        assert 0 <= curso.demanda <= 100, curso.id
        assert curso.nivel in {"iniciante", "intermediario", "avancado"}, curso.id
        assert urlparse(curso.url).scheme == "https", curso.id


def test_ids_nao_se_repetem():
    ids = [curso.id for curso in courses.CURSOS]
    assert len(ids) == len(set(ids))


def test_tags_dos_cursos_existem_no_catalogo_de_tags():
    """Sem isso o curso nunca casa: a tag do usuário vem do catálogo, e um
    nome escrito diferente aqui vira um slug que ninguém tem."""
    nomes = {nome for nome, *_ in SEED}
    for curso in courses.CURSOS:
        assert set(curso.tags) <= nomes, (curso.id, set(curso.tags) - nomes)


def test_catalogo_tem_gratuitos_para_as_areas_principais():
    gratuitos = {tag for curso in courses.CURSOS if curso.gratuito for tag in curso.tags}
    assert {"Python", "JavaScript", "SQL", "Segurança", "AWS", "Java", "Inglês"} <= gratuitos


# ── A ordenação ───────────────────────────────────────────────────────────


def test_gratuito_vem_antes_de_qualquer_pago():
    todas = [_tag(nome, is_target=True) for nome, *_ in SEED]
    lista = courses.recomendar(todas)
    gratuidade = [item["certificado"]["gratuito"] for item in lista]
    primeiro_pago = gratuidade.index(False)
    assert all(gratuidade[:primeiro_pago])
    assert not any(gratuidade[primeiro_pago:])


def test_pago_muito_relevante_nao_passa_na_frente_de_gratuito_pouco_relevante():
    # Três tags do curso da IBM (pago) contra uma de um curso gratuito.
    pedido = [_tag("Docker", is_target=True), _tag("Kubernetes", is_target=True),
              _tag("Microsserviços", is_target=True), _tag("Git", is_target=True)]
    ids = [item["id"] for item in courses.recomendar(pedido)]
    assert ids.index("fcc-relational-db") < ids.index("ibm-fullstack")


def test_dentro_do_grupo_a_relevancia_manda():
    pedido = [_tag("Python", is_target=True), _tag("Pandas", is_target=True)]
    gratuitos = [item["id"] for item in courses.recomendar(pedido) if item["certificado"]["gratuito"]]
    # Casa as duas tags; os de Python puro casam uma.
    assert gratuitos.index("fcc-data-analysis") < gratuitos.index("kaggle-python")


# ── O que conta como "quero aprender" ─────────────────────────────────────


def test_so_aparece_curso_do_que_foi_pedido():
    lista = courses.recomendar([_tag("Terraform", is_target=True)])
    assert [item["id"] for item in lista] == ["terraform-associate"]


def test_catalogo_inteiro_traz_tudo_com_o_pedido_na_frente_e_categoria():
    """A busca da tela de cursos: todos os cursos, e cada um com as categorias
    das suas tecnologias para filtrar."""
    lista = courses.recomendar([_tag("Terraform", is_target=True)], todos=True)
    assert len(lista) == len(courses.CURSOS)
    gratuitos = [item for item in lista if item["certificado"]["gratuito"]]
    pagos = [item for item in lista if not item["certificado"]["gratuito"]]
    assert lista == gratuitos + pagos
    terraform = next(item for item in lista if item["id"] == "terraform-associate")
    assert terraform["relevancia"] > 0 and "devops" in terraform["categorias"]
    assert all(item["categorias"] for item in lista)
    # Sem `todos`, continua só o pedido.
    assert [i["id"] for i in courses.recomendar([_tag("Terraform", is_target=True)])] == ["terraform-associate"]


def test_competencia_ja_dominada_e_sem_meta_nao_puxa_curso():
    assert courses.recomendar([_tag("Docker", proficiency=4)]) == []


def test_meta_desmarcada_some_dos_cursos():
    """Desmarcar a meta é dizer "não é para agora": o curso some, mesmo que a
    tecnologia esteja em N0 ou apareça no roadmap e no objetivo."""
    desmarcada = [_tag("Terraform", proficiency=0, is_target=False)]
    assert courses.recomendar(desmarcada) == []
    assert courses.recomendar(desmarcada, slugs_do_roadmap=["terraform"], objetivo="Quero Terraform") == []
    # Marcada de novo, volta.
    assert courses.recomendar([_tag("Terraform", is_target=True)])[0]["id"] == "terraform-associate"


def test_roadmap_e_objetivo_tambem_pedem():
    pelo_plano = courses.recomendar([], slugs_do_roadmap=["terraform"])
    assert pelo_plano[0]["motivos"][0]["tipo"] == "roadmap"

    pelo_texto = courses.recomendar([], objetivo="Quero ser dev backend com Kubernetes")
    assert {item["id"] for item in pelo_texto} >= {"kcna", "ckad"}


def test_objetivo_casa_palavra_inteira():
    """"Java" não pode acender dentro de "JavaScript"."""
    assert "java" not in courses.tags_no_texto("Desenvolvedor JavaScript")
    assert "java" in courses.tags_no_texto("Desenvolvedor Java pleno")
    assert "c-sharp" in courses.tags_no_texto("vaga de C# e .NET")
    assert "java" in courses.tags_no_texto("Quero aprender Java.")
    assert "c" not in courses.tags_no_texto("vaga c salário bom")


def test_meta_pesa_mais_que_o_texto_do_objetivo():
    lista = courses.recomendar([_tag("AWS", is_target=True)], objetivo="AWS")
    assert lista[0]["motivos"][0]["tipo"] == "meta"


# ── A barra de chama ──────────────────────────────────────────────────────


def test_faixas_de_demanda():
    assert courses.faixa_de(95)[0] == "pegando_fogo"
    assert courses.faixa_de(85)[0] == "pegando_fogo"
    assert courses.faixa_de(72)[0] == "em_alta"
    assert courses.faixa_de(50)[0] == "procurado"
    assert courses.faixa_de(40)[0] == "comum"
    assert courses.faixa_de(10)[0] == "basico"


def test_basico_explica_por_que_esta_embaixo():
    item = courses.recomendar([_tag("HTML", is_target=True)])[0]
    assert item["demanda"]["faixa"] == "basico"
    assert item["demanda"]["motivo"]


# ── O endpoint ────────────────────────────────────────────────────────────


def test_endpoint_junta_tags_perfil_e_roadmap():
    banco = FakeSupabase(
        pathr_tag=[
            {"id": "t1", "slug": "aws", "name": "AWS", "category": "cloud"},
            {"id": "t2", "slug": "terraform", "name": "Terraform", "category": "devops"},
            {"id": "t3", "slug": "scrum", "name": "Scrum", "category": "metodologia"},
        ],
        pathr_user_tag=[
            {"id": "u1", "user_id": "eu", "tag_id": "t1", "proficiency": 1, "is_target": True},
        ],
        pathr_profile=[{"user_id": "eu", "target_role": "", "goals": ["trabalhar com Scrum"]}],
        pathr_roadmap=[{"id": "r1", "user_id": "eu", "is_primary": True}],
        pathr_roadmap_node=[
            {"roadmap_id": "r1", "tag_ids": ["t2"], "status": "todo"},
            {"roadmap_id": "r1", "tag_ids": ["t3"], "status": "done"},
        ],
    )

    resposta = list_courses({"id": "eu"}, banco)

    tags_pedidas = {motivo["tag"] for item in resposta["cursos"] for motivo in item["motivos"]}
    assert {"AWS", "Terraform", "Scrum"} <= tags_pedidas
    assert resposta["tem_pedido"] is True
    assert resposta["conferido_em"] == courses.CONFERIDO_EM


def test_endpoint_sem_nada_pedido():
    banco = FakeSupabase(pathr_tag=[], pathr_user_tag=[], pathr_profile=[], pathr_roadmap=[])
    resposta = list_courses({"id": "eu"}, banco)
    assert resposta == {"cursos": [], "conferido_em": courses.CONFERIDO_EM, "tem_pedido": False}


# ── "Já possuo" ───────────────────────────────────────────────────────────


def test_marcar_ja_possuo_aparece_na_lista_e_em_meus_cursos():
    from app.routers.courses import mark_owned, my_courses, unmark_owned

    banco = FakeSupabase(
        pathr_tag=[{"id": "t1", "slug": "aws", "name": "AWS", "category": "cloud"}],
        pathr_user_tag=[{"id": "u1", "user_id": "eu", "tag_id": "t1", "proficiency": 1, "is_target": True}],
        pathr_profile=[{"user_id": "eu"}],
        pathr_roadmap=[],
        pathr_user_course=[],
    )
    eu = {"id": "eu"}

    marcado = mark_owned("aws-ccp", eu, banco)
    mark_owned("aws-ccp", eu, banco)  # de novo: não duplica

    assert marcado["titulo"] == "AWS Certified Cloud Practitioner"
    assert len(banco.linhas("pathr_user_course")) == 1
    assert [c["id"] for c in my_courses(eu, banco)] == ["aws-ccp"]
    lista = {c["id"]: c["possuo"] for c in list_courses(eu, banco)["cursos"]}
    assert lista["aws-ccp"] is True and lista["aws-cloud-practitioner-essentials"] is False

    unmark_owned("aws-ccp", eu, banco)
    assert my_courses(eu, banco) == []


def test_marcar_curso_inexistente_e_404():
    import pytest
    from fastapi import HTTPException

    from app.routers.courses import mark_owned

    with pytest.raises(HTTPException) as erro:
        mark_owned("nao-existe", {"id": "eu"}, FakeSupabase(pathr_user_course=[]))
    assert erro.value.status_code == 404


def test_curso_que_saiu_do_catalogo_nao_quebra_meus_cursos():
    from app.routers.courses import my_courses

    banco = FakeSupabase(pathr_user_course=[{"user_id": "eu", "course_id": "curso-antigo", "created_at": "2026-01-01"}])
    assert my_courses({"id": "eu"}, banco) == []
