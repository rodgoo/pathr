"""Extração de texto de um currículo enviado.

Cobre os formatos que as pessoas realmente mandam: PDF (a esmagadora
maioria), DOCX, ODT, RTF, TXT e Markdown. O texto extraído serve para duas
coisas — guardar em `pathr_resume.raw_text` (buscável, e evidência do que a
IA leu) e alimentar o caminho de texto da IA quando o envio direto do
arquivo não estiver disponível.

Importante: um PDF ESCANEADO não tem camada de texto, e nenhuma biblioteca
aqui inventa uma. `extract_text` devolve string vazia nesse caso, e quem
chama (services/resume_parser.py) manda o arquivo inteiro para o modelo com
visão em vez de desistir — que é justamente o caso em que o OCR do modelo
resolve e um parser de texto não resolveria.
"""

import io
import re
from dataclasses import dataclass

# Tipos aceitos no upload -> extensão canônica. A validação é por content type
# E por extensão porque navegador nenhum é confiável sozinho: o Windows manda
# .docx como application/octet-stream com frequência.
SUPPORTED = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/rtf": "rtf",
    "text/rtf": "rtf",
    "text/plain": "txt",
    "text/markdown": "md",
}

EXTENSIONS = {"pdf", "docx", "doc", "odt", "rtf", "txt", "md"}


@dataclass
class Extraction:
    text: str
    pages: int
    #  Por que a extração não rendeu nada, quando não rendeu — vai para
    # `pathr_resume.error` e explica ao usuário o que houve.
    note: str = ""


def normalize_kind(filename: str, content_type: str) -> str | None:
    """A extensão canônica do arquivo, ou None se não for um formato aceito."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in EXTENSIONS:
        return extension
    return SUPPORTED.get((content_type or "").split(";")[0].strip().lower())


# A assinatura que cada formato BINÁRIO carrega nos primeiros bytes. txt e md
# são texto puro, não têm assinatura e não entram aqui: qualquer byte é texto
# válido, e o pior que um binário renomeado para .txt causa é texto ilegível.
_ASSINATURAS_POR_TIPO: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
    # docx e odt sao conteineres ZIP; assinatura via bytes() para o fonte ficar ASCII puro.
    "docx": (bytes([0x50, 0x4B, 0x03, 0x04]), bytes([0x50, 0x4B, 0x05, 0x06]), bytes([0x50, 0x4B, 0x07, 0x08])),
    "odt": (bytes([0x50, 0x4B, 0x03, 0x04]), bytes([0x50, 0x4B, 0x05, 0x06]), bytes([0x50, 0x4B, 0x07, 0x08])),
    "doc": (bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]),),  # OLE2
    "rtf": (bytes([0x7B, 0x5C, 0x72, 0x74, 0x66]),),
}


def _zip_confere(kind: str, data: bytes) -> bool:
    """docx e odt são ZIP — a assinatura `PK` sozinha aceita QUALQUER zip
    (inclusive um .jar, um .apk ou um zip de malware renomeado). Aqui o
    conteiner precisa ter a estrutura interna do formato que diz ser:

    - docx (OOXML): tem `word/document.xml`.
    - odt (OpenDocument): tem `content.xml` e um arquivo `mimetype` cujo
      conteúdo começa com o mimetype de texto do OpenDocument.
    """
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as arquivo:
            nomes = set(arquivo.namelist())
            if kind == "docx":
                return "word/document.xml" in nomes
            if kind == "odt":
                if "content.xml" not in nomes or "mimetype" not in nomes:
                    return False
                mimetype = arquivo.read("mimetype").strip()
                return mimetype.startswith(b"application/vnd.oasis.opendocument.text")
    except (zipfile.BadZipFile, OSError, KeyError):
        return False
    return False


def bytes_conferem(kind: str, data: bytes) -> bool:
    """Os bytes batem com o formato declarado pela extensão?

    A extensão e o Content-Type vêm do cliente e mentem de graça — um arquivo
    qualquer renomeado para .pdf era aceito, guardado e, no caso do PDF, mandado
    ao Gemini como `application/pdf` sem nunca começar com `%PDF`. Aqui o
    conteúdo precisa provar o que diz ser. Mesma ideia do `_tipo_real` das fotos.
    """
    esperadas = _ASSINATURAS_POR_TIPO.get(kind)
    if esperadas is None:
        return True  # txt, md
    cabecalho = data[:1024]
    if kind == "pdf":
        # O `%PDF-` costuma abrir o arquivo, mas o padrão tolera alguns bytes
        # antes dele; aceitar no início do cabeçalho cobre esse caso raro.
        return b"%PDF-" in cabecalho
    if kind in ("docx", "odt"):
        # A assinatura ZIP é necessária mas NÃO suficiente: exige também a
        # estrutura interna do formato, senão qualquer zip passa por docx/odt.
        return any(cabecalho.startswith(a) for a in esperadas) and _zip_confere(kind, data)
    return any(cabecalho.startswith(a) for a in esperadas)


def _clean(text: str) -> str:
    """Junta as quebras que o PDF inventa e remove o excesso de espaço.

    Extração de PDF quebra linha no fim de cada linha VISUAL, então uma frase
    vira cinco linhas. Manter assim faz o modelo ler cada fragmento como item
    separado — e uma lista de skills quebrada no meio vira tecnologia
    inexistente.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_pdf(data: bytes) -> Extraction:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 — arquivo corrompido é entrada do usuário
        return Extraction("", 0, f"não foi possível abrir o PDF ({exc.__class__.__name__})")

    if reader.is_encrypted:
        # Tentativa padrão: muitos PDFs "protegidos" só bloqueiam impressão e
        # abrem com senha vazia.
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            return Extraction("", 0, "o PDF está protegido por senha")

    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — uma página ruim não invalida as outras
            continue

    text = _clean("\n".join(parts))
    if not text:
        return Extraction("", len(reader.pages), "o PDF não tem camada de texto (parece digitalizado)")
    return Extraction(text, len(reader.pages))


