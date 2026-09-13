/**
 * Região e abrangência das vagas.
 *
 * Quem não pode se mudar de estado não tem o que fazer com vaga presencial a
 * 900 km. A pessoa diz onde mora e até onde vai; a tela de Vagas mostra
 * presencial e híbrida só dentro desse raio, e remota de qualquer lugar.
 *
 * A cidade é escolhida da lista, e não digitada livre: "Vit" sugere "Vitória -
 * ES", e o que se grava é o nome como o IBGE escreve — é esse nome que o
 * servidor sabe localizar no mapa para medir a distância.
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { geo as geoApi } from "@/api/endpoints";
import type { City, Profile } from "@/api/types";
import { ACC, ACC4, C, SIZE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { Kicker, Panel } from "@/components/ui/primitives";

/** O mesmo padrão do servidor (services/vagas.py) quando nada foi escolhido. */
export const RAIO_PADRAO_KM = 50;

const RAIOS: readonly { km: number; rotulo: string }[] = [
  { km: 0, rotulo: "Só remotas" },
  { km: 10, rotulo: "10 km" },
  { km: 25, rotulo: "25 km" },
  { km: 50, rotulo: "50 km" },
  { km: 100, rotulo: "100 km" },
  { km: 200, rotulo: "200 km" },
];

export function RegiaoDasVagas({
  perfil,
  salvar,
  estado,
}: {
  perfil: Profile;
  salvar: (mudanca: Partial<Profile>) => void;
  /** A confirmação de salvamento deste painel. */
  estado?: ReactNode;
}) {
  const raio = perfil.job_radius_km ?? RAIO_PADRAO_KM;
  const [outro, setOutro] = useState(RAIOS.some((r) => r.km === raio) ? "" : String(raio));

  return (
    <Panel pad={16.8}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 11.2, marginBottom: 5.6 }}>
        <Kicker>Região e abrangência das vagas</Kicker>
        {estado}
      </div>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "70ch" }}>
        Vagas presenciais e híbridas aparecem só até esta distância da sua cidade. Vagas remotas aparecem sempre,
        de qualquer lugar.
      </p>

      <CampoDeCidade
        cidade={perfil.city ?? ""}
        uf={perfil.state ?? ""}
        onEscolher={(cidade) => salvar({ city: cidade.nome, state: cidade.uf })}
      />

      <div style={{ fontSize: SIZE.apoio, color: TEXT.faint, margin: "14px 0 5.6px" }}>Até que distância</div>
      <div
        role="radiogroup"
        aria-label="Raio das vagas presenciais"
        style={{ display: "flex", flexWrap: "wrap", gap: 5.6, alignItems: "center" }}
      >
        {RAIOS.map((opcao) => {
          const ativo = raio === opcao.km;
          return (
            <button
              key={opcao.km}
              type="button"
              role="radio"
              aria-checked={ativo}
              onClick={() => {
                setOutro("");
                salvar({ job_radius_km: opcao.km });
              }}
              style={{
                padding: "7px 14px",
                borderRadius: 6,
                font: "inherit",
                fontSize: 13,
                cursor: "pointer",
                border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.16)"}`,
                background: ativo ? "rgba(145,132,217,.13)" : "transparent",
                color: ativo ? ACC4 : TEXT.muted,
              }}
            >
              {opcao.rotulo}
            </button>
          );
        })}
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: TEXT.muted }}>
          ou
          <input
            className="input"
            type="number"
            inputMode="numeric"
            min={1}
            max={1000}
            aria-label="Outro raio em km"
            placeholder="outro"
            value={outro}
            onChange={(evento) => setOutro(evento.target.value)}
            onBlur={() => {
              const km = Math.round(Number(outro));
              if (!outro || !Number.isFinite(km) || km < 1 || km > 1000 || km === raio) return;
              salvar({ job_radius_km: km });
            }}
            style={{ width: 84 }}
          />
          km
        </label>
      </div>
      <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "8.4px 0 0" }}>
        {raio === 0
          ? "Só vagas remotas vão aparecer."
          : perfil.city
            ? `Presenciais e híbridas até ${raio} km de ${perfil.city}${perfil.state ? ` - ${perfil.state}` : ""}.`
            : "Escolha a sua cidade para as presenciais aparecerem pela distância."}
        {perfil.job_radius_km == null && raio !== 0 ? " (padrão)" : ""}
      </p>
    </Panel>
  );
}

