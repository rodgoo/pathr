"""Idiomas e as provas reais de cada um.

## A decisão que sustenta o módulo

O app mede numa escala só — a do CEFR, A1 a C2 — e APRESENTA o resultado na
prova que a pessoa escolheu. Ele não aplica IELTS, TOEFL ou JLPT: aplicar
qualquer um deles exigiria um banco de itens calibrado, revisado por
examinadores e mantido a cada edição do exame, e nenhum produto monta isso a
partir de um LLM. Dizer o contrário seria vender aprovação que não se pode
entregar.

O que ele faz é honesto e útil: estima onde a pessoa está no CEFR e traduz
isso para a régua que ela usa no dia a dia. Quem quer 7.0 no IELTS pensa em
7.0, não em C1 — e as duas coisas são o mesmo ponto. Cada `Faixa` carrega essa
equivalência, e é ela que faz a meta "7.0" virar um alvo que o nivelamento
sabe medir.

## De onde vêm as equivalências

Das tabelas publicadas pelos próprios examinadores (IELTS, ETS para o TOEFL,
Cambridge, Instituto Cervantes, Goethe-Institut, Fundação Japão, Hanban) e da
grade do Conselho da Europa. Onde a fonte dá uma faixa e não um ponto, fica o
CEFR mais baixo: prometer menos e entregar mais é o erro certo aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# A escala interna. Tudo se converte para cá, e é aqui que o nivelamento mede.
CEFR = ("A1", "A2", "B1", "B2", "C1", "C2")


@dataclass(frozen=True)
class Faixa:
    """Uma nota da prova e o ponto do CEFR que ela representa."""

    rotulo: str
    cefr: str
    nota: str = ""


@dataclass(frozen=True)
class Exame:
    id: str
    nome: str
    descricao: str
    faixas: tuple[Faixa, ...]


@dataclass(frozen=True)
class Idioma:
    codigo: str  # ISO 639-1
    nome: str
    nativo: str
    exames: tuple[Exame, ...]


def _cefr_puro(prefixo: str = "") -> tuple[Faixa, ...]:
    """As seis faixas do CEFR, opcionalmente com o nome do exame na frente.

    Vários exames (DELE, Goethe, CILS, TCF) certificam POR nível do CEFR, então
    a escala deles é a própria — o que muda é só como o certificado se chama.
    """
    return tuple(
        Faixa(rotulo=f"{prefixo}{nivel}" if prefixo else nivel, cefr=nivel) for nivel in CEFR
    )


_CEFR = Exame(
    id="cefr",
    nome="CEFR (Quadro Europeu)",
    descricao="A régua que o app usa por dentro. Escolha esta se você não presta prova.",
    faixas=_cefr_puro(),
)

IDIOMAS: tuple[Idioma, ...] = (
    Idioma(
        codigo="en",
        nome="Inglês",
        nativo="English",
        exames=(
            _CEFR,
            Exame(
                id="ielts",
                nome="IELTS",
                descricao="Banda de 0 a 9. Aceito por universidades e imigração no Reino Unido, Austrália e Canadá.",
                faixas=(
                    Faixa("4.0", "B1", "banda 4.0–5.0"),
                    Faixa("5.5", "B2", "banda 5.5–6.5"),
                    Faixa("6.5", "B2", "banda 5.5–6.5"),
                    Faixa("7.0", "C1", "banda 7.0–8.0"),
                    Faixa("8.0", "C1", "banda 7.0–8.0"),
                    Faixa("8.5", "C2", "banda 8.5–9.0"),
                ),
            ),
            Exame(
                id="toefl_ibt",
                nome="TOEFL iBT",
                descricao="Pontuação de 0 a 120. O exame mais pedido por universidades nos Estados Unidos.",
                faixas=(
                    Faixa("42", "B1", "42–71 pontos"),
                    Faixa("72", "B2", "72–94 pontos"),
                    Faixa("95", "C1", "95–113 pontos"),
                    Faixa("114", "C2", "114–120 pontos"),
                ),
            ),
            Exame(
                id="toeic",
                nome="TOEIC (Listening & Reading)",
                descricao="De 10 a 990. É o exame que empresas usam para cargo e promoção.",
                faixas=(
                    Faixa("225", "A2", "225–545 pontos"),
                    Faixa("550", "B1", "550–780 pontos"),
                    Faixa("785", "B2", "785–940 pontos"),
                    Faixa("945", "C1", "945–990 pontos"),
                ),
            ),
            Exame(
                id="cambridge",
                nome="Cambridge English",
                descricao="Certificado vitalício, um por nível: KET, PET, FCE, CAE e CPE.",
                faixas=(
                    Faixa("KET", "A2"),
                    Faixa("PET", "B1"),
                    Faixa("FCE", "B2"),
                    Faixa("CAE", "C1"),
                    Faixa("CPE", "C2"),
                ),
            ),
        ),
    ),
    Idioma(
        codigo="es",
        nome="Espanhol",
        nativo="Español",
        exames=(
            _CEFR,
            Exame(
                id="dele",
                nome="DELE",
                descricao="Diploma oficial do Instituto Cervantes, sem prazo de validade.",
                faixas=_cefr_puro("DELE "),
            ),
            Exame(
                id="siele",
                nome="SIELE",
                descricao="Exame eletrônico, resultado em três semanas e validade de cinco anos.",
                faixas=_cefr_puro(),
            ),
        ),
    ),
    Idioma(
        codigo="fr",
        nome="Francês",
        nativo="Français",
        exames=(
            _CEFR,
            Exame(
                id="delf_dalf",
                nome="DELF / DALF",
                descricao="Diplomas do Ministério da Educação francês. DELF vai até B2; DALF cobre C1 e C2.",
                faixas=(
                    Faixa("DELF A1", "A1"),
                    Faixa("DELF A2", "A2"),
                    Faixa("DELF B1", "B1"),
                    Faixa("DELF B2", "B2"),
                    Faixa("DALF C1", "C1"),
                    Faixa("DALF C2", "C2"),
                ),
            ),
            Exame(
                id="tcf",
                nome="TCF",
                descricao="Teste de posicionamento; é o exigido para imigração ao Canadá francófono.",
                faixas=_cefr_puro(),
            ),
        ),
    ),
    Idioma(
        codigo="de",
        nome="Alemão",
        nativo="Deutsch",
        exames=(
            _CEFR,
            Exame(
                id="goethe",
                nome="Goethe-Zertifikat",
                descricao="Certificado do Goethe-Institut, um por nível do CEFR.",
                faixas=_cefr_puro("Goethe "),
            ),
            Exame(
                id="testdaf",
                nome="TestDaF",
                descricao="Exigido para universidade na Alemanha. Notas TDN 3, 4 e 5.",
                faixas=(Faixa("TDN 3", "B2"), Faixa("TDN 4", "B2"), Faixa("TDN 5", "C1")),
            ),
        ),
    ),
    Idioma(
        codigo="it",
        nome="Italiano",
        nativo="Italiano",
        exames=(
            _CEFR,
            Exame(
                id="cils",
                nome="CILS",
                descricao="Certificado da Universidade para Estrangeiros de Siena.",
                faixas=_cefr_puro("CILS "),
            ),
            Exame(
                id="celi",
                nome="CELI",
                descricao="Certificado da Universidade de Perúgia.",
                faixas=(
                    Faixa("CELI Impatto", "A2"),
                    Faixa("CELI 1", "B1"),
                    Faixa("CELI 2", "B2"),
                    Faixa("CELI 3", "C1"),
                    Faixa("CELI 4", "C2"),
                ),
            ),
        ),
    ),
    Idioma(
        codigo="ja",
        nome="Japonês",
        nativo="日本語",
        exames=(
            _CEFR,
            Exame(
                id="jlpt",
                nome="JLPT",
                descricao="Do N5 (inicial) ao N1 (avançado). É o exame padrão para trabalho no Japão.",
                faixas=(
                    Faixa("N5", "A1"),
                    Faixa("N4", "A2"),
                    Faixa("N3", "B1"),
                    Faixa("N2", "B2"),
                    Faixa("N1", "C1"),
                ),
            ),
        ),
    ),
    Idioma(
        codigo="zh",
        nome="Chinês (mandarim)",
        nativo="中文",
        exames=(
            _CEFR,
            Exame(
                id="hsk",
                nome="HSK",
                descricao="Do HSK 1 ao 6. Exigido para bolsa e universidade na China.",
                faixas=(
                    Faixa("HSK 1", "A1"),
                    Faixa("HSK 2", "A2"),
                    Faixa("HSK 3", "A2"),
                    Faixa("HSK 4", "B1"),
                    Faixa("HSK 5", "B2"),
                    Faixa("HSK 6", "C1"),
                ),
            ),
        ),
    ),
    Idioma(
        codigo="ko",
        nome="Coreano",
        nativo="한국어",
        exames=(
            _CEFR,
            Exame(
                id="topik",
                nome="TOPIK",
                descricao="TOPIK I cobre os níveis 1 e 2; TOPIK II vai do 3 ao 6.",
                faixas=(
                    Faixa("TOPIK 1", "A1"),
                    Faixa("TOPIK 2", "A2"),
                    Faixa("TOPIK 3", "B1"),
                    Faixa("TOPIK 4", "B2"),
                    Faixa("TOPIK 5", "C1"),
                    Faixa("TOPIK 6", "C2"),
                ),
            ),
        ),
    ),
    Idioma(
        codigo="pt",
        nome="Português",
        nativo="Português",
        exames=(
            _CEFR,
            Exame(
                id="celpe_bras",
                nome="Celpe-Bras",
                descricao="Único certificado de português brasileiro reconhecido oficialmente.",
                faixas=(
                    Faixa("Intermediário", "B1"),
                    Faixa("Intermediário Superior", "B2"),
                    Faixa("Avançado", "C1"),
                    Faixa("Avançado Superior", "C2"),
                ),
            ),
        ),
    ),
)

_POR_CODIGO = {item.codigo: item for item in IDIOMAS}


def idioma(codigo: str) -> Optional[Idioma]:
    return _POR_CODIGO.get((codigo or "").strip().lower())


def existe(codigo: str) -> bool:
    return idioma(codigo) is not None


def exame(codigo_idioma: str, id_exame: str) -> Optional[Exame]:
    alvo = idioma(codigo_idioma)
    if not alvo:
        return None
    return next((e for e in alvo.exames if e.id == (id_exame or "").strip().lower()), None)


def cefr_da_meta(codigo_idioma: str, id_exame: str, rotulo: str) -> Optional[str]:
    """"7.0" no IELTS -> "C1". É o que faz a meta virar algo mensurável.

    Sem isto a meta seria texto solto: o nivelamento mede em CEFR, e sem
    converter não haveria como dizer se a pessoa chegou onde queria.
    """
    alvo = exame(codigo_idioma, id_exame)
    if not alvo:
        return None
    return next((f.cefr for f in alvo.faixas if f.rotulo == rotulo), None)


def meta_no_exame(codigo_idioma: str, id_exame: str, cefr: str) -> Optional[str]:
    """O caminho inverso: "C1" -> "7.0". Para a tela mostrar o nível medido na
    régua que a pessoa escolheu, e não na interna.

    Devolve a MENOR faixa que alcança o CEFR pedido — quem chegou em C1 chegou
    em 7.0, e anunciar 8.0 seria dar por certo o que não foi medido.
    """
    alvo = exame(codigo_idioma, id_exame)
    if not alvo:
        return None
    return next((f.rotulo for f in alvo.faixas if f.cefr == cefr), None)


def catalogo() -> list[dict]:
    """O catálogo como JSON, para o frontend montar a tela sem repetir a
    tabela de equivalências do lado dele."""
    return [
        {
            "codigo": item.codigo,
            "nome": item.nome,
            "nativo": item.nativo,
            "exames": [
                {
                    "id": e.id,
                    "nome": e.nome,
                    "descricao": e.descricao,
                    "faixas": [
                        {"rotulo": f.rotulo, "cefr": f.cefr, "nota": f.nota} for f in e.faixas
                    ],
                }
                for e in item.exames
            ],
        }
        for item in IDIOMAS
    ]