def _from_docx(data: bytes) -> Extraction:
    from docx import Document

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        return Extraction("", 0, f"não foi possível abrir o DOCX ({exc.__class__.__name__})")

    blocks = [paragraph.text for paragraph in document.paragraphs]
    # Currículo em DOCX frequentemente põe as competências numa tabela, e as
    # células não aparecem em document.paragraphs.
    for table in document.tables:
        for row in table.rows:
            blocks.append(" | ".join(cell.text.strip() for cell in row.cells))

    return Extraction(_clean("\n".join(blocks)), 0)


def _from_rtf(data: bytes) -> Extraction:
    """RTF sem dependência extra: remove grupos de controle e desescapa.

    Não é um parser de RTF completo, e não precisa ser — o objetivo é o texto
    corrido de um currículo, não fidelidade de formatação.
    """
    raw = data.decode("latin-1", errors="ignore")
    raw = re.sub(r"\\*\[a-z]+\d*[^{}]*", "", raw)
    raw = re.sub(r"\[a-z]+-?\d*\s?", " ", raw)
    raw = raw.replace("{", "").replace("}", "")
    return Extraction(_clean(raw), 0)


def _from_odt(data: bytes) -> Extraction:
    """ODT é um zip com content.xml dentro — dá para ler sem outra biblioteca."""
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("content.xml").decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        return Extraction("", 0, f"não foi possível abrir o ODT ({exc.__class__.__name__})")

    # Fecha parágrafo com quebra antes de remover as tags, senão o documento
    # inteiro vira uma linha só.
    xml = re.sub(r"</text:(p|h)>", "\n", xml)
    return Extraction(_clean(re.sub(r"<[^>]+>", " ", xml)), 0)


def extract_text(data: bytes, kind: str) -> Extraction:
    """Texto do arquivo, no melhor esforço. Nunca levanta por conteúdo ruim:
    arquivo enviado por usuário é entrada hostil por definição."""
    if kind == "pdf":
        return _from_pdf(data)
    if kind in ("docx", "doc"):
        # .doc antigo (OLE2) não é DOCX; a tentativa falha com nota clara em
        # vez de fingir que leu.
        result = _from_docx(data)
        if not result.text and kind == "doc":
            return Extraction("", 0, "formato .doc antigo — salve como .docx ou PDF")
        return result
    if kind == "odt":
        return _from_odt(data)
    if kind == "rtf":
        return _from_rtf(data)
    if kind in ("txt", "md"):
        return Extraction(_clean(data.decode("utf-8", errors="ignore")), 0)
    return Extraction("", 0, f"formato não suportado: {kind}")
