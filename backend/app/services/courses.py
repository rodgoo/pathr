"""Cursos com certificado, para o perfil do LinkedIn.

## Por que um catálogo curado, e não a IA nem a busca

O valor de cada item aqui é o CERTIFICADO: a linha que a pessoa vai colocar
no LinkedIn e que um recrutador vai conferir. Um curso inventado, um
certificado que não existe ou um "gratuito" que cobra na última aula quebra a
única promessa da tela. A IA inventa com a mesma confiança com que acerta, e a
busca acha a página do curso mas não diz se o certificado é pago. Por isso
cada entrada foi escolhida à mão, com emissor reconhecido.

A contrapartida é a cobertura: tecnologia sem certificação séria (Next.js, Go,
Rust) fica sem curso, em vez de ganhar um qualquer.

## Gratuito primeiro, sempre

A ordenação põe TODO certificado gratuito antes de qualquer pago, e só dentro
de cada grupo pesa relevância e demanda. Um pago muito relevante não passa na
frente de um gratuito pouco relevante: quem está começando a carreira precisa
ver primeiro o que pode fazer sem gastar.

## Condições mudam

Preço e gratuidade são dos emissores, e eles mudam. `CONFERIDO_EM` diz quando
a tabela foi revisada, e a tela mostra isso junto de "confira no site".

## A demanda

`demanda` vai de 0 a 100 e mede o quanto aquele CONTEÚDO pesa hoje numa vaga:
cloud, contêineres e IA no alto; HTML, Git e Scrum introdutório embaixo. Não
é qualidade do curso: um curso básico excelente continua sendo o básico que
todo mundo já tem no perfil.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.services.tag_catalog import slugify
from app.services.tag_seed import SEED

# A categoria de cada tecnologia, pelo catálogo de tags: é o que a tela de
# cursos usa para filtrar ("Cloud", "Dados"), sem uma segunda classificação
# para manter em sincronia.
_CATEGORIA_DA_TAG = {slugify(nome): categoria for nome, categoria, _pop, _apelidos in SEED}

CONFERIDO_EM = "2026-05"


@dataclass(frozen=True)
class Curso:
    id: str
    titulo: str
    emissor: str
    url: str
    tags: tuple[str, ...]  # nomes do catálogo de tags (tag_seed.SEED)
    nivel: str  # iniciante | intermediario | avancado
    idioma: str  # pt | en
    gratuito: bool  # o CERTIFICADO, não só as aulas
    custo: str
    demanda: int  # 0..100
    horas: Optional[int] = None


# Os motivos de demanda se repetem por assunto; um texto por assunto evita
# vinte variações da mesma frase.
_NUVEM = "Cloud aparece como requisito em boa parte das vagas de backend e DevOps."
_CONTEINER = "Contêineres e Kubernetes estão entre as habilidades mais pedidas em infra."
_IA = "IA generativa é a área que mais abriu vagas nos últimos anos."
_SEGURANCA = "Segurança tem falta crônica de profissionais."
_BASICO = "Conteúdo de base: esperado de todo mundo, pouco diferencia no perfil."

MOTIVO_DEMANDA: dict[str, str] = {
    "AWS": _NUVEM,
    "Azure": _NUVEM,
    "Google Cloud": _NUVEM,
    "Kubernetes": _CONTEINER,
    "Docker": _CONTEINER,
    "Terraform": "Infraestrutura como código virou padrão em times de plataforma.",
    "LLM": _IA,
    "Machine Learning": _IA,
    "Segurança": _SEGURANCA,
    "Spring Boot": "Spring segue dominante no backend Java corporativo.",
    "React": "React é o framework de frontend mais pedido.",
    "Kafka": "Mensageria é diferencial em vagas de backend pleno e sênior.",
    "Spark": "Engenharia de dados paga bem e tem pouca gente certificada.",
}

CURSOS: tuple[Curso, ...] = (
    # ── Certificado gratuito ────────────────────────────────────────────
    Curso("fcc-responsive-web", "Responsive Web Design", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/2022/responsive-web-design/",
          ("HTML", "CSS", "Acessibilidade"), "iniciante", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 25, 300),
    Curso("fcc-javascript", "JavaScript Algorithms and Data Structures", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures-v8/",
          ("JavaScript", "Algoritmos"), "iniciante", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 55, 300),
    Curso("fcc-frontend-libs", "Front End Development Libraries", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/front-end-development-libraries/",
          ("React", "Redux", "Sass"), "intermediario", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 72, 300),
    Curso("fcc-backend-apis", "Back End Development and APIs", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/back-end-development-and-apis/",
          ("Node.js", "Express", "MongoDB", "REST"), "intermediario", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 68, 300),
    Curso("fcc-relational-db", "Relational Database", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/relational-database/",
          ("SQL", "PostgreSQL", "Shell Script", "Git"), "iniciante", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 55, 300),
    Curso("fcc-python", "Scientific Computing with Python", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/scientific-computing-with-python/",
          ("Python", "Algoritmos"), "iniciante", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 62, 300),
    Curso("fcc-data-analysis", "Data Analysis with Python", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/data-analysis-with-python/",
          ("Python", "Pandas"), "intermediario", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 72, 300),
    Curso("fcc-machine-learning", "Machine Learning with Python", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/machine-learning-with-python/",
          ("Machine Learning", "Python"), "intermediario", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 82, 300),
    Curso("fcc-quality-assurance", "Quality Assurance", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/quality-assurance/",
          ("Testes automatizados", "Node.js"), "intermediario", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 60, 300),
    Curso("fcc-information-security", "Information Security", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/information-security/",
          ("Segurança", "Node.js", "Python"), "intermediario", "en", True,
          "Aulas e certificado gratuitos; exige 5 projetos aprovados.", 78, 300),
    Curso("fcc-csharp", "Foundational C# with Microsoft", "freeCodeCamp",
          "https://www.freecodecamp.org/learn/foundational-c-sharp-with-microsoft/",
          ("C#", ".NET"), "iniciante", "en", True,
          "Aulas, prova e certificado gratuitos, em parceria com a Microsoft.", 62, 35),
    Curso("kaggle-python", "Python", "Kaggle Learn",
          "https://www.kaggle.com/learn/python",
          ("Python",), "iniciante", "en", True,
          "Curso curto; certificado gratuito ao terminar os exercícios.", 45, 5),
    Curso("kaggle-pandas", "Pandas", "Kaggle Learn",
          "https://www.kaggle.com/learn/pandas",
          ("Pandas", "Python"), "iniciante", "en", True,
          "Curso curto; certificado gratuito ao terminar os exercícios.", 58, 4),
    Curso("kaggle-intro-ml", "Intro to Machine Learning", "Kaggle Learn",
          "https://www.kaggle.com/learn/intro-to-machine-learning",
          ("Machine Learning", "Python"), "iniciante", "en", True,
          "Curso curto; certificado gratuito ao terminar os exercícios.", 72, 3),
    Curso("kaggle-intro-sql", "Intro to SQL", "Kaggle Learn",
          "https://www.kaggle.com/learn/intro-to-sql",
          ("SQL",), "iniciante", "en", True,
          "Curso curto; certificado gratuito ao terminar os exercícios.", 42, 3),
    Curso("cs50x", "CS50x: Introduction to Computer Science", "Harvard (CS50)",
          "https://cs50.harvard.edu/x/",
          ("Algoritmos", "C", "Python", "SQL"), "iniciante", "en", True,
          "Certificado gratuito emitido pelo CS50; o certificado verificado do edX é pago.", 65, 100),
    Curso("cs50p", "CS50P: Introduction to Programming with Python", "Harvard (CS50)",
          "https://cs50.harvard.edu/python/",
          ("Python",), "iniciante", "en", True,
          "Certificado gratuito emitido pelo CS50; o certificado verificado do edX é pago.", 55, 80),
    Curso("cs50w", "CS50W: Web Programming with Python and JavaScript", "Harvard (CS50)",
          "https://cs50.harvard.edu/web/",
          ("Django", "JavaScript", "Python", "SQL", "Git"), "intermediario", "en", True,
          "Certificado gratuito emitido pelo CS50; o certificado verificado do edX é pago.", 70, 120),
    Curso("cs50ai", "CS50AI: Introduction to Artificial Intelligence with Python", "Harvard (CS50)",
          "https://cs50.harvard.edu/ai/",
          ("Machine Learning", "Python", "Algoritmos"), "intermediario", "en", True,
          "Certificado gratuito emitido pelo CS50; o certificado verificado do edX é pago.", 85, 70),
    Curso("netacad-cybersecurity", "Introduction to Cybersecurity", "Cisco Networking Academy",
          "https://www.netacad.com/courses/introduction-to-cybersecurity",
          ("Segurança",), "iniciante", "en", True,
          "Curso, certificado e selo digital (Credly) gratuitos.", 70, 6),
    Curso("netacad-python-1", "Python Essentials 1", "Cisco Networking Academy",
          "https://www.netacad.com/courses/python-essentials-1",
          ("Python",), "iniciante", "en", True,
          "Curso, certificado e selo digital gratuitos; prepara para a prova PCEP (paga).", 50, 30),
    Curso("netacad-javascript-1", "JavaScript Essentials 1", "Cisco Networking Academy",
          "https://www.netacad.com/courses/javascript-essentials-1",
          ("JavaScript",), "iniciante", "en", True,
          "Curso, certificado e selo digital gratuitos.", 48, 30),
    Curso("netacad-linux-unhatched", "Linux Unhatched", "Cisco Networking Academy",
          "https://www.netacad.com/courses/ndg-linux-unhatched",
          ("Linux", "Shell Script"), "iniciante", "en", True,
          "Curso e certificado gratuitos.", 40, 8),
    Curso("aws-cloud-practitioner-essentials", "AWS Cloud Practitioner Essentials", "AWS Skill Builder",
          "https://skillbuilder.aws/",
          ("AWS",), "iniciante", "en", True,
          "Curso e certificado de conclusão gratuitos; não é a certificação AWS, que é uma prova paga.", 78, 6),
    Curso("hf-agents", "AI Agents Course", "Hugging Face",
          "https://huggingface.co/learn/agents-course",
          ("LLM", "Python"), "intermediario", "en", True,
          "Curso e certificado gratuitos ao entregar as atividades.", 95, 40),
    Curso("databricks-fundamentals", "Databricks Fundamentals", "Databricks Academy",
          "https://www.databricks.com/resources/learn/training/databricks-fundamentals",
          ("Spark", "ETL"), "iniciante", "en", True,
          "Vídeos curtos e um quiz; o selo digital sai gratuito.", 72, 2),
    Curso("mongodb-skill-badges", "MongoDB Skill Badges", "MongoDB University",
          "https://learn.mongodb.com/skills",
          ("MongoDB",), "iniciante", "en", True,
          "Selos digitais gratuitos por tema, com prova curta.", 52, 2),
    Curso("scrumstudy-sfc", "Scrum Fundamentals Certified (SFC)", "SCRUMstudy",
          "https://www.scrumstudy.com/certification/scrum-fundamentals-certified",
          ("Scrum",), "iniciante", "en", True,
          "Curso e prova gratuitos.", 35, 10),
    Curso("ef-set", "EF SET English Certificate", "EF Education First",
          "https://www.efset.org/",
          ("Inglês",), "iniciante", "en", True,
          "Prova e certificado gratuitos, com nível CEFR.", 80, 1),
    Curso("helsinki-java", "Java Programming", "University of Helsinki (MOOC.fi)",
          "https://java-programming.mooc.fi/",
          ("Java", "Algoritmos"), "iniciante", "en", True,
          "Curso gratuito; o certificado de conclusão sai grátis no perfil do MOOC.fi.", 60, 150),
    # ── Certificado pago ────────────────────────────────────────────────
    Curso("aws-ccp", "AWS Certified Cloud Practitioner", "Amazon Web Services",
          "https://aws.amazon.com/certification/certified-cloud-practitioner/",
          ("AWS",), "iniciante", "en", False,
          "Prova paga (cerca de US$ 100). Treino gratuito no AWS Skill Builder.", 85),
    Curso("aws-developer", "AWS Certified Developer – Associate", "Amazon Web Services",
          "https://aws.amazon.com/certification/certified-developer-associate/",
          ("AWS",), "intermediario", "en", False,
          "Prova paga (cerca de US$ 150).", 92),
    Curso("aws-ai-practitioner", "AWS Certified AI Practitioner", "Amazon Web Services",
          "https://aws.amazon.com/certification/certified-ai-practitioner/",
          ("LLM", "Machine Learning", "AWS"), "iniciante", "en", False,
          "Prova paga (cerca de US$ 100).", 90),
    Curso("az-900", "Microsoft Azure Fundamentals (AZ-900)", "Microsoft",
          "https://learn.microsoft.com/credentials/certifications/azure-fundamentals/",
          ("Azure",), "iniciante", "pt", False,
          "Treino gratuito no Microsoft Learn; a prova é paga (preço regional).", 72),
    Curso("az-204", "Azure Developer Associate (AZ-204)", "Microsoft",
          "https://learn.microsoft.com/credentials/certifications/azure-developer/",
          ("Azure", ".NET"), "intermediario", "pt", False,
          "Treino gratuito no Microsoft Learn; a prova é paga (preço regional).", 86),
    Curso("ai-900", "Azure AI Fundamentals (AI-900)", "Microsoft",
          "https://learn.microsoft.com/credentials/certifications/azure-ai-fundamentals/",
          ("LLM", "Machine Learning", "Azure"), "iniciante", "pt", False,
          "Treino gratuito no Microsoft Learn; a prova é paga (preço regional).", 82),
    Curso("pl-300", "Power BI Data Analyst Associate (PL-300)", "Microsoft",
          "https://learn.microsoft.com/credentials/certifications/data-analyst-associate/",
          ("Power BI",), "intermediario", "pt", False,
          "Treino gratuito no Microsoft Learn; a prova é paga (preço regional).", 70),
    Curso("gcp-digital-leader", "Cloud Digital Leader", "Google Cloud",
          "https://cloud.google.com/learn/certification/cloud-digital-leader",
          ("Google Cloud",), "iniciante", "en", False,
          "Prova paga (cerca de US$ 99).", 62),
    Curso("github-foundations", "GitHub Foundations", "GitHub",
          "https://learn.github.com/certifications",
          ("Git",), "iniciante", "en", False,
          "Prova paga (cerca de US$ 99).", 40),
    Curso("github-actions", "GitHub Actions", "GitHub",
          "https://learn.github.com/certifications",
          ("GitHub Actions", "CI/CD"), "intermediario", "en", False,
          "Prova paga (cerca de US$ 99).", 70),
    Curso("kcna", "Kubernetes and Cloud Native Associate (KCNA)", "The Linux Foundation (CNCF)",
          "https://training.linuxfoundation.org/certification/kubernetes-cloud-native-associate/",
          ("Kubernetes", "Docker"), "iniciante", "en", False,
          "Prova paga (cerca de US$ 250); costuma ter desconto em datas promocionais.", 84),
    Curso("ckad", "Certified Kubernetes Application Developer (CKAD)", "The Linux Foundation (CNCF)",
          "https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/",
          ("Kubernetes", "Docker"), "avancado", "en", False,
          "Prova prática paga (cerca de US$ 445).", 95),
    Curso("docker-foundations", "Docker Foundations Professional Certificate", "Docker (LinkedIn Learning)",
          "https://www.linkedin.com/learning/paths/docker-foundations-professional-certificate",
          ("Docker",), "iniciante", "en", False,
          "Exige assinatura do LinkedIn Learning; o primeiro mês costuma ser gratuito.", 86),
    Curso("terraform-associate", "HashiCorp Certified: Terraform Associate", "HashiCorp",
          "https://developer.hashicorp.com/certifications/infrastructure-automation",
          ("Terraform",), "intermediario", "en", False,
          "Prova paga (cerca de US$ 70).", 84),
    Curso("isc2-cc", "Certified in Cybersecurity (CC)", "ISC2",
          "https://www.isc2.org/certifications/cc",
          ("Segurança",), "iniciante", "en", False,
          "Prova paga. O programa que a dava de graça (One Million Certified) fechou inscrições em maio de 2026.", 85),
    Curso("oracle-java-21", "Oracle Certified Professional: Java SE 21 Developer", "Oracle",
          "https://education.oracle.com/java-se-21-developer-professional/pexam_1Z0-830",
          ("Java",), "avancado", "en", False,
          "Prova paga (cerca de US$ 245).", 78),
    Curso("oracle-sql", "Oracle Database SQL Certified Associate", "Oracle",
          "https://education.oracle.com/oracle-database-sql/pexam_1Z0-071",
          ("SQL", "Oracle"), "intermediario", "en", False,
          "Prova paga (cerca de US$ 245).", 50),
    Curso("spring-professional", "Spring Certified Professional", "Broadcom (Spring)",
          "https://spring.academy/",
          ("Spring Boot", "JPA", "Spring Security"), "intermediario", "en", False,
          "Cursos no Spring Academy; a prova de certificação é paga.", 84),
    Curso("pcep", "PCEP – Certified Entry-Level Python Programmer", "Python Institute",
          "https://pythoninstitute.org/pcep",
          ("Python",), "iniciante", "en", False,
          "Prova paga (cerca de US$ 59). Preparação gratuita no Python Essentials 1.", 45),
    Curso("meta-frontend", "Meta Front-End Developer Professional Certificate", "Meta (Coursera)",
          "https://www.coursera.org/professional-certificates/meta-front-end-developer",
          ("React", "JavaScript", "HTML", "CSS"), "iniciante", "en", False,
          "Certificado exige assinatura do Coursera; há auxílio financeiro.", 70),
    Curso("meta-backend", "Meta Back-End Developer Professional Certificate", "Meta (Coursera)",
          "https://www.coursera.org/professional-certificates/meta-back-end-developer",
          ("Django", "Python", "REST", "MySQL"), "iniciante", "en", False,
          "Certificado exige assinatura do Coursera; há auxílio financeiro.", 68),
    Curso("ibm-fullstack", "IBM Full Stack Software Developer Professional Certificate", "IBM (Coursera)",
          "https://www.coursera.org/professional-certificates/ibm-full-stack-cloud-developer",
          ("Node.js", "React", "Docker", "Kubernetes", "Microsserviços"), "intermediario", "en", False,
          "Certificado exige assinatura do Coursera; há auxílio financeiro.", 80),
    Curso("genai-llms", "Generative AI with Large Language Models", "DeepLearning.AI e AWS (Coursera)",
          "https://www.coursera.org/learn/generative-ai-with-llms",
          ("LLM", "Machine Learning"), "intermediario", "en", False,
          "Certificado exige assinatura do Coursera; há auxílio financeiro.", 90),
    Curso("software-architecture", "Software Design and Architecture", "University of Alberta (Coursera)",
          "https://www.coursera.org/specializations/software-design-architecture",
          ("Arquitetura de software", "Clean Code"), "intermediario", "en", False,
          "Certificado exige assinatura do Coursera; há auxílio financeiro.", 62),
    Curso("psm-1", "Professional Scrum Master I (PSM I)", "Scrum.org",
          "https://www.scrum.org/assessments/professional-scrum-master-i-certification",
          ("Scrum",), "intermediario", "en", False,
          "Prova paga (cerca de US$ 200), sem validade.", 52),
    Curso("ctfl", "Certified Tester Foundation Level (CTFL)", "ISTQB / BSTQB",
          "https://bstqb.online/",
          ("Testes automatizados",), "iniciante", "pt", False,
          "Prova paga, aplicada em português pelo BSTQB.", 55),
    Curso("mongodb-associate", "MongoDB Associate Developer", "MongoDB",
          "https://learn.mongodb.com/pages/mongodb-associate-developer-exam",
          ("MongoDB",), "intermediario", "en", False,
          "Prova paga (cerca de US$ 150). Treino gratuito no MongoDB University.", 62),
    Curso("comptia-security", "CompTIA Security+", "CompTIA",
          "https://www.comptia.org/certifications/security",
          ("Segurança",), "intermediario", "en", False,
          "Prova paga (cerca de US$ 400).", 86),
    Curso("lpi-linux-essentials", "Linux Essentials", "Linux Professional Institute",
          "https://www.lpi.org/our-certifications/linux-essentials-overview/",
          ("Linux",), "iniciante", "pt", False,
          "Prova paga, com preço regional.", 45),
)

# Faixas da barra de chama. O limite é o menor valor de cada faixa.
FAIXAS: tuple[tuple[int, str, str], ...] = (
    (85, "pegando_fogo", "Pegando fogo"),
    (70, "em_alta", "Em alta"),
    (50, "procurado", "Procurado"),
    (35, "comum", "Comum"),
    (0, "basico", "Chama apagada"),
)

# Quanto cada sinal pesa. A meta declarada é a própria pessoa dizendo o que
# quer; o roadmap é o plano que ela aceitou; o texto do objetivo é a pista mais
# fraca, porque é casado por palavra.
PESO_META = 3
PESO_ROADMAP = 2
PESO_OBJETIVO = 1


def faixa_de(demanda: int) -> tuple[str, str]:
    for limite, chave, rotulo in FAIXAS:
        if demanda >= limite:
            return chave, rotulo
    return FAIXAS[-1][1], FAIXAS[-1][2]


def _normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    # O ponto fica quando faz parte do nome (".NET", "Node.js") e sai quando
    # fecha a frase: "quero aprender Java." precisa casar "java".
    sem_pontuacao = re.sub(r"\.(?![a-z0-9])", " ", sem_acento)
    return f" {re.sub(r'[^a-z0-9#+.]+', ' ', sem_pontuacao)} "


def tags_no_texto(texto: str) -> set[str]:
    """As tags do catálogo de cursos citadas num texto livre ("quero ser dev
    Java com AWS"). Casa por palavra inteira: "Java" não pode acender em
    "JavaScript". Nomes curtos só de letras (C, Go) ficam de fora — no meio
    de uma frase em português, "c" é quase sempre outra coisa. Com símbolo
    ("C#") não há essa ambiguidade."""
    alvo = _normaliza(texto)
    achadas: set[str] = set()
    for nome in {tag for curso in CURSOS for tag in curso.tags}:
        chave = _normaliza(nome).strip()
        if (len(chave) >= 3 or not chave.isalnum()) and f" {chave} " in alvo:
            achadas.add(slugify(nome))
    return achadas


def recomendar(
    user_tags: Iterable[dict[str, Any]],
    slugs_do_roadmap: Iterable[str] = (),
    objetivo: str = "",
    todos: bool = False,
) -> list[dict[str, Any]]:
    """Os cursos que servem ao que a pessoa quer aprender, já ordenados.

    `user_tags` tem a forma de `GET /tags/mine` (slug, name, proficiency,
    is_target). Só entram cursos com pelo menos uma tag pedida: esta tela
    responde "o que eu quero aprender", não "tudo que existe" — a não ser com
    `todos`, que é a busca no catálogo inteiro. Ali o curso sem pedido entra
    com relevância zero e sem motivo, depois dos pedidos.
    """
    pesos: dict[str, int] = {}
    motivos: dict[str, str] = {}
    nomes: dict[str, str] = {}

    def marca(slug: str, peso: int, motivo: str) -> None:
        if peso > pesos.get(slug, 0):
            pesos[slug] = peso
            motivos[slug] = motivo

    # Tecnologia que está no perfil SEM ser meta foi uma decisão: "isto não é
    # para agora". Ela não traz curso nem pelo roadmap nem pelo objetivo —
    # desmarcar a meta e continuar vendo o curso dela era dizer que a escolha
    # não valeu.
    fora: set[str] = set()
    for tag in user_tags:
        slug = str(tag.get("slug") or slugify(str(tag.get("name") or "")))
        if not slug:
            continue
        nomes[slug] = str(tag.get("name") or slug)
        if tag.get("is_target"):
            marca(slug, PESO_META, "meta")
        else:
            fora.add(slug)
    for slug in slugs_do_roadmap:
        if slug not in fora:
            marca(slug, PESO_ROADMAP, "roadmap")
    for slug in tags_no_texto(objetivo):
        if slug not in fora:
            marca(slug, PESO_OBJETIVO, "objetivo")

    resultado = []
    for curso in CURSOS:
        casadas = [slugify(nome) for nome in curso.tags if slugify(nome) in pesos]
        if not casadas and not todos:
            continue
        relevancia = sum(pesos[slug] for slug in casadas)
        chave, rotulo = faixa_de(curso.demanda)
        tag_quente = next((nome for nome in curso.tags if nome in MOTIVO_DEMANDA), None)
        resultado.append(
            {
                "id": curso.id,
                "titulo": curso.titulo,
                "emissor": curso.emissor,
                "url": curso.url,
                "tags": list(curso.tags),
                "categorias": sorted(
                    {_CATEGORIA_DA_TAG[slugify(nome)] for nome in curso.tags if slugify(nome) in _CATEGORIA_DA_TAG}
                ),
                "nivel": curso.nivel,
                "idioma": curso.idioma,
                "horas": curso.horas,
                "certificado": {"gratuito": curso.gratuito, "detalhe": curso.custo},
                "demanda": {
                    "nota": curso.demanda,
                    "faixa": chave,
                    "rotulo": rotulo,
                    "motivo": MOTIVO_DEMANDA[tag_quente]
                    if tag_quente
                    else (_BASICO if curso.demanda < 50 else None),
                },
                "motivos": [
                    {"tipo": motivos[slug], "tag": nomes.get(slug) or _nome_do_slug(curso, slug)}
                    for slug in casadas
                ],
                "relevancia": relevancia,
            }
        )

    # Gratuito primeiro, SEMPRE — ver o docstring do módulo.
    resultado.sort(
        key=lambda item: (
            not item["certificado"]["gratuito"],
            -item["relevancia"],
            -item["demanda"]["nota"],
            item["titulo"],
        )
    )
    return resultado


_POR_ID = {curso.id: curso for curso in CURSOS}


def por_id(course_id: str) -> Optional[Curso]:
    return _POR_ID.get(course_id)


def resumido(curso: Curso) -> dict[str, Any]:
    """O curso como aparece em Perfil e tags: o suficiente para mostrar e
    adicionar ao LinkedIn, sem a relevância, que depende das metas."""
    return {
        "id": curso.id,
        "titulo": curso.titulo,
        "emissor": curso.emissor,
        "url": curso.url,
        "tags": list(curso.tags),
        "gratuito": curso.gratuito,
    }


def _nome_do_slug(curso: Curso, slug: str) -> str:
    return next((nome for nome in curso.tags if slugify(nome) == slug), slug)
