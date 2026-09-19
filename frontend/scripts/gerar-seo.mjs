/**
 * Gera as páginas públicas de SEO do PathR (guias e roadmaps) e o sitemap.
 *
 *   cd frontend && node scripts/gerar-seo.mjs
 *
 * ## Por que páginas estáticas, e não uma rota do app
 *
 * O app é uma SPA: o conteúdo aparece depois que o JavaScript roda. O Google
 * até renderiza JS, mas devagar e sem garantia, e nenhuma página do app é
 * pública — tudo fica atrás de login. Para rankear em "como estudar
 * programação" ou "roadmap java", o buscador precisa de HTML com o texto JÁ
 * dentro. Estas páginas são isso: arquivos estáticos em `public/`, que a
 * Cloudflare serve antes do rewrite do SPA (`/* -> /index.html`), com o
 * conteúdo, o Q&A e o `FAQPage`/`Article` em JSON-LD prontos no HTML.
 *
 * Não é truque de ranqueamento — é conteúdo de verdade que responde a busca e
 * leva para o cadastro. Ranquear no topo depende disto + tempo + links de fora;
 * atalho não existe, e o que promete "sempre no topo" hoje derruba o site.
 *
 * Conteúdo novo entra numa entrada de `TOPICOS`. O gerador cuida do HTML, do
 * FAQ estruturado, dos links internos e do sitemap.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const PUBLIC = join(AQUI, "..", "public");
const BASE = "https://pathr.notter.com.br";
const APP = `${BASE}/`;
const OG_IMG = `${BASE}/icons/icon-512.png`;
const HOJE = new Date().toISOString().slice(0, 10);

/** tipo: "guia" | "roadmap"; o tipo vira o primeiro segmento da URL. */
const PASTA = { guia: "guias", roadmap: "roadmap" };
const ROTULO = { guia: "Guias", roadmap: "Roadmaps" };

