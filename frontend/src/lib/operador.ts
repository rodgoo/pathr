/**
 * Quem opera ESTA instalação do PathR.
 *
 * Os textos legais (termos, privacidade, segurança) nomeiam um responsável e
 * um endereço para pedidos sobre dados. Isso não pode ficar fixo no código:
 * quem publicar um fork sem trocar estaria prometendo, em nome de outra
 * pessoa, o que só ela pode cumprir — responder um pedido de exclusão, por
 * exemplo.
 *
 * O padrão é o desta instalação, então o build de sempre não muda de
 * comportamento; um fork define `VITE_OPERADOR` e `VITE_EMAIL_CONTATO`.
 *
 * Trocar os dois NÃO basta para publicar um fork: os textos descrevem
 * Supabase, Fly, Brevo e as decisões desta operação. Precisam ser lidos.
 */
// O SERVIÇO, e não uma pessoa. Trocar o nome próprio pelo nome do app é o que
// se costuma fazer enquanto não há CNPJ — e não muda quem responde: pela LGPD,
// controlador é quem de fato decide sobre o tratamento (art. 5º, VI), com nome
// escrito na página ou sem. O que o nome faz é informar quem lê, como o art. 9º
// exige; some-lo não transfere obrigação nenhuma.
export const OPERADOR = import.meta.env.VITE_OPERADOR ?? "PathR";
export const EMAIL_CONTATO = import.meta.env.VITE_EMAIL_CONTATO ?? "privacidade@notter.com.br";
