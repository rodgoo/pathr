/**
 * A cara de cada tecnologia: logo e cor, pelo NOME que aparece na tela.
 *
 * `linguagens.tsx` resolve pelo id do laboratório ("cpp", "csharp"); aqui a
 * entrada é o nome da tag como a pessoa vê — "Spring Boot", "C#", "Node.js" —
 * porque é isso que chega do perfil e dos cartões de pessoa.
 *
 * Cor da marca quando a tecnologia é conhecida, para a pessoa reconhecer de
 * relance (Java laranja, React ciano). Para o resto, uma cor da paleta do app
 * escolhida pelo nome: a mesma tag tem a mesma cor em todas as telas, sem
 * ninguém precisar cadastrar nada.
 *
 * Logos do Devicon 2.17.0 (MIT) em `assets/linguagens` e `assets/tecnologias`.
 * Ficaram de fora os que são quase pretos (Kafka, Express, Next.js, Django,
 * Flask): no fundo escuro do app eles viram um borrão, e a bolinha colorida
 * comunica melhor do que um logo que não se lê.
 */

import bash from "@/assets/linguagens/bash.svg";
import c from "@/assets/linguagens/c.svg";
import cplusplus from "@/assets/linguagens/cplusplus.svg";
import csharp from "@/assets/linguagens/csharp.svg";
import dart from "@/assets/linguagens/dart.svg";
import go from "@/assets/linguagens/go.svg";
import java from "@/assets/linguagens/java.svg";
import javascript from "@/assets/linguagens/javascript.svg";
import kotlin from "@/assets/linguagens/kotlin.svg";
import php from "@/assets/linguagens/php.svg";
import python from "@/assets/linguagens/python.svg";
import ruby from "@/assets/linguagens/ruby.svg";
import rust from "@/assets/linguagens/rust.svg";
import swift from "@/assets/linguagens/swift.svg";
import typescript from "@/assets/linguagens/typescript.svg";
import amazonwebservices from "@/assets/tecnologias/amazonwebservices.svg";
import angular from "@/assets/tecnologias/angular.svg";
import azure from "@/assets/tecnologias/azure.svg";
import css3 from "@/assets/tecnologias/css3.svg";
import docker from "@/assets/tecnologias/docker.svg";
import dotnetcore from "@/assets/tecnologias/dotnetcore.svg";
import elasticsearch from "@/assets/tecnologias/elasticsearch.svg";
import fastapi from "@/assets/tecnologias/fastapi.svg";
import figma from "@/assets/tecnologias/figma.svg";
import firebase from "@/assets/tecnologias/firebase.svg";
import flutter from "@/assets/tecnologias/flutter.svg";
import git from "@/assets/tecnologias/git.svg";
import githubactions from "@/assets/tecnologias/githubactions.svg";
import googlecloud from "@/assets/tecnologias/googlecloud.svg";
import graphql from "@/assets/tecnologias/graphql.svg";
import hibernate from "@/assets/tecnologias/hibernate.svg";
import html5 from "@/assets/tecnologias/html5.svg";
import jenkins from "@/assets/tecnologias/jenkins.svg";
import jest from "@/assets/tecnologias/jest.svg";
import junit from "@/assets/tecnologias/junit.svg";
import kubernetes from "@/assets/tecnologias/kubernetes.svg";
import laravel from "@/assets/tecnologias/laravel.svg";
import microsoftsqlserver from "@/assets/tecnologias/microsoftsqlserver.svg";
import mongodb from "@/assets/tecnologias/mongodb.svg";
import mysql from "@/assets/tecnologias/mysql.svg";
import nestjs from "@/assets/tecnologias/nestjs.svg";
import nginx from "@/assets/tecnologias/nginx.svg";
import nodejs from "@/assets/tecnologias/nodejs.svg";
import postgresql from "@/assets/tecnologias/postgresql.svg";
import pytest from "@/assets/tecnologias/pytest.svg";
import rabbitmq from "@/assets/tecnologias/rabbitmq.svg";
import react from "@/assets/tecnologias/react.svg";
import redis from "@/assets/tecnologias/redis.svg";
import redux from "@/assets/tecnologias/redux.svg";
import sass from "@/assets/tecnologias/sass.svg";
import selenium from "@/assets/tecnologias/selenium.svg";
import spring from "@/assets/tecnologias/spring.svg";
import sqlite from "@/assets/tecnologias/sqlite.svg";
import supabase from "@/assets/tecnologias/supabase.svg";
import svelte from "@/assets/tecnologias/svelte.svg";
import tailwindcss from "@/assets/tecnologias/tailwindcss.svg";
import terraform from "@/assets/tecnologias/terraform.svg";
import vitejs from "@/assets/tecnologias/vitejs.svg";
import vuejs from "@/assets/tecnologias/vuejs.svg";
import { ACC, C } from "@/lib/tokens";

