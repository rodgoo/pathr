/**
 * O select do PathR.
 *
 * O `<select>` nativo não aceita estilo na lista aberta: o navegador desenha
 * a sua, com a fonte, o azul de seleção e as bordas do sistema operacional —
 * um retângulo do Windows 98 no meio de uma tela escura. E não aceita ícone
 * dentro da opção, que é o que faz "Java" e "JavaScript" se distinguirem de
 * relance numa lista de dezesseis linguagens.
 *
 * Então a lista é nossa, e o que o nativo dava de graça é refeito aqui, porque
 * sem isso o bonito sai caro para quem usa teclado ou leitor de tela:
 *
 * - **Padrão ARIA de combobox só-de-escolha.** O gatilho é `role="combobox"` e
 *   o FOCO FICA NELE; a opção ativa é anunciada por `aria-activedescendant`.
 *   Mover o foco para dentro da lista faria o leitor de tela perder o rótulo
 *   do campo a cada seta.
 * - **O teclado do nativo.** Setas, Home/End, Enter e Espaço, Esc para fechar,
 *   Tab fecha e segue. E digitar letras pula para a opção — com a lista
 *   fechada, escolhe direto, como o nativo faz. Numa lista de 27 UFs, é assim
 *   que se chega a "SP" sem rolar.
 * - **`required` e `name` continuam valendo num `<form>`.** Um campo
 *   invisível carrega o valor e a obrigatoriedade; a validação do navegador
 *   ancora nele o balão "preencha este campo".
 * - **`<label htmlFor>` funciona.** O gatilho é um `<button>`, que é elemento
 *   rotulável: o rótulo nomeia o campo e clicar nele foca o gatilho.
 */

import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useT } from "@/lib/i18n";

export interface SelectOption<T extends string> {
  value: T;
  label: string;
  /** Ícone antes do rótulo — 18px de área. */
  icon?: ReactNode;
}

interface SelectProps<T extends string> {
  /** Vai no gatilho: é o alvo do `<label htmlFor>`. */
  id: string;
  options: readonly SelectOption<T>[];
  /** `""` é "nada escolhido ainda", e mostra o `placeholder`. */
  value: T | "";
  onChange: (value: T) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  /** Nome do campo num `<form>` nativo. */
  name?: string;
  /** Rótulo para tecnologia assistiva, quando não há `<label>` visível. */
  label?: string;
  style?: CSSProperties;
}

/** Quanto a lista cresce antes de passar a rolar. Cabe ~7 opções. */
const ALTURA_MAXIMA = 280;

/** Quanto tempo as letras digitadas se somam numa busca só. Igual ao nativo. */
const JANELA_DE_DIGITACAO_MS = 700;

