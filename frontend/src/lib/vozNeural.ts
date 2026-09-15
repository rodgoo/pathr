/**
 * A voz boa: áudio neural gerado no servidor, por `/languages/tts`.
 *
 * ## Por que existe, já havendo `fala.ts`
 *
 * `fala.ts` prepara o que vai para o `speechSynthesis` do navegador — e a voz
 * do navegador não é escolha do app. Ele só oferece o que o sistema tem
 * instalado, e num Windows em português sobra uma voz de inglês da geração
 * SAPI antiga, que lê palavra por palavra: não pausa na vírgula, não sobe no
 * ponto de interrogação, não separa uma fala da outra. Compreensão em nível
 * CEFR se apoia em prosódia; sem ela o item de escuta mede outra coisa.
 *
 * Então o servidor passou a falar, e o `speechSynthesis` virou o plano B.
 * `app/tts.py` conta a decisão inteira, inclusive por que o custo continua
 * contido.
 *
 * ## Por que é um arquivo à parte, e não mais uma função em `fala.ts`
 *
 * Porque `fala.ts` é puro: texto entra, texto (ou uma locução) sai, sem rede.
 * É isso que deixa `test/fala.test.ts` exercitar a limpeza do texto sem subir
 * cliente de API, sessão nem armazenamento offline. Trazer o `import` de
 * `@/api/endpoints` para lá arrastaria tudo isso para dentro de um teste que
 * só quer saber se "[[clean up]]" perde os colchetes.
 */

import { languages } from "@/api/endpoints";
import { textoParaFala } from "@/lib/fala";

/** Uma fala pronta para virar áudio: o texto e qual interlocutor diz. */
export interface FalaParaNarrar {
  texto: string;
  /** Índice do interlocutor — a mesma conta que dá uma voz a cada pessoa. */
  voz: number;
}

/**
 * Áudios já baixados, por texto+idioma+voz.
 *
 * Existe porque o pedido é POST, e POST o navegador não guarda em cache: sem
 * isto, tocar o mesmo diálogo duas vezes seguidas — o que se faz o tempo todo
 * num exercício de escuta — bateria no servidor de novo a cada clique.
 *
 * Guarda a URL `blob:`, e não os bytes: é o que `<audio src>` consome, e
 * mantê-la viva é justamente o que evita o segundo download. O custo é um
 * objeto por fala ouvida na aba, liberado quando a aba fecha.
 */
const baixados = new Map<string, string>();

function chaveDoAudio(texto: string, idioma: string, voz: number): string {
  return `${idioma} ${voz} ${texto}`;
}

/** O endereço tocável de uma fala, ou `null` se o servidor não puder gerar. */
async function urlDaFala(texto: string, idioma: string, voz: number): Promise<string | null> {
  // A mesma limpeza da voz do navegador: sem ela o modelo leria "underscore"
  // no lugar da lacuna e os colchetes do trecho destacado.
  const limpo = textoParaFala(texto, idioma);
  if (!limpo) return null;
  const chave = chaveDoAudio(limpo, idioma, voz);
  const guardado = baixados.get(chave);
  if (guardado) return guardado;
  try {
    const url = URL.createObjectURL(await languages.narrar(limpo, idioma, voz));
    baixados.set(chave, url);
    return url;
  } catch {
    // 503 (sem chave ou sem cota), 401 ou rede fora. Nenhum deles é erro de
    // tela: quem chamou decide, e a decisão é cair para a voz do navegador.
    return null;
  }
}

/**
 * Os áudios de um diálogo inteiro, na ordem — ou `null`.
 *
 * É tudo ou nada de propósito. Se uma fala viesse do servidor e outra do
 * sintetizador, o timbre trocaria no meio do diálogo, e isso soa como defeito
 * do app, não como recurso degradado.
 *
 * As falas são pedidas em paralelo porque a geração é o passo lento: em
 * série, um diálogo de quatro linhas somaria quatro esperas antes da primeira
 * palavra.
 */
export async function audiosDasFalas(
  falas: FalaParaNarrar[],
  idioma: string,
): Promise<HTMLAudioElement[] | null> {
  if (falas.length === 0) return null;
  const urls = await Promise.all(falas.map((f) => urlDaFala(f.texto, idioma, f.voz)));
  if (urls.some((url) => url === null)) return null;
  return (urls as string[]).map((url) => new Audio(url));
}
