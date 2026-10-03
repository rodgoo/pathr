"""A migration 0001 não pode recriar uma coluna que uma migration posterior adiciona.

A 0001 nasceu derivada do metadata vivo de `app/models.py` (`SQLModel.metadata.
create_all`), não de um schema congelado. Isso parecia seguro — "a 0001 É o
schema inteiro" — até alguém rodar `alembic upgrade head` num banco vazio
depois que o modelo ganhou colunas novas: a 0001 passou a criar a tabela JÁ
com `birth_date`, `username`, `tech_suggestions` etc., e a migration que
devia adicioná-las de verdade (0003, 0020, 0016...) batia de frente com
"column already exists". O banco de produção nunca viu o problema — rodou a
0001 antiga e todas as seguintes em ordem, e o estado final é o mesmo dos
dois jeitos — mas qualquer instalação nova (scripts/bootstrap.py) sofria.

Este teste lê o TEXTO das migrations (sem banco, sem importar `app.models`)
e confere a regra: toda coluna que a 0001 cria não pode ter um `op.add_column`
em nenhuma migration posterior para a mesma tabela.
"""

import re
from pathlib import Path

VERSOES = Path(__file__).resolve().parents[1] / "alembic" / "versions"

# Mesma ressalva que test_modelos_espelham_migracoes.py já documenta: a
# coluna nasce dentro de um laço, com o nome vindo de uma variável — não de
# um literal `"nome"` ao lado de `sa.Column(` — então o regex principal não
# alcança. Checadas à mão contra 0007_multi_language.py e
# 0017_language_practice.py.
_ADICIONADAS_EM_LACO = {
    ("pathr_english_profile", "language"),  # 0007_multi_language
    ("pathr_english_assessment", "language"),  # 0007_multi_language
    ("pathr_english_session", "language"),  # 0007_multi_language
    ("pathr_english_vocab", "language"),  # 0007_multi_language
    ("pathr_review_item", "language"),  # 0017_language_practice
    ("pathr_review_item", "skill"),  # 0017_language_practice
    ("pathr_review_item", "topic"),  # 0017_language_practice
    ("pathr_review_item", "band"),  # 0017_language_practice
}


def _colunas_adicionadas_depois_da_0001() -> set[tuple[str, str]]:
    """(tabela, coluna) para todo `op.add_column` em 0002 e seguintes."""
    padrao = re.compile(r'op\.add_column\(\s*"(pathr_\w+)"\s*,\s*sa\.Column\(\s*"(\w+)"', re.DOTALL)
    pares: set[tuple[str, str]] = set()
    for caminho in sorted(VERSOES.glob("*.py")):
        if caminho.name.startswith("0001_"):
            continue
        texto = caminho.read_text(encoding="utf-8")
        pares |= set(padrao.findall(texto))
    return pares | _ADICIONADAS_EM_LACO


def _tabelas_e_colunas_da_0001() -> dict[str, set[str]]:
    """Lê o texto da 0001 e devolve, por tabela, as colunas que ela cria.

    De propósito NÃO usa `SQLModel.metadata`: o bug que este teste trava é
    justamente a 0001 ter sido derivada do metadata de hoje em vez de um
    schema congelado. Comparar com o metadata validaria a 0001 contra o
    próprio problema que ela precisa não ter.
    """
    [caminho] = VERSOES.glob("0001_*.py")
    texto = caminho.read_text(encoding="utf-8")
    trecho_upgrade = texto.split("def downgrade", 1)[0]

    marcas = list(re.finditer(r'op\.create_table\(\s*"(pathr_\w+)"', trecho_upgrade))
    blocos: dict[str, str] = {}
    for i, marca in enumerate(marcas):
        inicio = marca.end()
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(trecho_upgrade)
        blocos[marca.group(1)] = trecho_upgrade[inicio:fim]

    resultado: dict[str, set[str]] = {}
    for tabela, bloco in blocos.items():
        colunas = set(re.findall(r'sa\.Column\(\s*"(\w+)"', bloco))
        colunas |= set(re.findall(r'_fk\(\s*"(\w+)"', bloco))
        if "_uuid_pk()" in bloco:
            colunas.add("id")
        resultado[tabela] = colunas
    return resultado


def test_0001_realmente_declara_tabelas_com_create_table():
    """Rede de proteção contra o teste principal passar vazio sem checar nada:
    se a 0001 voltar a ser derivada de metadata (sem `op.create_table`
    literal nenhum), isto já falha aqui, antes de chegar ao teste de verdade.
    """
    tabelas = _tabelas_e_colunas_da_0001()
    assert len(tabelas) >= 25, (
        "a 0001 não tem pelo menos 25 `op.create_table(\"pathr_...\")` "
        "literais — ela voltou a ser derivada de metadata (create_all) em "
        "vez de um schema congelado?"
    )
    assert all(colunas for colunas in tabelas.values()), "tabela sem nenhuma coluna reconhecida na 0001"


def test_0001_nao_duplica_coluna_que_migration_posterior_adiciona():
    adicionadas_depois = _colunas_adicionadas_depois_da_0001()
    tabelas_0001 = _tabelas_e_colunas_da_0001()

    duplicadas = set()
    for tabela, colunas in tabelas_0001.items():
        for coluna in colunas:
            if (tabela, coluna) in adicionadas_depois:
                duplicadas.add(f"{tabela}.{coluna}")

    assert not duplicadas, (
        "a 0001 cria estas colunas, E uma migration 0002+ tenta criá-las de "
        "novo com op.add_column — isso quebra 'alembic upgrade head' num "
        f"banco vazio com 'column already exists': {sorted(duplicadas)}"
    )


def test_review_item_language_skill_topic_band_nao_estao_na_0001():
    """As quatro colunas que só o laço da 0017 adiciona (fora do alcance do
    regex principal) também não podem estar na 0001 — prova direta, e não só
    via a lista manual usada no teste acima."""
    colunas = _tabelas_e_colunas_da_0001().get("pathr_review_item", set())
    assert not colunas & {"language", "skill", "topic", "band"}


def test_english_profile_assessment_session_vocab_sem_language_na_0001():
    """O mesmo para as quatro colunas que só o laço da 0007 adiciona."""
    tabelas_0001 = _tabelas_e_colunas_da_0001()
    for tabela in (
        "pathr_english_profile",
        "pathr_english_assessment",
        "pathr_english_session",
        "pathr_english_vocab",
    ):
        assert "language" not in tabelas_0001.get(tabela, set()), tabela
