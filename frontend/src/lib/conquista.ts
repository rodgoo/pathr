/**
 * Os marcos da sequência de estudos em dupla, e as frases do card.
 *
 * Marcos: 7 dias (a primeira semana é a mais difícil), 30, 60, 90 — e daí em
 * diante a cada 30. Um card por marco: a sequência de 45 dias ainda mostra o
 * de 30, e o de 60 aparece no dia em que chegar lá.
 */

const PRIMEIROS = [7, 30, 60, 90];

/** O maior marco já alcançado, ou null antes do primeiro. */
export function marcoAtingido(dias: number): number | null {
  if (dias < PRIMEIROS[0]) return null;
  if (dias < 120) return [...PRIMEIROS].reverse().find((marco) => dias >= marco) ?? null;
  return Math.floor(dias / 30) * 30;
}

/** O próximo marco, para dizer quanto falta. */
export function proximoMarco(dias: number): number {
  const proximo = PRIMEIROS.find((marco) => marco > dias);
  return proximo ?? (Math.floor(dias / 30) + 1) * 30;
}

/**
 * Quantas frases o card sorteia. As frases em si moram no dicionário
 * (`conquista.frases.0`…), para saírem no idioma de quem lê; aqui fica só a
 * contagem e o sorteio.
 */
export const TOTAL_DE_FRASES = 12;

/**
 * A CHAVE de uma frase sorteada — outra a cada vez que o card abre. Devolver a
 * chave (e não o texto) deixa o card resolvê-la com `t()` no idioma ativo.
 */
export function fraseAleatoria(sorteio: () => number = Math.random): string {
  const indice = Math.floor(sorteio() * TOTAL_DE_FRASES) % TOTAL_DE_FRASES;
  return `conquista.frases.${indice}`;
}