const TOPICOS = [
  {
    tipo: "guia",
    slug: "como-estudar-programacao-do-zero",
    metaTitle: "Como estudar programação do zero: guia passo a passo (2026) | PathR",
    h1: "Como estudar programação do zero",
    metaDesc:
      "Um caminho realista para aprender a programar do zero: qual linguagem escolher, quanto tempo dedicar, como praticar e não se perder em tutoriais soltos.",
    lead: "Começar é fácil; não desistir na terceira semana é o que separa quem aprende. Este guia mostra um caminho realista — sem atalho mágico, mas sem enrolação.",
    secoes: [
      {
        h2: "1. Escolha UMA linguagem e fique nela",
        paras: [
          "O erro mais comum de quem começa é pular de linguagem em linguagem. No início, a linguagem importa menos que a constância: escolha uma e dê a ela pelo menos os primeiros três meses.",
          "Para quem quer web e um mercado amplo, Python ou JavaScript resolvem. Python tem a sintaxe mais limpa para aprender lógica; JavaScript roda no navegador e abre a porta do front-end. Qualquer uma é uma boa primeira escolha.",
        ],
      },
      {
        h2: "2. Siga um roadmap, não tutoriais soltos",
        paras: [
          "Assistir a vinte vídeos desconexos ensina a copiar, não a construir. Um roadmap põe os assuntos na ordem em que um se apoia no outro: lógica e sintaxe, estruturas de dados básicas, um framework, banco de dados e, então, um projeto de verdade.",
          "A ordem importa porque cada etapa depende da anterior. Estudar um framework antes de dominar funções e laços é levantar telhado sem parede.",
        ],
      },
      {
        h2: "3. Pratique escrevendo código, não só lendo",
        paras: [
          "Programação se aprende como um idioma: usando. Para cada hora de teoria, gaste pelo menos uma escrevendo código do zero, sem copiar.",
          "Refaça exercícios depois de alguns dias — repetição espaçada. O que você consegue reescrever sem olhar é o que realmente aprendeu; o resto ainda é ilusão de entendimento.",
        ],
      },
      {
        h2: "4. Meça o progresso e ajuste toda semana",
        paras: [
          "Sem medir, é fácil estudar muito e avançar pouco. Feche cada semana revisando o que ficou pela metade e ajustando o plano ao seu ritmo real, não ao ritmo ideal de um cronograma que ignora a sua vida.",
        ],
      },
    ],
    faq: [
      {
        q: "Preciso saber matemática para programar?",
        a: "Para a maioria das áreas (web, mobile, automação), não. Você precisa de lógica e de conforto com raciocínio passo a passo. Matemática pesada só entra em nichos como jogos 3D, machine learning e criptografia.",
      },
      {
        q: "Qual linguagem devo aprender primeiro?",
        a: "Python, se quer a curva mais suave e foco em lógica e dados; JavaScript, se quer ver resultado no navegador rápido e seguir para o front-end. As duas têm muito emprego. O importante é escolher uma e não trocar nas primeiras semanas.",
      },
      {
        q: "Quanto tempo por dia preciso estudar?",
        a: "Melhor uma hora todo dia do que dez horas num sábado. A constância vence a intensidade porque programação depende de memória de longo prazo, que se constrói com repetição espaçada.",
      },
      {
        q: "Preciso de faculdade para trabalhar com programação?",
        a: "Não é obrigatória. Muita gente entra no mercado por conta própria, com projetos e um portfólio. A faculdade ajuda em fundamentos e em algumas vagas específicas, mas não é o único caminho.",
      },
    ],
  },
  {
    tipo: "guia",
    slug: "quanto-tempo-leva-para-aprender-programacao",
    metaTitle: "Quanto tempo leva para aprender programação? (resposta realista) | PathR",
    h1: "Quanto tempo leva para aprender programação?",
    metaDesc:
      "Uma resposta honesta, por marco: primeiro programa, primeiro projeto, primeiro emprego — e o que faz esse tempo encurtar ou esticar.",
    lead: "Depende do objetivo: 'aprender programação' pode ser escrever o primeiro script ou estar pronto para o mercado. Vamos por marcos concretos.",
    secoes: [
      {
        h2: "Escrever seu primeiro programa: dias",
        paras: [
          "Com uma hora por dia, em uma ou duas semanas você escreve programas pequenos que resolvem algo real: uma calculadora, um jogo de adivinhação, um script que organiza arquivos. É pouco, mas é o começo que prova que dá para seguir.",
        ],
      },
      {
        h2: "Construir um projeto do zero: 2 a 4 meses",
        paras: [
          "Sair do 'sei a sintaxe' para o 'consigo construir sozinho' costuma levar de dois a quatro meses de estudo consistente, com prática deliberada — escrevendo código sem copiar e depurando os próprios erros em vez de fugir deles.",
        ],
      },
      {
        h2: "Ficar empregável: 6 a 12 meses",
        paras: [
          "Para a primeira vaga, a maioria leva de seis meses a um ano estudando com regularidade (5 a 10 horas por semana), com alguns projetos no portfólio e o básico de uma stack completa: uma linguagem, um framework, banco de dados, Git e o essencial de testes.",
          "Esse intervalo estica ou encurta conforme três coisas: constância, prática de código real (não só vídeo) e ter um plano na ordem certa, em vez de pular de assunto a cada semana.",
        ],
      },
    ],
    faq: [
      {
        q: "Dá para aprender programação em 3 meses?",
        a: "Dá para sair do zero e construir projetos pequenos em três meses de estudo consistente. Ficar totalmente empregável nesse prazo é raro e depende de dedicação quase integral. Seis meses a um ano é o intervalo mais comum para a primeira vaga.",
      },
      {
        q: "Estudar todo dia faz diferença?",
        a: "Muita. Programação depende de memória de longo prazo, que se firma com repetição espaçada. Uma hora por dia rende mais que dez horas de uma vez, porque o cérebro consolida o aprendizado no intervalo entre as sessões.",
      },
      {
        q: "Preciso terminar um curso inteiro antes de conseguir emprego?",
        a: "Não. O que conta na entrevista é resolver problemas e mostrar projetos. Um plano que alterna teoria, prática e projeto costuma levar ao mercado mais rápido que um curso longo assistido de forma passiva.",
      },
    ],
  },
  {
    tipo: "roadmap",
    slug: "java",
    metaTitle: "Roadmap Java 2026: o que estudar para virar desenvolvedor Java | PathR",
    h1: "Roadmap para desenvolvedor Java",
    metaDesc:
      "A ordem para aprender Java de verdade: fundamentos, orientação a objetos, Spring Boot, banco de dados, testes e o que as vagas realmente pedem.",
    lead: "Java continua entre as linguagens mais pedidas em vagas de backend. Este é o caminho, na ordem em que cada assunto se apoia no anterior.",
    secoes: [
      {
        h2: "Fundamentos da linguagem",
        paras: [
          "Antes de qualquer framework: tipos, variáveis, condicionais, laços, métodos e coleções (List, Map, Set). É a base que todo o resto usa, e pulá-la cobra caro lá na frente.",
        ],
      },
      {
        h2: "Programação orientada a objetos",
        paras: [
          "Java é orientado a objetos no osso. Classes, objetos, herança, interfaces, encapsulamento e polimorfismo não são teoria opcional: é como o código Java se organiza. Domine isso antes de tocar em Spring.",
        ],
      },
      {
        h2: "Spring Boot e APIs REST",
        paras: [
          "É o que a maioria das vagas pede. Aprenda a criar uma API REST com Spring Boot: controllers, injeção de dependência e a comunicação com o banco via Spring Data JPA.",
        ],
      },
      {
        h2: "Banco de dados e persistência",
        paras: [
          "SQL (SELECT, JOIN, índices) e o mapeamento objeto-relacional com JPA/Hibernate. Saber modelar e consultar dados é metade do trabalho de backend.",
        ],
      },
      {
        h2: "Testes, Git e o resto",
        paras: [
          "Testes com JUnit, controle de versão com Git e uma noção de Docker e CI/CD para se aproximar do dia a dia real. São os itens que aparecem como 'diferencial' nas vagas e viram obrigatórios rápido.",
        ],
      },
    ],
    faq: [
      {
        q: "Preciso aprender Java puro antes de Spring?",
        a: "Sim. Spring assume que você já entende Java e orientação a objetos. Pular direto para o framework costuma resultar em copiar código sem entender por que funciona — e trava na primeira coisa fora do tutorial.",
      },
      {
        q: "Quanto tempo leva para aprender Java para o mercado?",
        a: "Com estudo consistente (5 a 10 horas por semana), de seis meses a um ano para a primeira vaga, incluindo Spring Boot, banco de dados e alguns projetos no portfólio.",
      },
      {
        q: "Java ainda vale a pena em 2026?",
        a: "Sim. Java é uma das linguagens mais usadas em backend corporativo, bancos e sistemas de grande escala, com muitas vagas e salários competitivos.",
      },
    ],
  },
  {
    tipo: "roadmap",
    slug: "react",
    metaTitle: "Roadmap React 2026: o que estudar para virar dev front-end | PathR",
    h1: "Roadmap para desenvolvedor React",
    metaDesc:
      "A ordem para aprender React de verdade: HTML, CSS e JavaScript primeiro, depois componentes, hooks, estado, rotas e o que as vagas de front-end pedem.",
    lead: "React é a biblioteca de interface mais pedida em vagas de front-end. Mas ela se apoia numa base — pular essa base é o erro mais comum de quem trava.",
    secoes: [
      {
        h2: "A base: HTML, CSS e JavaScript",
        paras: [
          "React é JavaScript. Sem o essencial de HTML, CSS e, principalmente, JavaScript moderno (funções, arrays, objetos, promises, async/await), React vira mágica que você copia sem entender. Comece por aqui — é o que mais economiza tempo depois.",
        ],
      },
      {
        h2: "Componentes e JSX",
        paras: [
          "A ideia central do React: montar a tela com componentes reutilizáveis, escritos em JSX. Aprenda a quebrar uma interface em pedaços e a passar dados entre eles com props.",
        ],
      },
      {
        h2: "Estado e hooks",
        paras: [
          "useState e useEffect são o coração do React moderno. Entender quando o componente re-renderiza e como o efeito colateral roda é o que separa quem copia de quem constrói.",
        ],
      },
      {
        h2: "Rotas, dados e formulários",
        paras: [
          "Navegar entre telas, buscar dados de uma API e lidar com formulários aparecem em quase todo projeto real. É aqui que o React deixa de ser exercício e vira um app de verdade.",
        ],
      },
      {
        h2: "TypeScript, testes e o resto",
        paras: [
          "TypeScript é praticamente padrão nas vagas de React hoje. Some testes e Git, e você cobre o que a maioria das vagas de front-end pede.",
        ],
      },
    ],
    faq: [
      {
        q: "Preciso saber JavaScript antes de React?",
        a: "Sim, e bem. React é uma biblioteca JavaScript — boa parte da dificuldade de quem 'não entende React' é, na verdade, JavaScript que faltou. Invista na base antes de acelerar.",
      },
      {
        q: "React ou Angular para começar?",
        a: "React tem mais vagas e uma comunidade maior, o que facilita achar material e ajuda. Angular é forte em ambientes corporativos. Para a primeira vaga de front-end, React costuma abrir mais portas.",
      },
      {
        q: "Preciso aprender TypeScript com React?",
        a: "Cada vez mais sim. A maioria das vagas de React em 2026 pede TypeScript. Dá para começar com JavaScript e adicionar TypeScript quando os componentes já fizerem sentido.",
      },
    ],
  },
  {
    tipo: "roadmap",
    slug: "python",
    metaTitle: "Roadmap Python 2026: o que estudar para virar desenvolvedor Python | PathR",
    h1: "Roadmap para desenvolvedor Python",
    metaDesc:
      "A ordem para aprender Python de verdade: fundamentos, estruturas de dados, um caminho (web, dados ou automação), banco de dados e testes.",
    lead: "Python é a porta de entrada mais suave para a programação — e leva a três mundos: web, dados e automação. Este é o caminho, na ordem certa.",
    secoes: [
      { h2: "Fundamentos da linguagem", paras: ["Sintaxe, tipos, listas, dicionários, funções e laços. Python é limpo o bastante para você focar na lógica, não na cerimônia da linguagem."] },
      { h2: "Estruturas de dados e orientação a objetos", paras: ["Listas, dicionários e conjuntos no sangue, mais o básico de classes e objetos. É o que separa um script de um programa de verdade."] },
      { h2: "Escolha um caminho: web, dados ou automação", paras: ["Python abre três portas. Web: um framework como Django ou FastAPI. Dados: pandas, NumPy e visualização. Automação: scripts que falam com arquivos, planilhas e APIs. Escolha um para se aprofundar em vez de tocar em tudo pela metade."] },
      { h2: "Banco de dados", paras: ["SQL e um ORM (SQLAlchemy ou o do Django). Quase todo projeto real guarda dados em algum lugar, e saber consultá-los é metade do trabalho."] },
      { h2: "Testes, Git e o resto", paras: ["pytest, controle de versão com Git e uma noção de Docker. É o que aproxima o seu código do que roda em produção."] },
    ],
    faq: [
      { q: "Python é bom para quem está começando?", a: "Sim, é uma das melhores primeiras linguagens: sintaxe limpa, comunidade enorme e uso em web, dados e automação. Você foca em aprender a pensar como programador antes de brigar com a linguagem." },
      { q: "Python serve para conseguir emprego?", a: "Serve. Há muitas vagas em back-end (Django, FastAPI), em dados e engenharia de dados, além de automação. Escolher um caminho e ter projetos nele é o que abre a vaga." },
      { q: "Django ou FastAPI?", a: "Django entrega mais pronto (admin, ORM, autenticação) e é ótimo para apps completos. FastAPI é enxuto, rápido e ideal para APIs. Para a primeira vaga de back-end, qualquer um dos dois é uma escolha forte." },
    ],
  },
  {
    tipo: "roadmap",
    slug: "javascript",
    metaTitle: "Roadmap JavaScript 2026: o que estudar do zero ao mercado | PathR",
    h1: "Roadmap para desenvolvedor JavaScript",
    metaDesc:
      "A ordem para aprender JavaScript de verdade: fundamentos, o DOM, código assíncrono, um framework como React e Node.js no back-end.",
    lead: "JavaScript é a única linguagem que roda no navegador — e, com Node.js, também no servidor. Aprender bem abre front-end e back-end.",
    secoes: [
      { h2: "Fundamentos da linguagem", paras: ["Tipos, funções, arrays, objetos e escopo. A base que todo framework assume — e que, quando falta, faz o resto parecer mágica."] },
      { h2: "O DOM e eventos", paras: ["Como o JavaScript mexe na página: selecionar elementos, reagir a cliques, mudar o conteúdo. É o que torna a web interativa."] },
      { h2: "Assíncrono: promises e async/await", paras: ["Buscar dados de uma API sem travar a tela. É o assunto que mais confunde no começo e o que mais aparece no trabalho real."] },
      { h2: "Um framework de front-end (React)", paras: ["Depois da base, um framework como React organiza apps grandes. Aqui o JavaScript vira produto."] },
      { h2: "Node.js no back-end", paras: ["O mesmo JavaScript no servidor: APIs, banco de dados e a stack completa numa linguagem só."] },
    ],
    faq: [
      { q: "Preciso aprender JavaScript antes de React?", a: "Sim. React é JavaScript; a maior parte da dificuldade de quem 'não entende React' é JavaScript que faltou. Base primeiro." },
      { q: "JavaScript dá emprego?", a: "Muito. É a linguagem da web: front-end (React, Vue, Angular) e back-end (Node.js). Uma das que mais têm vagas no mercado." },
      { q: "Vale aprender TypeScript depois?", a: "Vale, e cedo. TypeScript é JavaScript com tipos e virou padrão em vagas. Comece com JS e adote TS quando a base fizer sentido." },
    ],
  },
  {
    tipo: "roadmap",
    slug: "typescript",
    metaTitle: "Roadmap TypeScript 2026: por que e como aprender | PathR",
    h1: "Roadmap para aprender TypeScript",
    metaDesc:
      "Por que TypeScript virou padrão, e o caminho: JavaScript sólido primeiro, tipos, interfaces, generics e uso com React ou Node.",
    lead: "TypeScript é JavaScript com tipos — e virou quase obrigatório em vagas. Mas só faz sentido depois de um JavaScript sólido.",
    secoes: [
      { h2: "Primeiro, JavaScript de verdade", paras: ["TypeScript não substitui aprender JavaScript; ele adiciona uma camada. Sem a base, os tipos viram ruído em vez de ajuda."] },
      { h2: "Tipos, interfaces e uniões", paras: ["Anotar o que uma variável ou função aceita e devolve. É o que pega erro antes de o código rodar, no editor."] },
      { h2: "Generics e tipos utilitários", paras: ["Escrever código que funciona com vários tipos sem perder a checagem. O que separa o TypeScript básico do profissional."] },
      { h2: "TypeScript com React ou Node", paras: ["Onde ele brilha: componentes tipados no front, APIs tipadas no back. É assim que as vagas usam TypeScript de verdade."] },
    ],
    faq: [
      { q: "Preciso saber JavaScript antes de TypeScript?", a: "Sim. TypeScript é uma camada sobre JavaScript. Aprender os dois ao mesmo tempo costuma confundir; base de JS primeiro." },
      { q: "TypeScript é obrigatório para conseguir emprego?", a: "Cada vez mais pedido, principalmente em React e Node. Não é obrigatório em toda vaga, mas domina o mercado moderno de front-end." },
      { q: "TypeScript é difícil?", a: "A sintaxe extra é pequena; a dificuldade real é entender os tipos, e isso vem com prática. Quem já sabe JavaScript pega o básico em poucas semanas." },
    ],
  },
  {
    tipo: "roadmap",
    slug: "node",
    metaTitle: "Roadmap Node.js 2026: o que estudar para back-end com JavaScript | PathR",
    h1: "Roadmap para desenvolvedor Node.js",
    metaDesc:
      "A ordem para aprender back-end com Node.js: JavaScript sólido, um framework (Express ou NestJS), APIs REST, banco de dados, autenticação e testes.",
    lead: "Node.js leva o JavaScript para o servidor — dá para ser full stack com uma linguagem só. Este é o caminho de back-end.",
    secoes: [
      { h2: "JavaScript e assíncrono primeiro", paras: ["Node é JavaScript no servidor, e quase tudo nele é assíncrono. Promises e async/await são pré-requisito, não detalhe."] },
      { h2: "Um framework: Express ou NestJS", paras: ["Express é minimalista e ótimo para entender o básico; NestJS é estruturado e comum em vagas maiores. Comece por um e vá fundo."] },
      { h2: "APIs REST e banco de dados", paras: ["Rotas, controllers e a comunicação com um banco (PostgreSQL ou MongoDB) via um ORM como Prisma. É o coração do back-end."] },
      { h2: "Autenticação e segurança", paras: ["Login, tokens (JWT) e o básico de proteger uma API. O que separa um exercício de um app de verdade."] },
      { h2: "Testes, Git e deploy", paras: ["Testes automatizados, Git e subir a API para um servidor. Fecha a stack de back-end."] },
    ],
    faq: [
      { q: "Node.js ou Python para back-end?", a: "Node.js aproveita o JavaScript que você já usa no front (stack única); Python é forte em dados e tem Django/FastAPI. Ambos empregam bem — escolha pela stack que quer trabalhar." },
      { q: "Express ou NestJS?", a: "Express para aprender os fundamentos e projetos menores; NestJS para arquitetura estruturada e vagas corporativas. Muitos começam no Express e migram." },
      { q: "Preciso saber front-end para trabalhar com Node?", a: "Não é obrigatório, mas ajuda. Node é back-end; saber o básico de front torna você full stack, o que abre mais vagas." },
    ],
  },
  {
    tipo: "roadmap",
    slug: "ciencia-de-dados",
    metaTitle: "Roadmap Ciência de Dados 2026: por onde começar | PathR",
    h1: "Roadmap para ciência de dados",
    metaDesc:
      "O caminho para entrar em dados: Python, estatística e SQL, manipulação com pandas, visualização e uma base de machine learning.",
    lead: "Ciência de dados junta programação, estatística e negócio. O caminho é longo, mas cada etapa se apoia na anterior.",
    secoes: [
      { h2: "Python e manipulação de dados", paras: ["Python é a língua franca de dados. Some pandas e NumPy para carregar, limpar e transformar tabelas — 80% do trabalho é isso."] },
      { h2: "Estatística e SQL", paras: ["Estatística descritiva e o básico de probabilidade para não tirar conclusão errada; SQL para buscar os dados onde eles moram."] },
      { h2: "Visualização e storytelling", paras: ["Um gráfico claro vale mais que um modelo complexo que ninguém entende. Matplotlib/Seaborn e a habilidade de contar a história dos dados."] },
      { h2: "Machine learning (base)", paras: ["Regressão, classificação e como avaliar um modelo de verdade — sem cair na ilusão de 99% de acerto. É o topo do caminho, não o começo."] },
    ],
    faq: [
      { q: "Preciso ser bom em matemática para ciência de dados?", a: "Mais que na maioria das áreas de programação, sim — estatística e um pouco de álgebra ajudam. Mas dá para começar com o básico e aprofundar conforme avança." },
      { q: "Por onde começo em dados?", a: "Por Python e manipulação de dados (pandas) e SQL. Análise de dados vem antes de machine learning; pular direto para ML sem essa base costuma travar." },
      { q: "Analista ou cientista de dados?", a: "Analista foca em consultar, visualizar e explicar dados (SQL, dashboards) — porta de entrada mais rápida. Cientista adiciona estatística e machine learning. Comece por analista se quer entrar mais cedo." },
    ],
  },
  {
    tipo: "roadmap",
    slug: "devops",
    metaTitle: "Roadmap DevOps 2026: o que estudar para começar | PathR",
    h1: "Roadmap para DevOps",
    metaDesc:
      "O caminho para DevOps: Linux e redes, Git e CI/CD, Docker e contêineres, nuvem e infraestrutura como código — na ordem certa.",
    lead: "DevOps é a ponte entre escrever código e colocá-lo no ar de forma confiável. Exige base antes das ferramentas da moda.",
    secoes: [
      { h2: "Linux, redes e linha de comando", paras: ["Quase toda infraestrutura roda em Linux. Terminal, permissões e o básico de rede (DNS, HTTP, portas) são o alicerce."] },
      { h2: "Git e CI/CD", paras: ["Controle de versão e pipelines que testam e entregam o código automaticamente. É o coração da entrega contínua."] },
      { h2: "Docker e contêineres", paras: ["Empacotar a aplicação com tudo que ela precisa, para rodar igual em qualquer lugar. Depois, orquestração com Kubernetes."] },
      { h2: "Nuvem e infraestrutura como código", paras: ["Um provedor (AWS, GCP ou Azure) e ferramentas como Terraform para descrever a infraestrutura em código, versionada e repetível."] },
    ],
    faq: [
      { q: "Preciso saber programar para DevOps?", a: "Sim, o básico. Você automatiza com scripts (shell, Python) e lida com o código dos outros. Não precisa ser dev de aplicação, mas programar é parte do trabalho." },
      { q: "DevOps é uma boa área para começar do zero?", a: "Costuma render mais como segunda etapa: entender desenvolvimento e Linux antes ajuda muito. Mas dá para mirar DevOps desde cedo focando em Linux, redes e automação." },
      { q: "Qual nuvem aprender: AWS, Azure ou GCP?", a: "AWS tem mais vagas e material; Azure é forte em empresas que já usam Microsoft. Aprenda uma a fundo — os conceitos transferem para as outras." },
    ],
  },
  {
    tipo: "guia",
    slug: "melhores-cursos-gratuitos-com-certificado",
    metaTitle: "Melhores cursos gratuitos com certificado de programação (2026) | PathR",
    h1: "Cursos gratuitos com certificado para programação",
    metaDesc:
      "Como encontrar cursos de programação gratuitos que emitem certificado de verdade — e como usá-los no currículo e no LinkedIn sem perder tempo.",
    lead: "Certificado gratuito existe e ajuda no currículo — se for de uma fonte reconhecida e usado do jeito certo. Veja como escolher e o que evita perda de tempo.",
    secoes: [
      { h2: "O que faz um certificado valer", paras: ["O nome que emite pesa mais que o papel. Certificados de grandes plataformas e de empresas de tecnologia são reconhecidos; 'certificado' de fonte desconhecida acrescenta pouco."] },
      { h2: "Onde procurar cursos gratuitos com certificado", paras: ["Grandes plataformas de educação, trilhas oficiais de empresas de nuvem e programas de formação abertos costumam ter cursos gratuitos que emitem certificado. O segredo é filtrar por área e por quem emite."] },
      { h2: "Como usar o certificado no currículo e no LinkedIn", paras: ["Adicione à seção de certificações do LinkedIn e cite no currículo junto com o projeto que você fez com aquele conhecimento. Certificado sem prática rende menos que certificado mais um projeto no portfólio."] },
      { h2: "O que NÃO fazer", paras: ["Colecionar dezenas de certificados de tópicos soltos não impressiona. Vale mais uma trilha coerente, ligada ao seu objetivo, do que um mural de logotipos."] },
    ],
    faq: [
      { q: "Certificado gratuito de programação vale a pena?", a: "Vale, se for de uma fonte reconhecida e acompanhado de prática. Ele mostra dedicação e complementa o portfólio; sozinho, sem projeto, pesa pouco." },
      { q: "Onde encontro cursos gratuitos com certificado?", a: "Em grandes plataformas de educação e nas trilhas oficiais de empresas de tecnologia e nuvem. O PathR reúne cursos com certificado filtrados pelo que você quer aprender." },
      { q: "Certificado substitui faculdade?", a: "Não substitui, mas complementa. Para muitas vagas de tecnologia, portfólio, certificados relevantes e saber resolver problemas contam mais que o diploma." },
    ],
  },
  {
    tipo: "guia",
    slug: "front-end-ou-back-end",
    metaTitle: "Front-end ou back-end? Como escolher por onde começar | PathR",
    h1: "Front-end ou back-end: qual escolher?",
    metaDesc:
      "As diferenças reais entre front-end e back-end, o que cada um exige, qual tem mais vagas e como decidir sem travar na dúvida.",
    lead: "A dúvida trava muita gente no começo. A boa notícia: a base é parecida, e dá para trocar depois. Veja como decidir agora.",
    secoes: [
      { h2: "O que é cada um", paras: ["Front-end é o que a pessoa vê e usa — telas, botões, interações (HTML, CSS, JavaScript, React). Back-end é o que roda no servidor — regras, banco de dados, APIs (Java, Python, Node)."] },
      { h2: "O que combina com você", paras: ["Gosta de ver o resultado visual e cuidar da experiência? Front-end. Prefere lógica, dados e o que acontece por trás? Back-end. Nenhum é 'mais fácil' — são gostos diferentes."] },
      { h2: "Vagas e mercado", paras: ["Os dois têm muitas vagas. Full stack (os dois) abre ainda mais portas, mas exige mais tempo. No começo, escolher um e ir fundo rende mais que se dividir."] },
      { h2: "E se eu errar a escolha?", paras: ["Você não erra de forma irreversível. A base (lógica, uma linguagem, Git) serve para os dois, e migrar depois é comum. Comece por um e ajuste no caminho."] },
    ],
    faq: [
      { q: "Front-end é mais fácil que back-end?", a: "Não. Front-end tem a complexidade de estados, layout e experiência; back-end tem lógica, dados e escala. São dificuldades diferentes, não níveis." },
      { q: "Qual tem mais vagas: front-end ou back-end?", a: "Os dois têm bastante. Back-end costuma ter leve vantagem em volume e salário em alguns mercados, mas a diferença é pequena — escolha pelo que gosta." },
      { q: "Preciso escolher agora?", a: "Para focar os estudos, sim — evita se dividir. Mas a escolha não é definitiva: a base é comum e trocar depois é normal." },
    ],
  },
  {
    tipo: "guia",
    slug: "como-conseguir-o-primeiro-emprego-de-programador",
    metaTitle: "Como conseguir o primeiro emprego de programador (2026) | PathR",
    h1: "Como conseguir o primeiro emprego de programador",
    metaDesc:
      "O que realmente abre a primeira vaga: portfólio com projetos, uma stack coerente, currículo enxuto e como se preparar para a entrevista técnica.",
    lead: "A primeira vaga é a mais difícil — e não se ganha só acumulando cursos. Veja o que os recrutadores realmente olham.",
    secoes: [
      { h2: "Portfólio com projetos de verdade", paras: ["Dois ou três projetos que você construiu do zero valem mais que dez certificados. Eles provam que você resolve problemas, não só assiste a aulas."] },
      { h2: "Uma stack coerente, não dez pela metade", paras: ["Melhor saber bem uma stack completa (uma linguagem, um framework, banco, Git) do que tocar em tudo superficialmente. Foco abre porta."] },
      { h2: "Currículo enxuto e LinkedIn ativo", paras: ["Uma página, com projetos e tecnologias que você realmente usa. LinkedIn atualizado, porque é onde muita vaga aparece."] },
      { h2: "Prepare a entrevista técnica", paras: ["Pratique explicar o seu código e resolver problemas em voz alta. Saber falar sobre o que fez conta tanto quanto o código."] },
    ],
    faq: [
      { q: "Preciso de experiência para o primeiro emprego?", a: "É o paradoxo do começo. Projetos pessoais, freelances e contribuições contam como experiência prática — é assim que a maioria fura a barreira." },
      { q: "Quantos projetos preciso no portfólio?", a: "Dois ou três bem feitos, que você saiba explicar por inteiro, valem mais que muitos projetos copiados. Domínio acima de quantidade." },
      { q: "Vale a pena fazer freelance para começar?", a: "Vale. Freela e projetos reais dão experiência, portfólio e histórias para a entrevista — tudo o que falta a quem só estudou." },
    ],
  },
];

