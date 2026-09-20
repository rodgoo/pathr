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
export const OPERADOR = import.meta.env.VITE_OPERADOR ?? "Rodrigo Carvalho";
export const EMAIL_CONTATO = import.meta.env.VITE_EMAIL_CONTATO ?? "privacidade@notter.com.br";
