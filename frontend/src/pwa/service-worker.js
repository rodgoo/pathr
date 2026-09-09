/**
 * O service worker do PathR.
 *
 * Não é bundlado: `vite.config.ts` lê este arquivo no fim do build, troca os
 * dois marcadores por valores reais e grava `dist/sw.js`. Por isso é
 * JavaScript puro, sem imports e sem TypeScript — o que estiver aqui é
 * exatamente o que roda no navegador.
 *
 * O que ele guarda: o CASCO do app — HTML, JavaScript, CSS, ícones. É o que
 * faz o PathR abrir no metrô. O que ele NÃO guarda: nada vindo da API. Os
 * dados têm dono, precisam sair no logout e precisam da fila de escrita, e
 * nada disso o service worker sabe — quem cuida deles é `src/offline/`.
 *
 * Uma versão nova instala e ESPERA. Assumir de imediato trocaria os pedaços
 * de JavaScript debaixo de uma sessão aberta, e o app quebraria no meio do
 * que a pessoa estivesse fazendo. Quem manda assumir é a interface, quando a
 * pessoa toca em "atualizar".
 */

/* global self, caches, fetch, Request, URL */

const VERSAO = "__VERSION__";
const PRECACHE = __PRECACHE__;
const CACHE = `pathr-${VERSAO}`;
const CASCO = "/index.html";

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((cache) =>
      // `cache: "reload"` ignora o cache HTTP do navegador: sem isso, um
      // index.html velho ainda dentro da validade seria gravado como se
      // fosse a versão nova, e o deploy não chegaria a ninguém.
      cache.addAll(PRECACHE.map((url) => new Request(url, { cache: "reload" }))),
    ),
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nomes) =>
        Promise.all(
          nomes
            .filter((nome) => nome.startsWith("pathr-") && nome !== CACHE)
            .map((nome) => caches.delete(nome)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (evento) => {
  if (evento.data && evento.data.type === "SKIP_WAITING") self.skipWaiting();
});

/**
 * `ignoreVary` em toda consulta ao cache, e não é detalhe.
 *
 * O servidor manda `Vary: Origin` nos arquivos. O pedido que o precache faz
 * não tem cabeçalho `Origin`; o que o `<script crossorigin>` da página faz,
 * tem. Sem ignorar o Vary, o Cache API trata os dois como coisas diferentes,
 * a busca não acha nada, e o app abre offline como uma página EM BRANCO — o
 * casco vem do cache, o JavaScript não. Foi exatamente o que aconteceu.
 */
const OPCOES_DE_BUSCA = { ignoreVary: true };

/**
 * Uma navegação — abrir o app, recarregar, chegar por um link de e-mail.
 *
 * Rede primeiro para que um deploy novo apareça na primeira abertura com
 * rede. Sem rede, devolve o casco guardado: o roteamento do PathR acontece no
 * cliente, então o mesmo index.html serve qualquer endereço.
 */
async function navegacao(pedido) {
  try {
    return await fetch(pedido);
  } catch (erro) {
    const guardado = await caches.match(CASCO, OPCOES_DE_BUSCA);
    if (guardado) return guardado;
    throw erro;
  }
}

/**
 * Um arquivo do app.
 *
 * Cache primeiro porque os nomes carregam hash: `index-a1b2c3.js` nunca muda
 * de conteúdo, então ir à rede confirmar seria gastar tempo para receber a
 * mesma coisa. O que não tem hash (ícones, manifest) entra no cache na
 * primeira vez que for pedido e sai junto com a versão, no activate.
 */
async function arquivo(pedido) {
  const guardado = await caches.match(pedido, OPCOES_DE_BUSCA);
  if (guardado) return guardado;

  const resposta = await fetch(pedido);
  if (resposta.ok && resposta.status === 200 && resposta.type === "basic") {
    const copia = resposta.clone();
    caches.open(CACHE).then((cache) => cache.put(pedido, copia));
  }
  return resposta;
}

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  if (pedido.method !== "GET") return;

  // A API mora noutro host e é tratada pelo app, não aqui: as respostas dela
  // têm dono, precisam sumir no logout e alimentam a fila de escrita. Um
  // cache cego neste ponto mostraria o roadmap de uma pessoa para outra.
  const url = new URL(pedido.url);
  if (url.origin !== self.location.origin) return;

  evento.respondWith(pedido.mode === "navigate" ? navegacao(pedido) : arquivo(pedido));
});