// ---------------------------------------------------------------------------

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const urlDe = (t) => `${BASE}/${PASTA[t.tipo]}/${t.slug}/`;

const CSS = `
:root{color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:#000;color:#e9e9ed;font:16px/1.65 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:#b5abfc}
.wrap{max-width:720px;margin:0 auto;padding:0 20px 72px}
.top{display:flex;align-items:center;gap:10px;padding:20px 0}
.mark{width:34px;height:34px;flex:none;border-radius:9px;box-shadow:inset 0 0 0 1px rgba(233,233,237,.14)}
.top b{font-size:15px}.top small{font-size:12px;color:#8a8d99;display:block}
nav.bc{font-size:13px;color:#8a8d99;margin:8px 0 0}
nav.bc a{color:#8a8d99}
h1{font-size:clamp(26px,5.5vw,40px);line-height:1.15;margin:18px 0 10px;letter-spacing:-.01em}
.lead{font-size:18px;color:#c9c9d2;margin:0 0 8px}
h2{font-size:21px;margin:34px 0 6px;letter-spacing:-.01em}
p{margin:10px 0}
.cta{display:inline-block;margin:26px 0 8px;padding:14px 22px;border-radius:11px;background:#7c6cf0;color:#fff;font-weight:600;text-decoration:none}
.cta:hover{background:#8b7cf5}
.faq{margin-top:14px}
.faq h3{font-size:17px;margin:22px 0 2px;color:#fff}
.rel{margin-top:44px;padding-top:22px;border-top:1px solid rgba(233,233,237,.12)}
.rel a{display:block;padding:8px 0;color:#e9e9ed}
.hub a{display:block;padding:15px 0;border-bottom:1px solid rgba(233,233,237,.1);color:#e9e9ed;text-decoration:none}
.hub a:hover b{color:#b5abfc}
.hub b{display:block;font-size:17px}
.hub span{display:block;font-size:13.5px;color:#8a8d99;margin-top:3px;line-height:1.45}
footer{margin-top:40px;font-size:13px;color:#8a8d99}
footer a{color:#8a8d99}
`.trim();

