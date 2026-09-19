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
.mark{width:34px;height:34px;flex:none;border-radius:9px;background:#0c0c10;display:grid;place-items:center;box-shadow:inset 0 0 0 1px rgba(233,233,237,.14);color:#b5abfc;font-weight:800}
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
      <span class="mark">{P}</span>
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

function sitemap() {
  const estaticas = [
    { loc: `${BASE}/`, freq: "weekly", pri: "1.0" },
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
writeFileSync(join(PUBLIC, "sitemap.xml"), sitemap(), "utf8");
console.log(`sitemap: ${TOPICOS.length + 4} URLs`);
