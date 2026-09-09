/**
 * Registro do service worker.
 *
 * É ele que faz o app ABRIR sem rede: o HTML, o JavaScript e o CSS ficam
 * gravados no aparelho e são servidos do disco. Os dados são outra história e
 * moram em `offline/` — service worker guarda arquivos, não o progresso de
 * ninguém.
 *
 * **A versão nova nunca entra sozinha.** Quando um deploy acontece, o worker
 * novo instala e FICA ESPERANDO; a troca só ocorre quando a pessoa toca em
 * "atualizar". Trocar por conta própria significaria puxar os pedaços do
 * JavaScript debaixo de uma sessão em andamento — o app quebraria no meio de
 * um quiz, com um erro que ninguém consegue explicar.
 *
 * Em desenvolvimento não há registro nenhum: um worker guardando os arquivos
 * do Vite transforma cada alteração num mistério de cache.
 */

const CAMINHO = "/sw.js";

type Ouvinte = () => void;

const ouvintes = new Set<Ouvinte>();
let esperando: ServiceWorker | null = null;
let recarregando = false;

/** Avisa quando existe uma versão nova pronta para entrar. */
export function onUpdateReady(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte);
  if (esperando) ouvinte();
  return () => {
    ouvintes.delete(ouvinte);
  };
}

export const updateReady = (): boolean => esperando !== null;

/** Manda o worker novo assumir. A página recarrega quando ele assumir. */
export function applyUpdate(): void {
  esperando?.postMessage({ type: "SKIP_WAITING" });
}

function anuncia(worker: ServiceWorker): void {
  esperando = worker;
  ouvintes.forEach((ouvinte) => ouvinte());
}

/**
 * Um worker instalado E com controlador anterior é uma ATUALIZAÇÃO. Sem
 * controlador anterior é a primeira instalação — aí não há nada a anunciar,
 * a pessoa acabou de abrir a versão que está vendo.
 */
function observa(registro: ServiceWorkerRegistration): void {
  if (registro.waiting && navigator.serviceWorker.controller) anuncia(registro.waiting);

  registro.addEventListener("updatefound", () => {
    const novo = registro.installing;
    if (!novo) return;
    novo.addEventListener("statechange", () => {
      if (novo.state === "installed" && navigator.serviceWorker.controller) anuncia(novo);
    });
  });
}

export function registerServiceWorker(): void {
  if (!import.meta.env.PROD) return;
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    // O guarda existe porque este evento também dispara na primeira
    // instalação em algumas versões do Safari; sem ele, o app recarregaria
    // sozinho logo depois de abrir.
    if (recarregando || !esperando) return;
    recarregando = true;
    window.location.reload();
  });

  window.addEventListener("load", () => {
    void navigator.serviceWorker
      // `updateViaCache: "none"` obriga o navegador a buscar o sw.js na rede
      // em toda checagem, ignorando o cache HTTP.
      //
      // Não é redundância com o `Cache-Control: no-cache` do `public/_headers`:
      // o Cloudflare Pages NÃO honra aquela regra — ele serve o sw.js com
      // `max-age=14400` de qualquer jeito (verificado em produção). E o sw.js
      // é o arquivo que sabe quais assets existem nesta versão: servir uma
      // cópia velha dele é o deploy não chegar a quem instalou o app na tela
      // de início, que é justamente quem não tem como recarregar para forçar.
      //
      // A regra no `_headers` fica: se o Pages passar a honrá-la, as duas
      // dizem a mesma coisa. Esta aqui é a que não depende do host.
      .register(CAMINHO, { updateViaCache: "none" })
      .then((registro) => {
        observa(registro);
        // Uma checagem ao voltar para o app: quem deixa o PathR aberto na
        // tela de início por semanas nunca dispararia a busca por versão nova
        // de outro jeito.
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState === "visible") void registro.update();
        });
      })
      .catch(() => {
        // Sem service worker o app continua funcionando — só não abre offline.
        // Não vale mostrar erro por isso.
      });
  });
}
