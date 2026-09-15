"""O laboratório de cada pessoa: só as linguagens dela, e o que abrir a seguir.

O que se segura: linguagem fora do perfil não aparece, o roadmap em andamento
vem antes da trilha genérica, o nível acompanha a proficiência, e o que já foi
gerado não é sugerido de novo.
"""

from app.services import code_lab as L


def _tag(slug, proficiency=1, is_target=True):
    return {"slug": slug, "proficiency": proficiency, "is_target": is_target}


def test_so_as_linguagens_do_perfil_e_sem_nenhuma_todas():
    r = L.sugerir([_tag("java"), _tag("docker"), _tag("sql", 3, False)], [], set())
    # O automático na frente; depois as do perfil; depois os formatos de
    # ferramenta (YAML, Dockerfile…), que valem para todo mundo.
    assert [l["id"] for l in r["linguagens"]] == ["auto", "java", "sql", *L.FORMATOS]
    assert r["do_perfil"] is True
    assert {s["language"] for s in r["sugestoes"]} <= {"java", "sql"}

    vazio = L.sugerir([_tag("docker")], [], set())
    assert vazio["do_perfil"] is False and len(vazio["linguagens"]) == len(L.LINGUAGENS) + 1
    assert vazio["sugestoes"] == []


def test_roadmap_primeiro_com_o_modulo_em_andamento_na_frente():
    modulos = [
        {"titulo": "Docker", "status": "doing", "objetivos": ["Subir containers."], "tags": ["docker"]},
        {"titulo": "Spring Boot", "status": "todo", "objetivos": ["Criar um projeto."], "tags": ["spring-boot"]},
        {"titulo": "JUnit", "status": "doing", "objetivos": ["Escrever testes."], "tags": ["junit"]},
        {"titulo": "Feito", "status": "done", "objetivos": [], "tags": ["java"]},
    ]
    r = L.sugerir([_tag("java")], modulos, set())
    do_roadmap = [s for s in r["sugestoes"] if s["origem"] == "roadmap"]
    # Docker se estuda no Dockerfile, mesmo sem a "linguagem" no perfil; o
    # módulo feito não volta.
    assert [s["topic"] for s in do_roadmap] == [
        "Docker: Subir containers", "JUnit: Escrever testes", "Spring Boot: Criar um projeto",
    ]
    assert [s["language"] for s in do_roadmap] == ["dockerfile", "java", "java"]
    assert do_roadmap[0]["motivo"].startswith("Em andamento")
    assert r["sugestoes"][: len(do_roadmap)] == do_roadmap


def test_modulo_de_github_actions_vira_yaml():
    modulos = [{"titulo": "GitHub Actions", "status": "doing", "objetivos": ["Rodar testes no CI."], "tags": ["github-actions"]}]
    r = L.sugerir([_tag("python")], modulos, set())
    assert r["sugestoes"][0]["language"] == "yaml"
    assert r["sugestoes"][0]["topic"] == "GitHub Actions: Rodar testes no CI"


def test_nivel_pela_proficiencia_e_um_passo_acima():
    r = L.sugerir([_tag("python", 4, False), _tag("java", 0)], [], set())
    niveis = {(s["language"], s["origem"]): s["level"] for s in r["sugestoes"]}
    assert niveis[("python", "trilha")] == "avancado"
    assert niveis[("java", "trilha")] == "iniciante"
    assert niveis[("java", "proximo_nivel")] == "intermediario"
    # Quem já está no avançado não tem "próximo passo".
    assert ("python", "proximo_nivel") not in niveis


def test_o_que_ja_foi_gerado_nao_volta_e_ha_varias_sugestoes():
    ja = {"Variáveis, tipos e operadores", "if/else e switch"}
    r = L.sugerir([_tag("java"), _tag("typescript")], [], ja)
    topicos = [s["topic"] for s in r["sugestoes"]]
    assert "variáveis, tipos e operadores" not in topicos and "if/else e switch" not in topicos
    assert len(topicos) >= 8 and len(set(topicos)) == len(topicos)
    assert {"java", "typescript"} == {s["language"] for s in r["sugestoes"]}
