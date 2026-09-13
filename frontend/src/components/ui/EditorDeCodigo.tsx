/**
 * Campo de texto com cores de código.
 *
 * Um `<textarea>` de verdade por cima de uma camada colorida: a letra do campo
 * é transparente (só o cursor e a seleção aparecem) e quem mostra o texto é a
 * camada de baixo. Assim continua valendo tudo o que um campo nativo dá de
 * graça — desfazer, colar, leitor de tela, teclado do celular — sem trazer um
 * editor inteiro para uma caixa de resposta.
 *
 * As duas camadas precisam da MESMA caixa (fonte, espaçamento, quebra de
 * linha, borda); qualquer diferença desalinha a cor da letra. Por isso as
 * medidas moram numa classe só, `.editor-codigo__camada`, usada pelas duas.
 *
 * O texto é renderizado como texto (spans do React), nunca como HTML: o que a
 * pessoa digita não vira marcação nem script.
 */

import { useMemo, useRef } from "react";
import { COR_DO_PAPEL, realcar } from "@/lib/realce";

interface Props {
  id: string;
  value: string;
  onChange: (valor: string) => void;
  placeholder?: string;
  minHeight?: number;
  describedBy?: string;
}

export function EditorDeCodigo({ id, value, onChange, placeholder, minHeight = 200, describedBy }: Props) {
  const camada = useRef<HTMLPreElement>(null);
  const pedacos = useMemo(() => realcar(value), [value]);

  return (
    <div className="editor-codigo">
      <pre ref={camada} aria-hidden className="editor-codigo__camada editor-codigo__cores campo-codigo">
        {pedacos.map((pedaco, posicao) => (
          <span
            key={posicao}
            data-papel={pedaco.papel}
            style={{
              color: COR_DO_PAPEL[pedaco.papel],
              fontStyle: pedaco.papel === "comentario" ? "italic" : undefined,
            }}
          >
            {pedaco.texto}
          </span>
        ))}
        {/* Uma quebra no fim do texto só ganha altura com algo depois dela. */}
        {"\n "}
      </pre>
      <textarea
        id={id}
        className="editor-codigo__camada editor-codigo__campo campo-codigo"
        value={value}
        onChange={(evento) => onChange(evento.target.value)}
        onScroll={(evento) => {
          if (camada.current) {
            camada.current.scrollTop = evento.currentTarget.scrollTop;
            camada.current.scrollLeft = evento.currentTarget.scrollLeft;
          }
        }}
        placeholder={placeholder}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        autoComplete="off"
        aria-describedby={describedBy}
        style={{ minHeight }}
      />
    </div>
  );
}