/** Campo de cidade com sugestões enquanto se digita (padrão combobox da WAI-ARIA).
 * A lista usa as classes do `ui/Select`: a mesma caixa, o mesmo destaque. */
function CampoDeCidade({
  cidade,
  uf,
  onEscolher,
}: {
  cidade: string;
  uf: string;
  onEscolher: (cidade: City) => void;
}) {
  const atual = cidade ? `${cidade}${uf ? ` - ${uf}` : ""}` : "";
  const [texto, setTexto] = useState(atual);
  const [sugestoes, setSugestoes] = useState<City[]>([]);
  const [aberta, setAberta] = useState(false);
  const [destaque, setDestaque] = useState(0);
  const [erro, setErro] = useState<string | null>(null);
  const id = useId();
  const pedido = useRef(0);

  useEffect(() => setTexto(atual), [atual]);

  useEffect(() => {
    const consulta = texto.trim();
    if (!aberta || consulta.length < 2 || consulta === atual) {
      setSugestoes([]);
      return undefined;
    }
    // Espera a pessoa parar de digitar: uma consulta por letra seria
    // desperdício, e respostas fora de ordem trocariam a lista embaixo do cursor.
    const numero = ++pedido.current;
    const temporizador = window.setTimeout(() => {
      geoApi
        .cidades(consulta)
        .then((lista) => {
          if (numero !== pedido.current) return;
          setSugestoes(lista);
          setDestaque(0);
          setErro(null);
        })
        .catch(() => {
          if (numero === pedido.current) setErro("Não consegui buscar cidades agora.");
        });
    }, 180);
    return () => window.clearTimeout(temporizador);
  }, [texto, aberta, atual]);

  function escolher(escolhida: City) {
    setTexto(`${escolhida.nome} - ${escolhida.uf}`);
    setAberta(false);
    setSugestoes([]);
    onEscolher(escolhida);
  }

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
      setTexto(atual);
    }
  }

  const mostrarLista = aberta && sugestoes.length > 0;

  return (
    <div className="field" style={{ maxWidth: 420 }}>
      <label htmlFor={`${id}-cidade`}>Cidade onde você mora</label>
      <div className="sel">
        <Icon
          name="mapPin"
          size={15}
          style={{
            position: "absolute",
            left: 10,
            top: "50%",
            transform: "translateY(-50%)",
            color: TEXT.faint,
            pointerEvents: "none",
          }}
        />
        <input
          id={`${id}-cidade`}
          className="input"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={mostrarLista}
          aria-controls={`${id}-lista`}
          aria-activedescendant={mostrarLista ? `${id}-op-${destaque}` : undefined}
          autoComplete="off"
          placeholder="Comece a digitar: Vit…"
          value={texto}
          onChange={(evento) => {
            setTexto(evento.target.value);
            setAberta(true);
          }}
          onFocus={() => setAberta(true)}
          onBlur={() => setAberta(false)}
          onKeyDown={teclas}
          style={{ width: "100%", paddingLeft: 32 }}
        />
        <ul id={`${id}-lista`} role="listbox" aria-label="Cidades sugeridas" className="sel-lista" hidden={!mostrarLista}>
          {sugestoes.map((sugestao, posicao) => (
            <li
              key={sugestao.ibge}
              id={`${id}-op-${posicao}`}
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
                <span style={{ marginLeft: "auto", fontSize: 11, color: TEXT.faint }}>capital</span>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
      {erro ? <div style={{ fontSize: 11.5, color: C.ambar, marginTop: 4 }}>{erro}</div> : null}
    </div>
  );
}
