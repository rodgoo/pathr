"""Semente do catálogo global de tecnologias.

Não pretende ser exaustiva — o catálogo cresce sozinho quando um currículo
cita algo que falta (ver tag_catalog.TagCatalog.create). O que está aqui é o
que precisa existir ANTES do primeiro currículo: os nomes que aparecem em
praticamente todo CV de tecnologia, com os apelidos que as pessoas realmente
escrevem. Sem os apelidos, "postgres" viraria uma tag separada de
"PostgreSQL" no primeiro upload, e o catálogo nasceria duplicado.

`popularity` ordena o autocomplete: quanto maior, mais acima.
"""

# (nome, categoria, popularidade, apelidos)
SEED: list[tuple[str, str, int, list[str]]] = [
    # Linguagens
    ("JavaScript", "linguagem", 100, ["js", "ecmascript", "es6"]),
    ("TypeScript", "linguagem", 95, ["ts"]),
    ("Python", "linguagem", 95, ["py", "python3"]),
    ("Java", "linguagem", 90, ["java se", "java ee", "jdk"]),
    ("C#", "linguagem", 80, ["csharp", "c sharp", "dotnet c#"]),
    ("Go", "linguagem", 70, ["golang"]),
    ("PHP", "linguagem", 70, []),
    ("Ruby", "linguagem", 60, []),
    ("Kotlin", "linguagem", 60, []),
    ("Swift", "linguagem", 55, []),
    ("Rust", "linguagem", 55, []),
    ("C++", "linguagem", 50, ["cpp", "c plus plus"]),
    ("C", "linguagem", 45, []),
    ("SQL", "linguagem", 90, ["ansi sql"]),
    ("Shell Script", "linguagem", 45, ["bash", "shell", "sh", "zsh"]),
    # Frontend
    ("React", "frontend", 100, ["react.js", "reactjs", "react js"]),
    ("Next.js", "frontend", 80, ["nextjs", "next"]),
    ("Vue.js", "frontend", 70, ["vue", "vuejs", "vue 3"]),
    ("Angular", "frontend", 70, ["angularjs", "angular 2+"]),
    ("Svelte", "frontend", 40, ["sveltekit"]),
    ("HTML", "frontend", 90, ["html5"]),
    ("CSS", "frontend", 90, ["css3"]),
    ("Sass", "frontend", 55, ["scss"]),
    ("Tailwind CSS", "frontend", 65, ["tailwind", "tailwindcss"]),
    ("Redux", "frontend", 55, ["redux toolkit"]),
    ("Vite", "ferramenta", 50, []),
    ("Webpack", "ferramenta", 45, []),
    ("Acessibilidade", "frontend", 40, ["a11y", "wcag"]),
    # Backend e frameworks
    ("Node.js", "backend", 90, ["node", "nodejs", "node js"]),
    ("Express", "backend", 65, ["express.js", "expressjs"]),
    ("NestJS", "backend", 50, ["nest.js", "nest"]),
    ("Spring Boot", "backend", 85, ["springboot", "spring"]),
    ("Spring Security", "backend", 45, []),
    ("Django", "backend", 70, []),
    ("Flask", "backend", 55, []),
    ("FastAPI", "backend", 60, []),
    ("Laravel", "backend", 60, []),
    ("Rails", "backend", 45, ["ruby on rails"]),
    (".NET", "backend", 70, ["dotnet", "asp.net", "net core", "asp net core"]),
    ("JPA", "backend", 60, ["hibernate", "spring data jpa", "jakarta persistence"]),
    ("REST", "arquitetura", 85, ["rest api", "api rest", "restful"]),
    ("GraphQL", "arquitetura", 50, []),
    ("gRPC", "arquitetura", 35, []),
    ("WebSocket", "arquitetura", 40, ["websockets"]),
    # Dados
    ("PostgreSQL", "banco", 85, ["postgres", "psql", "pg"]),
    ("MySQL", "banco", 80, ["mariadb"]),
    ("SQL Server", "banco", 60, ["sqlserver", "mssql", "t-sql"]),
    ("Oracle", "banco", 50, ["oracle db", "pl/sql"]),
    ("MongoDB", "banco", 70, ["mongo"]),
    ("Redis", "banco", 60, []),
    ("Elasticsearch", "banco", 40, ["elastic", "opensearch"]),
    ("Modelagem de dados", "dados", 55, ["modelagem", "data modeling", "er"]),
    ("Kafka", "dados", 50, ["apache kafka"]),
    ("RabbitMQ", "dados", 45, ["rabbit"]),
    ("ETL", "dados", 45, ["pipeline de dados", "data pipeline"]),
    ("Power BI", "dados", 45, ["powerbi"]),
    ("Pandas", "dados", 50, []),
    ("Spark", "dados", 35, ["apache spark", "pyspark"]),
    # Infra e entrega
    ("Docker", "devops", 85, ["containers", "docker compose"]),
    ("Kubernetes", "devops", 60, ["k8s", "kube"]),
    ("CI/CD", "devops", 75, ["ci cd", "integracao continua", "pipeline"]),
    ("GitHub Actions", "devops", 55, ["gh actions"]),
    ("Jenkins", "devops", 40, []),
    ("Terraform", "devops", 45, ["iac"]),
    ("AWS", "cloud", 80, ["amazon web services", "ec2", "s3", "lambda"]),
    ("Azure", "cloud", 60, ["microsoft azure"]),
    ("Google Cloud", "cloud", 45, ["gcp", "google cloud platform"]),
    ("Linux", "devops", 70, ["unix", "ubuntu", "debian"]),
    ("Nginx", "devops", 45, []),
    ("Observabilidade", "devops", 40, ["monitoramento", "grafana", "prometheus", "datadog"]),
    # Qualidade e ofício
    ("Git", "ferramenta", 90, ["github", "gitlab", "controle de versao"]),
    ("Testes automatizados", "testes", 70, ["testes", "test", "qa", "tdd"]),
    ("JUnit", "testes", 45, []),
    ("Jest", "testes", 50, []),
    ("Cypress", "testes", 40, ["playwright", "e2e"]),
    ("Pytest", "testes", 40, []),
    ("Arquitetura de software", "arquitetura", 65, ["arquitetura", "system design", "ddd"]),
    ("Microsserviços", "arquitetura", 55, ["microservices", "microservicos"]),
    ("Clean Code", "metodologia", 45, ["codigo limpo", "solid"]),
    ("Algoritmos", "metodologia", 55, ["estrutura de dados", "algoritmos e estruturas de dados"]),
    ("Code review", "metodologia", 45, ["revisao de codigo"]),
    ("Scrum", "metodologia", 60, ["agile", "agil", "kanban"]),
    ("Segurança", "seguranca", 45, ["security", "owasp", "appsec"]),
    # Mobile e IA
    ("React Native", "mobile", 50, ["react-native"]),
    ("Flutter", "mobile", 45, ["dart"]),
    ("Android", "mobile", 45, []),
    ("iOS", "mobile", 40, []),
    ("Machine Learning", "ia", 50, ["ml", "aprendizado de maquina"]),
    ("LLM", "ia", 40, ["llms", "genai", "ia generativa", "openai"]),
    # Idiomas
    ("Inglês", "idioma", 80, ["english", "ingles"]),
    ("Espanhol", "idioma", 40, ["spanish", "espanol"]),
]


def seed_rows() -> list[dict]:
    from app.services.tag_catalog import CATEGORY_COLORS, slugify

    return [
        {
            "slug": slugify(name),
            "name": name,
            "category": category,
            "color": CATEGORY_COLORS.get(category),
            "aliases": aliases,
            "popularity": popularity,
        }
        for name, category, popularity, aliases in SEED
    ]
