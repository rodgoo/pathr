/**
 * A rede de segurança embaixo da tela ativa.
 *
 * Sem ela, uma exceção durante o render — um campo que veio com outra forma
 * do servidor, um `.filter` num objeto que devia ser lista — desmonta a
 * árvore inteira do React e deixa a página EM BRANCO. Sem barra de navegação,
 * sem mensagem, sem saída: no celular, a única ação possível é fechar o app.
 * Isso aconteceu de verdade durante o desenvolvimento desta versão.
 *
 * O limite fica em volta do conteúdo e DENTRO da moldura, de propósito: a
 * navegação continua desenhada, então a pessoa sai da tela quebrada tocando
 * em qualquer outro destino.
 *
 * Classe porque o React não tem equivalente em função: `componentDidCatch` e
 * `getDerivedStateFromError` só existem em componentes de classe.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";
import { TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";

interface Props {
  children: ReactNode;
  /** Muda quando a tela muda: é o que faz o limite se rearmar ao navegar. */
  resetKey: string;
}

interface State {
  falhou: boolean;
}

export class ScreenBoundary extends Component<Props, State> {
  state: State = { falhou: false };

  static getDerivedStateFromError(): State {
    return { falhou: true };
  }

  componentDidUpdate(anterior: Props) {
    // Trocar de tela limpa o erro. Sem isto, um render que falhou uma vez
    // deixaria a moldura mostrando a mensagem para sempre.
    if (this.state.falhou && anterior.resetKey !== this.props.resetKey) {
      this.setState({ falhou: false });
    }
  }

  componentDidCatch(erro: Error, info: ErrorInfo) {
    // O console é onde isto some menos: não há coletor de erros no projeto, e
    // engolir em silêncio um render quebrado é o que torna esse tipo de bug
    // impossível de reproduzir depois.
    console.error("Tela quebrou:", erro, info.componentStack);
  }

  render() {
    if (!this.state.falhou) return this.props.children;

    return (
      <div
        role="alert"
        style={{
          padding: "44px 22.4px",
          borderRadius: 14,
          textAlign: "center",
          fontSize: 13.5,
          color: "rgba(233,233,237,.8)",
          border: "1px solid rgba(207,162,94,.35)",
          background: "rgba(207,162,94,.08)",
        }}
      >
        <p style={{ margin: "0 0 8.4px", fontSize: 16, color: TEXT.full }}>
          Esta tela não abriu
        </p>
        <p style={{ margin: "0 auto 16.8px", maxWidth: "44ch", lineHeight: 1.6 }}>
          Alguma coisa quebrou ao desenhar o conteúdo. As outras telas continuam
          funcionando — e nada do que você registrou se perdeu.
        </p>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => this.setState({ falhou: false })}
        >
          <Icon name="refresh" size={15} />
          Tentar de novo
        </button>
      </div>
    );
  }
}