function jsonLd(t) {
  const url = urlDe(t);
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        headline: t.h1,
        description: t.metaDesc,
        inLanguage: "pt-BR",
        mainEntityOfPage: url,
        author: { "@type": "Organization", name: "PathR", url: APP },
        publisher: { "@type": "Organization", name: "PathR", url: APP, logo: OG_IMG },
        datePublished: HOJE,
        dateModified: HOJE,
      },
      {
        "@type": "FAQPage",
        mainEntity: t.faq.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Início", item: APP },
          { "@type": "ListItem", position: 2, name: ROTULO[t.tipo], item: url },
          { "@type": "ListItem", position: 3, name: t.h1, item: url },
        ],
      },
    ],
  };
}

function pagina(t) {
  const url = urlDe(t);
  const secoes = t.secoes
    .map((s) => `      <h2>${esc(s.h2)}</h2>\n${s.paras.map((p) => `      <p>${esc(p)}</p>`).join("\n")}`)
    .join("\n");
  const faq = t.faq.map((f) => `        <h3>${esc(f.q)}</h3>\n        <p>${esc(f.a)}</p>`).join("\n");
  const relacionados = TOPICOS.filter((o) => o.slug !== t.slug)
    .map((o) => `        <a href="${urlDe(o)}">${esc(o.h1)}</a>`)
    .join("\n");
  return `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>${esc(t.metaTitle)}</title>
  <meta name="description" content="${esc(t.metaDesc)}" />
  <link rel="canonical" href="${url}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="icon" type="image/svg+xml" href="/logo.svg" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="PathR" />
  <meta property="og:title" content="${esc(t.metaTitle)}" />
  <meta property="og:description" content="${esc(t.metaDesc)}" />
  <meta property="og:url" content="${url}" />
  <meta property="og:image" content="${OG_IMG}" />
  <meta property="og:locale" content="pt_BR" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="${esc(t.metaTitle)}" />
  <meta name="twitter:description" content="${esc(t.metaDesc)}" />
  <meta name="twitter:image" content="${OG_IMG}" />
  <script type="application/ld+json">
${JSON.stringify(jsonLd(t), null, 2)}
  </script>
  <style>${CSS}</style>
</head>
<body>
  <div class="wrap">
    <a class="top" href="/" style="text-decoration:none;color:inherit">
      <img class="mark" src="/logo.svg" alt="PathR" width="34" height="34" />
      <span><b>PathR</b><small>plano de estudos em tecnologia</small></span>
    </a>
    <nav class="bc"><a href="/">Início</a> › ${ROTULO[t.tipo]} › ${esc(t.h1)}</nav>

    <main>
      <h1>${esc(t.h1)}</h1>
      <p class="lead">${esc(t.lead)}</p>

      <a class="cta" href="${APP}">Criar meu plano de estudos grátis</a>

${secoes}

      <h2>Perguntas frequentes</h2>
      <div class="faq">
${faq}
      </div>

      <a class="cta" href="${APP}">Montar meu roadmap no PathR — grátis</a>

      <p style="color:#8a8d99;font-size:14px;margin-top:24px">O <a href="${APP}">PathR</a> gera um roadmap de estudos a partir do seu currículo e objetivo, com biblioteca curada, quizzes, inglês corporativo, cursos com certificado e vagas que combinam com você. É gratuito.</p>

      <div class="rel">
        <strong>Continue lendo</strong>
${relacionados}
      </div>
    </main>

    <footer>
      <a href="/">PathR</a> · <a href="/termos">Termos</a> · <a href="/privacidade">Privacidade</a> · <a href="/seguranca">Segurança</a>
    </footer>
  </div>
</body>
</html>
`;
}

