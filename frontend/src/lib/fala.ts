/**
 * O que vai para a síntese de voz do navegador.
 *
 * ## Por que limpar o texto
 *
 * A síntese lê o que recebe, literalmente. "___" sai "underscore underscore",
 * "[[clean up]]" sai com os colchetes, e "i'll" em minúsculas vira "i", "ll"
 * em várias vozes. A pessoa precisa ouvir a FRASE, não os símbolos que a
 * tela usa para desenhar lacuna e destaque.
 *
 * ## Por que escolher a voz
 *
 * Sem voz do idioma instalada, o navegador não recusa: lê inglês com a voz
 * padrão do sistema — num Windows em português, a voz portuguesa, que
 * pronuncia cada palavra como se fosse português. É o áudio "péssimo e
 * literal". Preferimos vozes neurais/online (Edge "Natural", Chrome "Google",
 * Safari "Premium"/"Enhanced"), e a tela avisa quando não há nenhuma do idioma.
 */

/** Região padrão de cada idioma, para quando o sistema não diz. */
export const REGIAO_DA_VOZ: Record<string, string> = {
  en: "en-US",
  es: "es-ES",
  fr: "fr-FR",
  de: "de-DE",
  it: "it-IT",
  ja: "ja-JP",
  zh: "zh-CN",
  ko: "ko-KR",
  pt: "pt-BR",
};

export function textoParaFala(texto: string, idioma = "en"): string {
  let limpo = texto
    // Destaque: fica a palavra, somem os colchetes.
    .replace(/\[\[([^[\]]+)\]\]/g, "$1")
    // Lacuna: uma pausa em vez do nome do símbolo.
    .replace(/_{2,}/g, " … ")
    // Apóstrofo tipográfico confunde parte das vozes.
    .replace(/[’‘]/g, "'")
    // Marcação que não é fala.
    .replace(/[*#`]+/g, "");
  if (idioma === "en") {
    // "i", "i'll", "i'm" em minúsculas: o pronome é sempre maiúsculo em
    // inglês, e várias vozes só o reconhecem assim.
    limpo = limpo.replace(/\bi(?=('(ll|m|ve|d)\b|\s|[,.!?]|$))/g, "I");
  }
  return limpo.replace(/\s{2,}/g, " ").trim();
}

const QUALIDADE = /natural|neural|online|google|premium|enhanced|siri/i;

const normaliza = (lang: string) => lang.toLowerCase().replace("_", "-");

/** As vozes do idioma entre as instaladas, da melhor para a pior. */
export function vozesDoIdioma(todas: SpeechSynthesisVoice[], idioma: string): SpeechSynthesisVoice[] {
  const regiao = normaliza(REGIAO_DA_VOZ[idioma] ?? idioma);
  const nota = (voz: SpeechSynthesisVoice) =>
    (QUALIDADE.test(voz.name) ? 2 : 0) + (normaliza(voz.lang) === regiao ? 1 : 0);
  return todas.filter((voz) => normaliza(voz.lang).startsWith(idioma)).sort((a, b) => nota(b) - nota(a));
}

/** Uma locução pronta: texto limpo, idioma e a melhor voz disponível. */
export function locucao(
  texto: string,
  idioma: string,
  vozes: SpeechSynthesisVoice[],
  indiceDaVoz = 0,
): SpeechSynthesisUtterance {
  const fala = new SpeechSynthesisUtterance(textoParaFala(texto, idioma));
  const voz = vozes.length ? vozes[indiceDaVoz % vozes.length] : undefined;
  fala.lang = voz?.lang ?? REGIAO_DA_VOZ[idioma] ?? idioma;
  if (voz) fala.voice = voz;
  return fala;
}

/** Aviso para quando o sistema não tem voz do idioma: o áudio sairia com a
 * pronúncia de outra língua, e a pessoa culparia o próprio ouvido. */
export const SEM_VOZ_DO_IDIOMA =
  "Seu navegador não tem voz neste idioma, então o áudio sai com pronúncia errada. " +
  "No Edge ou no Chrome a voz vem pronta; no Windows, dá para instalar em Configurações › Hora e idioma › Fala.";
