/**
 * A marca do PathR.
 *
 * O símbolo é um traçado só — o caminho que sobe, contorna o nó e segue — sobre
 * o ladrilho preto de cantos arredondados. Ele vive aqui como elemento React, e
 * não como `<img src="/logo.svg">`, pelo mesmo motivo dos ícones: o arquivo
 * estático seria um pedido de rede a mais para 32px de desenho, e um `img`
 * pisca antes de carregar justo na primeira tela que a pessoa vê.
 *
 * O arquivo `public/logo.svg` continua existindo, com o mesmo desenho, porque o
 * favicon e o manifesto precisam de uma URL — lá o navegador não executa React.
 * Os dois são a mesma marca; ao mexer em um, mexa no outro.
 */

import type { SVGProps } from "react";

/** O raio do ladrilho no desenho original, em fração do lado. */
const RADIUS_RATIO = 80 / 440;

interface LogoProps extends Omit<SVGProps<SVGSVGElement>, "width" | "height"> {
  size?: number;
}

/**
 * O ladrilho da marca em `size` px.
 *
 * Decorativo por padrão: nas duas telas onde aparece, o nome "PathR" está
 * escrito ao lado, e anunciar a marca duas vezes só atrasa quem usa leitor de
 * tela. Passe `aria-label` onde o símbolo estiver sozinho.
 *
 * O anel de 1px não é enfeite: o ladrilho é preto e o fundo do app é quase
 * preto, então sem ele a borda do símbolo desaparece e o traçado branco flutua
 * solto no escuro.
 */
export function Logo({ size = 32, style, ...rest }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 440 440"
      fill="none"
      aria-hidden={rest["aria-label"] ? undefined : true}
      focusable={false}
      style={{
        flex: "none",
        borderRadius: size * RADIUS_RATIO,
        boxShadow: "0 0 0 1px rgba(233,233,237,.14)",
        ...style,
      }}
      {...rest}
    >
      <rect width="440" height="440" rx="80" fill="#000" />
      <g stroke="#fff" strokeWidth="24" strokeLinecap="round">
        <path d="M144 89.2451L126.654 93.1647C109.013 97.1509 96.2412 112.478 95.5031 130.549L93.6673 175.498C93.1115 189.108 85.6684 201.499 73.9148 208.382L58.873 217.191C55.1505 219.371 54.8762 224.65 58.3526 227.204L77.2881 241.116C87.0774 248.308 93.0679 259.559 93.5705 271.696L95.4885 318.014C96.2355 336.054 109.008 351.928 127.055 352.464C132.987 352.64 138.933 352.361 144 351.245C146.616 350.669 149.372 349.713 152.159 348.512C173.647 339.247 183 315.025 183 291.624V260.5M183 260.5C183 260.5 183 230 183 205.002C183 175.5 208.254 154.774 236.5 154.5C261.967 154.253 286 173.778 286 199.246C286 224.399 261.652 242.301 236.5 242.5C214.056 242.678 183 260.5 183 260.5Z" />
        <path d="M314 351L323.88 348.232C340.681 343.524 352.492 328.47 353.066 311.032L354.666 262.462C355.072 250.124 361.152 238.666 371.141 231.412L383.039 222.772C386.115 220.538 386.365 216.042 383.554 213.482L367.786 199.117C359.809 191.849 355.107 181.667 354.747 170.883L353.305 127.716C352.621 107.233 336.567 90.5807 316.123 89.1487L314 89" />
      </g>
    </svg>
  );
}