/** As páginas-hub: uma por tipo (/guias/ e /roadmap/), que LISTAM e linkam as
 * páginas daquele tipo. Não é um depósito de perguntas — é um índice, que ajuda
 * o Google a rastrear tudo e distribui autoridade entre as páginas focadas. */
const HUB = {
  guia: {
    metaTitle: "Guias para estudar programação e tecnologia | PathR",
    h1: "Guias para estudar programação",
    metaDesc:
      "Guias diretos para quem estuda tecnologia: por onde começar, quanto tempo leva, front-end ou back-end, cursos com certificado e como conseguir o primeiro emprego.",
  },
  roadmap: {
    metaTitle: "Roadmaps de estudo por tecnologia | PathR",
    h1: "Roadmaps por tecnologia",
    metaDesc:
      "O que estudar, na ordem certa, para cada tecnologia: Java, Python, JavaScript, TypeScript, React, Node.js, DevOps e ciência de dados.",
  },
};

const urlHub = (tipo) => `${BASE}/${PASTA[tipo]}/`;

function hub(tipo) {
  const url = urlHub(tipo);
  const meta = HUB[tipo];
  const itens = TOPICOS.filter((t) => t.tipo === tipo);
  const lista = itens
    .map((t) => `        <a href="${urlDe(t)}"><b>${esc(t.h1)}</b><span>${esc(t.metaDesc)}</span></a>`)
    .join("\n");
  const ld = {
    "@context": "https://schema.org",
    "@graph": [
      { "@type": "CollectionPage", name: meta.h1, description: meta.metaDesc, url, inLanguage: "pt-BR" },
      {
        "@type": "ItemList",
        itemListElement: itens.map((t, i) => ({ "@type": "ListItem", position: i + 1, url: urlDe(t), name: t.h1 })),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Início", item: APP },
          { "@type": "ListItem", position: 2, name: ROTULO[tipo], item: url },
        ],
      },
    ],
  };
  return `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>${esc(meta.metaTitle)}</title>
  <meta name="description" content="${esc(meta.metaDesc)}" />
  <link rel="canonical" href="${url}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="icon" type="image/svg+xml" href="/logo.svg" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="PathR" />
  <meta property="og:title" content="${esc(meta.metaTitle)}" />
  <meta property="og:description" content="${esc(meta.metaDesc)}" />
  <meta property="og:url" content="${url}" />
  <meta property="og:image" content="${OG_IMG}" />
  <meta property="og:locale" content="pt_BR" />
  <script type="application/ld+json">
${JSON.stringify(ld, null, 2)}
  </script>
  <style>${CSS}</style>
</head>
<body>
  <div class="wrap">
    <a class="top" href="/" style="text-decoration:none;color:inherit">
      <img class="mark" src="/logo.svg" alt="PathR" width="34" height="34" />
      <span><b>PathR</b><small>plano de estudos em tecnologia</small></span>
    </a>
    <nav class="bc"><a href="/">Início</a> › ${ROTULO[tipo]}</nav>
    <main>
      <h1>${esc(meta.h1)}</h1>
      <p class="lead">${esc(meta.metaDesc)}</p>
      <a class="cta" href="${APP}">Criar meu plano de estudos grátis</a>
      <div class="hub">
${lista}
      </div>
    </main>
    <footer>
      <a href="/">PathR</a> · <a href="/termos">Termos</a> · <a href="/privacidade">Privacidade</a> · <a href="/seguranca">Segurança</a>
    </footer>
  </div>
</body>
</html>
`;
}

