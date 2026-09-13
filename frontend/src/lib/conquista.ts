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

const FRASES = [
  "Constância a dois vence talento sozinho.",
  "Um puxou o outro, e ninguém ficou para trás.",
  "Todo dia um pouco, sempre juntos.",
  "Disciplina fica mais leve quando é dividida.",
  "Não foi sorte: foi um dia de cada vez.",
  "Quem estuda junto chega mais longe.",
  "A sequência é de vocês. A evolução também.",
  "Sem pular um dia. Sem largar a mão.",
  "O código compila melhor em dupla.",
  "Parceria de estudo é o melhor framework.",
  "Commit diário, merge garantido.",
  "Duas cabeças, uma meta, zero desculpas.",
];

/** Uma frase sorteada — outra a cada vez que o card abre. */
export function fraseAleatoria(sorteio: () => number = Math.random): string {
  return FRASES[Math.floor(sorteio() * FRASES.length) % FRASES.length];
}

export const TOTAL_DE_FRASES = FRASES.length;
