"""Leitura de currículo: extração de texto, normalização e catálogo de tags.

Estes são os pontos onde entrada hostil encontra o app — um PDF quebrado, um
modelo que respondeu fora do formato, um nome de tecnologia escrito de outro
jeito. Nenhum deles pode derrubar a requisição nem sujar o perfil.
"""

import io
import zipfile

from app.security import hash_password, password_problems, verify_password
from app.services.resume_parser import normalize
from app.services.tag_catalog import CATEGORIES, normalize_category, slugify
from app.services.tag_seed import SEED, seed_rows
from app.services.text_extract import extract_text, normalize_kind


class TestExtracaoDeTexto:
    def test_txt_e_markdown(self):
        resultado = extract_text(b"Java\n\n\n\nSpring   Boot", "txt")
        # Espaco repetido colapsa e a sequencia de linhas vazias vira uma so.
        assert resultado.text == "Java\n\nSpring Boot"

    def test_pdf_corrompido_nao_levanta(self):
        resultado = extract_text(b"isto nao e um pdf", "pdf")
        assert resultado.text == ""
        assert resultado.note

    def test_docx_corrompido_nao_levanta(self):
        resultado = extract_text(b"lixo", "docx")
        assert resultado.text == ""

    def test_odt_le_o_content_xml(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "content.xml",
                "<office><text:p>Java</text:p><text:p>PostgreSQL</text:p></office>",
            )
        resultado = extract_text(buffer.getvalue(), "odt")
        assert "Java" in resultado.text and "PostgreSQL" in resultado.text

    def test_formato_reconhecido_por_extensao_ou_content_type(self):
        assert normalize_kind("cv.pdf", "application/octet-stream") == "pdf"
        assert normalize_kind("cv", "application/pdf") == "pdf"
        assert normalize_kind("cv.exe", "application/x-msdownload") is None


class TestNormalizacaoDoParse:
    def test_proficiencia_fora_da_escala_e_limitada(self):
        saida = normalize({"tecnologias": [{"nome": "Java", "proficiencia": 99}]})
        assert saida["tecnologias"][0]["proficiencia"] == 5

    def test_proficiencia_invalida_vira_zero(self):
        saida = normalize({"tecnologias": [{"nome": "Java", "proficiencia": "muito boa"}]})
        assert saida["tecnologias"][0]["proficiencia"] == 0

    def test_duplicata_por_caixa_e_descartada(self):
        saida = normalize(
            {"tecnologias": [{"nome": "React", "proficiencia": 3}, {"nome": "REACT", "proficiencia": 1}]}
        )
        assert len(saida["tecnologias"]) == 1
        assert saida["tecnologias"][0]["proficiencia"] == 3

    def test_nome_vazio_ou_gigante_e_descartado(self):
        saida = normalize(
            {"tecnologias": [{"nome": "  "}, {"nome": "x" * 80}, {"nome": "Go", "proficiencia": 2}]}
        )
        assert [item["nome"] for item in saida["tecnologias"]] == ["Go"]

    def test_resposta_sem_lista_nao_quebra(self):
        assert normalize({"tecnologias": "Java, Python"})["tecnologias"] == []
        assert normalize({})["tecnologias"] == []

    def test_categoria_ausente_cai_no_balde_honesto(self):
        saida = normalize({"tecnologias": [{"nome": "Java", "proficiencia": 3}]})
        assert saida["tecnologias"][0]["categoria"] == "ferramenta"


class TestCatalogoDeTags:
    def test_slug_separa_linguagens_parecidas(self):
        # Sem tratamento especial, C# e C colidiriam no mesmo slug.
        assert slugify("C#") == "c-sharp"
        assert slugify("C++") == "c-plus-plus"
        assert slugify("C") == "c"

    def test_slug_ignora_acento_e_pontuacao(self):
        assert slugify("Node.js") == "node-js"
        assert slugify("Ciência de Dados") == "ciencia-de-dados"
        assert slugify("  CI/CD  ") == "ci-cd"

    def test_categoria_desconhecida_vira_ferramenta(self):
        assert normalize_category("Frontend") == "frontend"
        assert normalize_category("inventada") == "ferramenta"
        assert normalize_category(None) == "ferramenta"

    def test_semente_nao_tem_slug_duplicado(self):
        slugs = [row["slug"] for row in seed_rows()]
        assert len(slugs) == len(set(slugs))

    def test_semente_so_usa_categorias_validas(self):
        assert {row["category"] for row in seed_rows()} <= CATEGORIES

    def test_apelido_nao_sequestra_outra_tag(self):
        """Um apelido que colidisse com o slug canônico de outra tecnologia
        faria a importação de currículo apontar para a tag errada."""
        canonicos = {slugify(nome) for nome, _c, _p, _a in SEED}
        for nome, _categoria, _popularidade, apelidos in SEED:
            for apelido in apelidos:
                slug = slugify(apelido)
                assert slug not in canonicos or slug == slugify(nome), (nome, apelido)


class TestSenha:
    def test_hash_e_verificacao(self):
        hash_ = hash_password("uma-senha-longa-1")
        assert verify_password("uma-senha-longa-1", hash_)
        assert not verify_password("outra-senha-longa-1", hash_)

    def test_hash_nunca_se_repete(self):
        # Argon2 salga por hash: duas iguais geram digests diferentes.
        assert hash_password("mesma-senha-123") != hash_password("mesma-senha-123")

    def test_regras_minimas(self):
        assert password_problems("curta1") 
        assert password_problems("apenasletrasaqui")
        assert password_problems("1234567890123")
        assert password_problems("senha-forte-123") == []