function sitemap() {
  const estaticas = [
    { loc: `${BASE}/`, freq: "weekly", pri: "1.0" },
    { loc: urlHub("guia"), freq: "weekly", pri: "0.7" },
    { loc: urlHub("roadmap"), freq: "weekly", pri: "0.7" },
    ...TOPICOS.map((t) => ({ loc: urlDe(t), freq: "monthly", pri: "0.8" })),
    { loc: `${BASE}/termos`, freq: "monthly", pri: "0.3" },
    { loc: `${BASE}/privacidade`, freq: "monthly", pri: "0.3" },
    { loc: `${BASE}/seguranca`, freq: "monthly", pri: "0.3" },
  ];
  const urls = estaticas
    .map(
      (u) =>
        `  <url>\n    <loc>${u.loc}</loc>\n    <lastmod>${HOJE}</lastmod>\n    <changefreq>${u.freq}</changefreq>\n    <priority>${u.pri}</priority>\n  </url>`,
    )
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

for (const t of TOPICOS) {
  const destino = join(PUBLIC, PASTA[t.tipo], t.slug, "index.html");
  mkdirSync(dirname(destino), { recursive: true });
  writeFileSync(destino, pagina(t), "utf8");
  console.log("gerado:", urlDe(t));
}
for (const tipo of Object.keys(HUB)) {
  const destino = join(PUBLIC, PASTA[tipo], "index.html");
  mkdirSync(dirname(destino), { recursive: true });
  writeFileSync(destino, hub(tipo), "utf8");
  console.log("hub:   ", urlHub(tipo));
}
writeFileSync(join(PUBLIC, "sitemap.xml"), sitemap(), "utf8");
console.log(`sitemap: ${TOPICOS.length + 6} URLs`);
