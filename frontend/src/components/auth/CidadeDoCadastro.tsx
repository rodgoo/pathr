/**
 * A cidade no cadastro: sugestões enquanto se digita, e a UF sai da escolha.
 *
 * Antes eram dois campos, cidade livre e UF num select — e "Vitoria" sem
 * acento, ou Vitória com a UF errada, virava uma cidade que as vagas por
 * distância não sabiam localizar. Aqui a pessoa digita "Vit", escolhe
 * "Vitória - ES" e o que se grava é o nome como o IBGE escreve, com a UF certa.
 *
 * Reconhece sozinha quando o texto digitado já É uma cidade: se a pessoa
 * escreve "Vitória" inteiro e há uma única cidade com esse nome, ela é
 * escolhida sem precisar clicar. Com homônimos ("São Domingos" existe em
 * vários estados), a lista fica aberta para a pessoa escolher.
 *
 * Mesmo padrão de combobox da WAI-ARIA do campo de região das Configurações,
 * e as mesmas classes do `ui/Select`.
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { geo as geoApi } from "@/api/endpoints";
import type { City } from "@/api/types";
import { Icon } from "@/components/ui/icons";
import { useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";

function normaliza(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function CidadeDoCadastro({
  id,
  escolhida,
  onEscolher,
}: {
  id: string;
  escolhida: City | null;
  /** `null` quando a pessoa volta a editar o texto depois de escolher. */
  onEscolher: (cidade: City | null) => void;
}) {
  const t = useT();
  const [texto, setTexto] = useState(escolhida ? `${escolhida.nome} - ${escolhida.uf}` : "");
  const [sugestoes, setSugestoes] = useState<City[]>([]);
  const [aberta, setAberta] = useState(false);
  const [destaque, setDestaque] = useState(0);
  const [erro, setErro] = useState<string | null>(null);
  const listaId = useId();
  const pedido = useRef(0);

  function escolher(cidade: City) {
    setTexto(`${cidade.nome} - ${cidade.uf}`);
    setAberta(false);
    setSugestoes([]);
    onEscolher(cidade);
  }

  useEffect(() => {
    const consulta = texto.trim();
    if (escolhida || consulta.length < 2) {
      setSugestoes([]);
      return undefined;
    }
    // Espera a pessoa parar de digitar: uma consulta por letra seria
    // desperdício, e respostas fora de ordem trocariam a lista embaixo do cursor.
    const numero = ++pedido.current;
    const temporizador = window.setTimeout(() => {
      geoApi
        .cidadesPublico(consulta)
        .then((lista) => {
          if (numero !== pedido.current) return;
          setErro(null);
          const iguais = lista.filter((c) => normaliza(c.nome) === normaliza(consulta));
          if (iguais.length === 1) {
            escolher(iguais[0]);
            return;
          }
          setSugestoes(lista);
          setDestaque(0);
        })
        .catch(() => {
          if (numero === pedido.current) setErro(t("cidade.erro"));
        });
    }, 200);
    return () => window.clearTimeout(temporizador);
    // `escolher` só usa setters estáveis e o callback do pai.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto, escolhida]);

  function teclas(evento: KeyboardEvent<HTMLInputElement>) {
    if (evento.key === "ArrowDown" && sugestoes.length) {
      evento.preventDefault();
      setAberta(true);
      setDestaque((valor) => (valor + 1) % sugestoes.length);
    } else if (evento.key === "ArrowUp" && sugestoes.length) {
      evento.preventDefault();
      setDestaque((valor) => (valor - 1 + sugestoes.length) % sugestoes.length);
    } else if (evento.key === "Enter" && aberta && sugestoes[destaque]) {
      evento.preventDefault();
      escolher(sugestoes[destaque]);
    } else if (evento.key === "Escape") {
      setAberta(false);
    }
  }

  const mostrarLista = aberta && sugestoes.length > 0;

  return (
    <div className="field" style={{ marginBottom: 11.2 }}>
      <label htmlFor={id}>{t("cidade.label")}</label>
      <div className="sel campo-icone" style={{ position: "relative" }}>
        <span className="campo-icone-simbolo" style={escolhida ? { color: C.verde } : undefined}>
          <Icon name={escolhida ? "check" : "mapPin"} size={17} />
        </span>
        <input
          id={id}
          className="input"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={mostrarLista}
          aria-controls={listaId}
          aria-activedescendant={mostrarLista ? `${listaId}-op-${destaque}` : undefined}
          autoComplete="off"
          placeholder={t("cidade.placeholder")}
          required
          value={texto}
          onChange={(evento) => {
            setTexto(evento.target.value);
            setAberta(true);
            if (escolhida) onEscolher(null);
          }}
          onFocus={() => setAberta(true)}
          onBlur={() => setAberta(false)}
          onKeyDown={teclas}
          style={{ width: "100%" }}
        />
        <ul id={listaId} role="listbox" aria-label={t("cidade.sugeridas")} className="sel-lista" hidden={!mostrarLista}>
          {sugestoes.map((sugestao, posicao) => (
            <li
              key={sugestao.ibge}
              id={`${listaId}-op-${posicao}`}
              role="option"
              aria-selected={posicao === destaque}
              className={posicao === destaque ? "sel-opcao sel-ativa" : "sel-opcao"}
              // `mousedown` com preventDefault: o campo não perde o foco (e a
              // lista não fecha) antes do clique chegar à opção.
              onMouseDown={(evento) => evento.preventDefault()}
              onMouseEnter={() => setDestaque(posicao)}
              onClick={() => escolher(sugestao)}
            >
              <span className="sel-icone">
                <Icon name="mapPin" size={15} />
              </span>
              <span className="sel-rotulo">
                {sugestao.nome} <span style={{ color: TEXT.faint }}>- {sugestao.uf}</span>
              </span>
              {sugestao.capital ? (
                <span style={{ marginLeft: "auto", fontSize: 11, color: TEXT.faint }}>{t("cidade.capital")}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
      {erro ? (
        <div style={{ fontSize: 11.5, color: C.ambar, marginTop: 4 }}>{erro}</div>
      ) : (
        <div style={{ fontSize: 11, color: escolhida ? C.verde : TEXT.faint, marginTop: 4 }}>
          {escolhida
            ? t("cidade.reconhecida", { nome: escolhida.nome, uf: escolhida.uf })
            : t("cidade.ufJunto")}
        </div>
      )}
    </div>
  );
}