export function Select<T extends string>({
  id,
  options,
  value,
  onChange,
  placeholder,
  disabled = false,
  required = false,
  name,
  label,
  style,
}: SelectProps<T>) {
  const t = useT();
  const rotuloVazio = placeholder ?? t("comum.selecione");
  const listaId = useId();
  const raiz = useRef<HTMLDivElement | null>(null);
  const lista = useRef<HTMLUListElement | null>(null);
  const [aberta, setAberta] = useState(false);
  const [ativa, setAtiva] = useState(-1);
  const [paraCima, setParaCima] = useState(false);
  const digitado = useRef({ texto: "", ate: 0 });

  const indiceEscolhido = options.findIndex((opcao) => opcao.value === value);
  const escolhida = indiceEscolhido >= 0 ? options[indiceEscolhido] : null;

  function abrir() {
    if (disabled || options.length === 0) return;
    setAtiva(indiceEscolhido >= 0 ? indiceEscolhido : 0);
    setAberta(true);
  }

  function escolher(indice: number) {
    const opcao = options[indice];
    if (!opcao) return;
    if (opcao.value !== value) onChange(opcao.value);
    setAberta(false);
  }

  // Abre para cima quando não cabe embaixo. No celular o teclado virtual e a
  // barra inferior comem a metade de baixo da tela, e uma lista que abre para
  // fora da vista parece não ter aberto.
  useLayoutEffect(() => {
    if (!aberta || !raiz.current) return;
    const caixa = raiz.current.getBoundingClientRect();
    const altura = Math.min(ALTURA_MAXIMA, lista.current?.scrollHeight ?? ALTURA_MAXIMA);
    const embaixo = window.innerHeight - caixa.bottom;
    setParaCima(embaixo < altura + 12 && caixa.top > embaixo);
  }, [aberta]);

  // A opção ativa sempre à vista, inclusive a já escolhida ao abrir: abrir a
  // lista de UFs em "SP" e mostrar "AC" obrigaria a procurar a própria escolha.
  useEffect(() => {
    if (!aberta || ativa < 0) return;
    const alvo = lista.current?.children[ativa] as HTMLElement | undefined;
    alvo?.scrollIntoView?.({ block: "nearest" });
  }, [aberta, ativa]);

  // Clicar fora fecha. `pointerdown` e não `click`: fecha antes de o clique
  // chegar a outro controle, que senão receberia o clique com a lista ainda
  // aberta por cima dele.
  useEffect(() => {
    if (!aberta) return undefined;
    const aoTocar = (evento: PointerEvent) => {
      if (!raiz.current?.contains(evento.target as Node)) setAberta(false);
    };
    document.addEventListener("pointerdown", aoTocar);
    return () => document.removeEventListener("pointerdown", aoTocar);
  }, [aberta]);

  /** Primeira opção, a partir da seguinte à atual, que começa com o digitado. */
  function buscarPorLetras(tecla: string): number {
    const agora = Date.now();
    const anterior = digitado.current;
    const texto = (agora < anterior.ate ? anterior.texto : "") + tecla.toLowerCase();
    digitado.current = { texto, ate: agora + JANELA_DE_DIGITACAO_MS };

    const partida = aberta ? ativa : indiceEscolhido;
    // Letra repetida ("s", "s") circula entre as que começam com ela, como no
    // nativo; texto maior ("sp") procura a partir da atual, incluindo-a.
    const repetida = texto.length > 1 && [...texto].every((letra) => letra === texto[0]);
    const procura = repetida ? texto[0] : texto;
    const inicio = texto.length === 1 || repetida ? partida + 1 : Math.max(partida, 0);
    for (let passo = 0; passo < options.length; passo += 1) {
      const indice = (inicio + passo) % options.length;
      if (options[indice].label.toLowerCase().startsWith(procura)) return indice;
    }
    return -1;
  }

  function aoTeclar(evento: KeyboardEvent<HTMLButtonElement>) {
    if (disabled) return;
    const { key } = evento;

    if (!aberta) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(key)) {
        evento.preventDefault();
        abrir();
        return;
      }
      if (key.length === 1 && /\S/.test(key)) {
        const achada = buscarPorLetras(key);
        if (achada >= 0) escolher(achada);
      }
      return;
    }

    switch (key) {
      case "ArrowDown":
        evento.preventDefault();
        setAtiva((atual) => Math.min(options.length - 1, atual + 1));
        return;
      case "ArrowUp":
        evento.preventDefault();
        setAtiva((atual) => Math.max(0, atual - 1));
        return;
      case "Home":
        evento.preventDefault();
        setAtiva(0);
        return;
      case "End":
        evento.preventDefault();
        setAtiva(options.length - 1);
        return;
      case "Enter":
      case " ":
        evento.preventDefault();
        escolher(ativa);
        return;
      case "Escape":
        evento.preventDefault();
        setAberta(false);
        return;
      case "Tab":
        // Tab escolhe o que está ativo e segue, como no nativo — e fecha, para
        // a lista não ficar aberta atrás do próximo campo.
        if (ativa >= 0) escolher(ativa);
        else setAberta(false);
        return;
      default:
        if (key.length === 1 && /\S/.test(key)) {
          const achada = buscarPorLetras(key);
          if (achada >= 0) setAtiva(achada);
        }
    }
  }

  const idDaOpcao = (indice: number) => `${listaId}-${indice}`;

  return (
    <div ref={raiz} className="sel" style={style}>
      <button
        id={id}
        type="button"
        className="input sel-gatilho"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={aberta}
        aria-controls={listaId}
        aria-activedescendant={aberta && ativa >= 0 ? idDaOpcao(ativa) : undefined}
        aria-label={label}
        aria-required={required || undefined}
        disabled={disabled}
        onClick={() => (aberta ? setAberta(false) : abrir())}
        onKeyDown={aoTeclar}
      >
        {escolhida?.icon ? <span className="sel-icone">{escolhida.icon}</span> : null}
        <span className={escolhida ? "sel-rotulo" : "sel-rotulo sel-vazio"}>
          {escolhida ? escolhida.label : rotuloVazio}
        </span>
        <svg className="sel-seta" width="14" height="14" viewBox="0 0 24 24" aria-hidden>
          <path
            d="M6 9l6 6 6-6"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {/* O valor para o `<form>`. Invisível e fora da ordem de tabulação, mas
          NÃO `display: none` — um campo obrigatório escondido assim faz o
          navegador recusar o envio sem conseguir mostrar onde está o erro. */}
      {name || required ? (
        <input
          className="sel-nativo"
          tabIndex={-1}
          aria-hidden
          name={name}
          required={required}
          value={value}
          onChange={() => undefined}
          onFocus={() => document.getElementById(id)?.focus()}
        />
      ) : null}

      <ul
        ref={lista}
        id={listaId}
        role="listbox"
        aria-labelledby={id}
        className={paraCima ? "sel-lista sel-para-cima" : "sel-lista"}
        hidden={!aberta}
        style={{ maxHeight: ALTURA_MAXIMA }}
      >
        {options.map((opcao, indice) => (
          <li
            key={opcao.value}
            id={idDaOpcao(indice)}
            role="option"
            aria-selected={opcao.value === value}
            className={indice === ativa ? "sel-opcao sel-ativa" : "sel-opcao"}
            // `mousedown` com preventDefault: sem isto o gatilho perde o foco
            // no clique, e quem navega pelo teclado depois volta ao início.
            onMouseDown={(evento) => evento.preventDefault()}
            onMouseEnter={() => setAtiva(indice)}
            onClick={() => escolher(indice)}
          >
            {opcao.icon ? <span className="sel-icone">{opcao.icon}</span> : null}
            <span className="sel-rotulo">{opcao.label}</span>
            {opcao.value === value ? (
              <svg className="sel-marca" width="14" height="14" viewBox="0 0 24 24" aria-hidden>
                <path
                  d="M5 12.5l4.5 4.5L19 7.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
