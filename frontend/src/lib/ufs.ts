/**
 * As 27 unidades federativas do Brasil.
 *
 * Um `select` em vez de campo livre porque "ES", "Es", "Espírito Santo" e
 * "Espirito Santo" seriam quatro lugares diferentes na hora de agrupar
 * qualquer coisa por região — e digitar a sigla errada é fácil.
 *
 * O app é pt-BR (ver o padrão de `locale` e `timezone_name` em
 * backend/app/models.py), então a lista fechada cobre quem ele atende hoje.
 * O backend aceita até 60 caracteres neste campo justamente para o dia em que
 * isso deixar de ser verdade.
 */
export const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
] as const;
