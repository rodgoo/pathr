/**
 * O canal que avisa esta tela de que algo mudou em outro aparelho.
 *
 * Server-Sent Events em `GET /events`. O servidor não manda conteúdo — manda
 * um empurrão para reconsultar — e quem sabe pedir os dados continua sendo o
 * `useQuery` de sempre. Duas formas de o cliente aprender a verdade seriam
 * duas formas de divergir.
 *
 * ## Só com o app à vista
 *
 * A conexão abre quando a aba fica visível e fecha quando ela some. Não é
 * economia de enfeite: uma conexão SSE aberta é uma requisição em voo, e a
 * hospedagem da API suspende a máquina quando não há nenhuma. Um celular
 * esquecido aberto no bolso seguraria a máquina no ar sem ninguém olhando —
 * e o valor de um aviso em tempo real para uma tela que ninguém está vendo é
 * zero. Ao voltar, a reconferência de foco já cobre o que se perdeu.
 *
 * ## O eco
 *
 * Toda escrita manda o cabeçalho `X-Pathr-Client` com o id desta aba, e o
 * aviso volta com ele em `origem`. Quem escreveu ignora o próprio aviso: a
 * tela dele já está atualizada, e reconsultar por causa do próprio POST seria
 * uma requisição a mais por escrita, em todo aparelho.
 */

import { dataRevision } from "./status";

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "https://localhost:8031";

/**
 * O id desta aba. Vive na memória e morre com ela — não é identidade de
 * usuário nem de aparelho, é só "quem escreveu isto".
 */
export const ID_DESTA_ABA = Math.random().toString(36).slice(2, 10);

/**
 * Espera crescente entre tentativas.
 *
 * O `EventSource` reconecta sozinho, mas só enquanto o servidor responde. Um
 * 401 ou uma API fora do ar fazem o navegador tentar de novo em laço apertado
 * — e é justamente quando insistir menos é melhor. Por isso o controle é
 * nosso: fechamos e reagendamos.
 */
const ESPERA_INICIAL_MS = 2_000;
const ESPERA_MAXIMA_MS = 60_000;

let canal: EventSource | null = null;
let reagendado: number | null = null;
let espera = ESPERA_INICIAL_MS;
let ligado = false;

function fecha(): void {
  canal?.close();
  canal = null;
  if (reagendado !== null) {
    window.clearTimeout(reagendado);
    reagendado = null;
  }
}

function abre(): void {
  if (!ligado || canal || typeof EventSource === "undefined") return;

  // `withCredentials` é o que manda o cookie de sessão para a outra origem.
  // Sem ele o servidor responde 401 e o canal nunca sobe.
  const fonte = new EventSource(`${BASE_URL}/events`, { withCredentials: true });
  canal = fonte;

  fonte.onopen = () => {
    espera = ESPERA_INICIAL_MS;
  };

  fonte.onmessage = (evento) => {
    let corpo: { rota?: string; origem?: string; aberto?: boolean };
    try {
      corpo = JSON.parse(evento.data);
    } catch {
      return;
    }
    // O primeiro evento só confirma que o canal está de pé.
    if (corpo.aberto) return;
    if (corpo.origem && corpo.origem === ID_DESTA_ABA) return;
    dataRevision.bump();
  };

  fonte.onerror = () => {
    // O servidor também fecha por conta própria a cada 15 minutos, para a
    // máquina poder suspender nos intervalos. Aqui isso é indistinguível de
    // uma queda, e a resposta é a mesma: reabrir.
    fecha();
    if (!ligado) return;
    reagendado = window.setTimeout(abre, espera);
    espera = Math.min(espera * 2, ESPERA_MAXIMA_MS);
  };
}

/** Liga o canal enquanto a aba estiver visível. */
export function conectarEventos(): void {
  ligado = true;
  if (document.visibilityState === "visible") abre();
}

/** Desliga e para de reconectar — no logout, ou ao esconder a aba. */
export function desconectarEventos(): void {
  ligado = false;
  espera = ESPERA_INICIAL_MS;
  fecha();
}

/** Segue a visibilidade da aba: abre ao aparecer, fecha ao sumir. */
export function seguirVisibilidade(): () => void {
  const aoMudar = () => {
    if (!ligado) return;
    if (document.visibilityState === "visible") abre();
    else fecha();
  };
  document.addEventListener("visibilitychange", aoMudar);
  return () => document.removeEventListener("visibilitychange", aoMudar);
}
