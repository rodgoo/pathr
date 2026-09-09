/**
 * A marca do PathR enquanto algo carrega.
 *
 * Substitui o "Carregando…" de texto puro que estava em toda tela. A troca não
 * é enfeite: uma palavra parada não distingue "está vindo" de "travou", e é
 * essa dúvida que faz alguém tocar de novo, recarregar, ou fechar o app. Uma
 * animação em curso responde a pergunta sem dizer nada.
 *
 * Dois movimentos, e cada um diz uma coisa:
 *
 * - **O brilho atravessando o símbolo.** É o pulso — mostra que o app está
 *   vivo. Passa sobre o ladrilho preto, onde o contraste do reflexo aparece.
 * - **O nome preenchendo por baixo.** É a espera — o texto acende da esquerda
 *   para a direita, no mesmo ritmo, e dá ao olho um lugar para pousar.
 *
 * O movimento vive no CSS (`styles/app.css`) e não aqui porque
 * `prefers-reduced-motion` precisa alcançá-lo: quem pediu menos movimento
 * recebe a marca parada e o nome legível, não uma tela em branco.
 */

import { TEXT } from "@/lib/tokens";
import { Logo } from "./Logo";

export function MarcaCarregando({
  size = 56,
  label = "Carregando…",
}: {
  size?: number;
  /** O que está sendo carregado. Vai para o leitor de tela, sempre. */
  label?: string;
}) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        padding: "44px 22.4px",
      }}
    >
      <span className="marca-brilho" style={{ borderRadius: size * (80 / 440) }}>
        <Logo size={size} />
      </span>

      <span className="nome-brilho" style={{ fontSize: size * 0.3, fontWeight: 500 }}>
        PathR
      </span>

      {/* O rótulo é a única coisa que um leitor de tela tem para ler: o brilho
          e o nome animado não dizem O QUE está carregando. */}
      <span style={{ fontSize: 12, color: TEXT.faint }}>{label}</span>
    </div>
  );
}