export interface Identidade {
  cor: string;
  logo: string | null;
}

/**
 * Chave de comparação: minúsculas, sem acento, espaço, ponto ou hífen.
 * "Node.js", "NodeJS" e "node js" viram todos "nodejs". `#` e `+` viram
 * palavra, senão "C#", "C++" e "C" seriam a mesma coisa.
 */
export function chave(nome: string): string {
  return nome
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\+/g, "plus")
    .replace(/#/g, "sharp")
    .replace(/[^a-z0-9]/g, "");
}

// [logo, cor da marca], por chave. Várias grafias apontam para a mesma entrada.
const CONHECIDAS: Record<string, [string | null, string]> = {
  java: [java, "#f0932b"],
  javascript: [javascript, "#e8c547"],
  js: [javascript, "#e8c547"],
  typescript: [typescript, "#4b8fd6"],
  ts: [typescript, "#4b8fd6"],
  python: [python, "#5b9bd5"],
  go: [go, "#3fb5d6"],
  golang: [go, "#3fb5d6"],
  rust: [rust, "#de7b52"],
  c: [c, "#7d93c9"],
  cplusplus: [cplusplus, "#6b8fd1"],
  csharp: [csharp, "#a77bd8"],
  php: [php, "#8892cf"],
  ruby: [ruby, "#d9534f"],
  kotlin: [kotlin, "#b37dfa"],
  swift: [swift, "#f26b3a"],
  dart: [dart, "#3fb5d6"],
  bash: [bash, "#6cc070"],
  shell: [bash, "#6cc070"],
  shellscript: [bash, "#6cc070"],
  sql: [null, C.azul],

  react: [react, "#61dafb"],
  reactjs: [react, "#61dafb"],
  reactnative: [react, "#61dafb"],
  nodejs: [nodejs, "#6cc070"],
  node: [nodejs, "#6cc070"],
  angular: [angular, "#e2445c"],
  vue: [vuejs, "#41b883"],
  vuejs: [vuejs, "#41b883"],
  svelte: [svelte, "#ff6a33"],
  html: [html5, "#f16529"],
  html5: [html5, "#f16529"],
  css: [css3, "#4b8fd6"],
  css3: [css3, "#4b8fd6"],
  sass: [sass, "#cb6699"],
  tailwind: [tailwindcss, "#38bdf8"],
  tailwindcss: [tailwindcss, "#38bdf8"],
  redux: [redux, "#9b7bd8"],
  vite: [vitejs, "#a78bfa"],
  vitejs: [vitejs, "#a78bfa"],
  nestjs: [nestjs, "#e0405f"],
  express: [null, "#9aa0a6"],
  expressjs: [null, "#9aa0a6"],
  nextjs: [null, "#c9c9d1"],
  flutter: [flutter, "#3fb6d3"],

  spring: [spring, "#77bc1f"],
  springboot: [spring, "#77bc1f"],
  springsecurity: [spring, "#77bc1f"],
  springframework: [spring, "#77bc1f"],
  hibernate: [hibernate, "#bcae79"],
  jpa: [hibernate, "#bcae79"],
  junit: [junit, "#25a162"],
  dotnet: [dotnetcore, "#8f6ed5"],
  netcore: [dotnetcore, "#8f6ed5"],
  aspnet: [dotnetcore, "#8f6ed5"],
  aspnetcore: [dotnetcore, "#8f6ed5"],
  laravel: [laravel, "#f0513f"],
  fastapi: [fastapi, "#1fb8a5"],
  django: [null, "#44b78b"],
  flask: [null, "#c9c9d1"],
  pytest: [pytest, "#f0a030"],
  jest: [jest, "#c2566f"],
  selenium: [selenium, "#43b02a"],

  postgresql: [postgresql, "#6d9fd0"],
  postgres: [postgresql, "#6d9fd0"],
  mysql: [mysql, "#4a9fc9"],
  sqlserver: [microsoftsqlserver, "#d34a4a"],
  microsoftsqlserver: [microsoftsqlserver, "#d34a4a"],
  sqlite: [sqlite, "#4aa3df"],
  mongodb: [mongodb, "#4faa41"],
  mongo: [mongodb, "#4faa41"],
  redis: [redis, "#e0503f"],
  elasticsearch: [elasticsearch, "#fec514"],
  supabase: [supabase, "#3ecf8e"],
  firebase: [firebase, "#ffca28"],
  graphql: [graphql, "#e535ab"],
  rabbitmq: [rabbitmq, "#ff7a1a"],
  kafka: [null, "#b0b0bb"],
  apachekafka: [null, "#b0b0bb"],

  docker: [docker, "#2aa8e0"],
  kubernetes: [kubernetes, "#5b8def"],
  k8s: [kubernetes, "#5b8def"],
  aws: [amazonwebservices, "#ff9900"],
  amazonwebservices: [amazonwebservices, "#ff9900"],
  azure: [azure, "#2f8fe0"],
  gcp: [googlecloud, "#f2b01e"],
  googlecloud: [googlecloud, "#f2b01e"],
  terraform: [terraform, "#7b6cf0"],
  git: [git, "#f05033"],
  github: [null, "#c9c9d1"],
  githubactions: [githubactions, "#2f8fff"],
  jenkins: [jenkins, "#e2574c"],
  nginx: [nginx, "#2fa84f"],
  figma: [figma, "#f24e1e"],
};

