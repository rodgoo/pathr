/**
 * O balão de um dia: o que foi estudado e por quanto tempo.
 *
 * O quadrado verde do heatmap e as barrinhas dos cartões diziam, no máximo,
 * "11 de setembro · 4 atividades · 12 min" — num `title` nativo, que demora
 * um segundo para aparecer e não aparece no toque. Quatro atividades de quê?
 * Um gráfico de constância que não diz o que foi feito em cada dia não ajuda
 * a lembrar o que se estudou, que é metade do motivo de olhar para ele.
 *
 * Um balão só por gráfico, e não um por célula: o mapa do ano tem 371
 * quadrados, e 371 balões montados para mostrar um de cada vez seria
 * desperdício. O gatilho guarda qual dia está sob o mouse e onde ele fica.
 */

import {
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import type { ActivityItem } from "@/api/types";
import { longDate, type DayDetail } from "@/lib/dashboard";
import { useT } from "@/lib/i18n";

/** O nome de cada coisa que se faz no app, como a pessoa diria. */
const MATERIAL: Record<string, string> = {
  video: "Vídeo",
  article: "Artigo",
  doc: "Documentação",
  course: "Curso",
  book: "Livro",
  podcast: "Podcast",
  repo: "Repositório",
  exercise: "Exercício",
};

const ATIVIDADE: Record<string, string> = {
  quiz_done: "Quiz",
  explanation_done: "Explicação",
  node_done: "Módulo concluído",
  review_done: "Revisão",
  english_session: "Sessão de idioma",
  english_assessment: "Nivelamento de idioma",
  language: "Idioma",
  walkthrough: "Exemplo de código",
  roadmap_created: "Plano criado",
  resume_parsed: "Currículo importado",
};

export function nomeDaAtividade(item: ActivityItem): string {
  if (item.kind === "resource_done") {
    return MATERIAL[item.resource_kind ?? ""] ?? "Material";
  }
  return ATIVIDADE[item.kind] ?? "Atividade";
}

/** "42 minutos", "1 hora", "2 horas e 5 minutos". */
export function tempoPorExtenso(minutos: number): string {
  if (minutos < 60) return `${minutos} ${minutos === 1 ? "minuto" : "minutos"}`;
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  const h = `${horas} ${horas === 1 ? "hora" : "horas"}`;
  return resto ? `${h} e ${resto} ${resto === 1 ? "minuto" : "minutos"}` : h;
}

interface Alvo {
  dia: DayDetail;
  x: number;
  topo: number;
  base: number;
}

/**
 * O estado do balão de um gráfico.
 *
 * `gatilho(dia)` vai espalhado no elemento do dia; `dica` é renderizado uma
 * vez, em qualquer lugar do gráfico — ele se posiciona pela tela, não pelo pai.
 */
export function useDicaDoDia() {
  const [alvo, setAlvo] = useState<Alvo | null>(null);

  function mostrar(dia: DayDetail, elemento: Element) {
    const caixa = elemento.getBoundingClientRect();
    setAlvo({ dia, x: caixa.left + caixa.width / 2, topo: caixa.top, base: caixa.bottom });
  }

  const gatilho = (dia: DayDetail) => ({
    onMouseEnter: (evento: MouseEvent) => mostrar(dia, evento.currentTarget),
    onMouseLeave: () => setAlvo(null),
    onFocus: (evento: FocusEvent) => mostrar(dia, evento.currentTarget),
    onBlur: () => setAlvo(null),
  });

  // No `<body>`, e não onde o gráfico está. O balão é `position: fixed` para
  // escapar das áreas com rolagem, mas `fixed` só se mede pela janela quando
  // nenhum ancestral tem `transform` — e a tela inteira tem: a animação de
  // entrada (`noc-in … both`) deixa o transform final aplicado. Dentro dela o
  // balão se posicionava a partir do topo da TELA, e aparecia centenas de
  // pixels acima do dia apontado. O portal tira o balão dessa árvore.
  const dica: ReactNode =
    alvo && typeof document !== "undefined"
      ? createPortal(<Balao alvo={alvo} />, document.body)
      : null;
  return { gatilho, dica };
}

/** Largura do balão, para o encaixe na tela saber com o que conta. */
const LARGURA = 300;

function Balao({ alvo }: { alvo: Alvo }) {
  const t = useT();
  const { dia } = alvo;
  // `clientWidth` e não `innerWidth`: o segundo inclui a barra de rolagem
  // vertical, e o balão encostado na borda direita ficava por baixo dela.
  const largura =
    typeof document === "undefined" ? 1024 : document.documentElement.clientWidth;
  // Centralizado sobre o dia, mas sem sair da tela: o último quadrado do mapa
  // fica colado na borda direita, e metade do balão sumiria.
  const x = Math.min(Math.max(alvo.x, LARGURA / 2 + 8), largura - LARGURA / 2 - 8);
  // Acima do dia; embaixo quando não cabe em cima. MEDIDO, e não por uma
  // altura suposta: um dia com cinco materiais de nome longo tem o triplo da
  // altura de um dia com um, e a regra fixa cortava o balão no topo da tela.
  const balao = useRef<HTMLDivElement | null>(null);
  const [embaixo, setEmbaixo] = useState(false);
  useLayoutEffect(() => {
    const altura = balao.current?.offsetHeight ?? 0;
    setEmbaixo(alvo.topo - altura - 16 < 0);
  }, [alvo.topo, dia.date]);
  const titulo = longDate(dia.date);
  const vazio = dia.count === 0 && dia.minutes === 0;

  return (
    <div
      ref={balao}
      role="tooltip"
      className="dica"
      style={{
        left: x,
        top: embaixo ? alvo.base + 8 : alvo.topo - 8,
        transform: embaixo ? "translateX(-50%)" : "translate(-50%, -100%)",
        width: LARGURA,
      }}
    >
      <div className="dica-titulo">{titulo[0].toUpperCase() + titulo.slice(1)}</div>

      {vazio ? (
        <div className="dica-vazio">{t("dica.semEstudo")}</div>
      ) : (
        <>
          {dia.items.length > 0 ? (
            <ul className="dica-lista">
              {dia.items.map((item, posicao) => (
                // O tipo numa linha própria, pequena, acima do nome. Na mesma
                // linha, "Nivelamento de idioma" espremia o título até sobrar
                // "Nivelame…" — e o nome é o que a pessoa procura no balão.
                <li key={`${item.kind}-${posicao}`}>
                  <span className="dica-tipo">{nomeDaAtividade(item)}</span>
                  <span className="dica-linha">
                    <span className="dica-nome">{item.title || nomeDaAtividade(item)}</span>
                    {item.minutes > 0 ? (
                      <span className="dica-min">
                        {item.estimated ? "≈" : ""}
                        {t("painel.minutos", { n: item.minutes })}
                      </span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="dica-vazio">
              {t(dia.count === 1 ? "painel.umaAtividade" : "painel.atividades", { n: dia.count })}
            </div>
          )}
          <div className="dica-total">
            {t("dica.tempoDeEstudo")}{" "}
            <strong>
              {dia.minutes > 0
                ? `${dia.estimated ? "≈ " : ""}${tempoPorExtenso(dia.minutes)}`
                : t("dica.semTempo")}
            </strong>
          </div>
          {/* A estimativa se declara. Tempo de artigo sai do tamanho do
              texto, não de um cronômetro, e apresentar como medido seria
              dizer mais do que o app sabe. */}
          {dia.estimated ? (
            <div className="dica-nota">{t("dica.estimado")}</div>
          ) : null}
        </>
      )}
    </div>
  );
}