// A paleta do app, na ordem em que as cores ficam mais distantes entre si.
const PALETA = [ACC, C.verde, C.azul, C.ambar, C.rosa, C.teal] as const;

export function identidade(nome: string): Identidade {
  const k = chave(nome);
  const conhecida = CONHECIDAS[k];
  if (conhecida) return { logo: conhecida[0], cor: conhecida[1] };
  // Hash simples e estável: não precisa ser bom, precisa só dar a mesma cor
  // para o mesmo nome em qualquer tela.
  let soma = 0;
  for (let i = 0; i < k.length; i += 1) soma = (soma * 31 + k.charCodeAt(i)) >>> 0;
  return { logo: null, cor: PALETA[soma % PALETA.length] };
}

/** O logo da tecnologia, ou uma bolinha na cor dela quando não há logo. */
export function MarcaDaTecnologia({ nome, lado = 14 }: { nome: string; lado?: number }) {
  const { logo, cor } = identidade(nome);
  if (logo) {
    // alt="" pelo mesmo motivo de linguagens.tsx: o nome já está escrito ao lado.
    return <img src={logo} alt="" width={lado} height={lado} style={{ flex: "none", display: "block" }} />;
  }
  const bolinha = Math.round(lado * 0.55);
  return (
    <span
      aria-hidden
      style={{
        width: bolinha,
        height: bolinha,
        borderRadius: "50%",
        background: cor,
        flex: "none",
        margin: (lado - bolinha) / 2,
      }}
    />
  );
}
