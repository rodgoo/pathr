/**
 * Peças visuais da newsletter que a tela de configuração e a página
 * `/newsletter` dividem: o cartão da matéria (com foto) e o mapa de ângulos.
 *
 * ## Foto
 *
 * Só `https`, passando por `linkExterno` (o endereço veio de uma busca na
 * web). Foto que não abre — ou matéria que nunca teve uma — cai num fundo com
 * o ícone do ângulo, na cor dele: o cartão nunca fica com um buraco. A imagem
 * leva `referrerPolicy="no-referrer"`, para o site de origem não saber de
 * qual tela o pedido veio.
 *
 * ## Ângulo, cor e ícone
 *
 * Cada ângulo tem uma cor e um ícone fixos, usados em todo lugar (etiqueta,
 * cartão de escolha, e-mail): a pessoa aprende que verde é emprego uma vez.
 */

import { useState, type CSSProperties } from "react";
import type { AnguloNewsletter, MateriaNewsletter } from "@/api/endpoints";
import { Icon, type IconName } from "@/components/ui/icons";
import { useT } from "@/lib/i18n";
import { linkExterno } from "@/lib/linkExterno";
import { ACC4, C } from "@/lib/tokens";
import "@/styles/newsletter.css";

export const ANGULO: Record<AnguloNewsletter, { icon: IconName; tone: string }> = {
  noticias: { icon: "article", tone: ACC4 },
  novidades: { icon: "flame", tone: C.azul },
  trabalhos: { icon: "suitcase", tone: C.verde },
  polemicas: { icon: "chat", tone: C.ambar },
};

export function estiloDoAngulo(angulo: AnguloNewsletter): CSSProperties {
  return { ["--tone" as string]: ANGULO[angulo]?.tone ?? ACC4 };
}

/** "09 out" — o dia da matéria, sem o ano que todo mundo sabe. */
export function dataCurta(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
}

/** A foto utilizável: https, ou nada. */
export function fotoDe(item: Pick<MateriaNewsletter, "imagem">): string | undefined {
  const url = linkExterno(item.imagem);
  return url?.startsWith("https://") ? url : undefined;
}

interface MateriaCardProps {
  item: MateriaNewsletter;
  /** Quando presente, o cartão ganha a marca de seleção no canto da foto. */
  selecionada?: boolean;
  onAlternar?: () => void;
}

export function MateriaCard({ item, selecionada, onAlternar }: MateriaCardProps) {
  const t = useT();
  const [fotoFalhou, setFotoFalhou] = useState(false);
  const foto = fotoDe(item);
  const href = linkExterno(item.url);
  const angulo = ANGULO[item.categoria] ? item.categoria : "noticias";
  const meta = ANGULO[angulo];
  const via = item.termo && item.termo.toLowerCase() !== item.topico.toLowerCase() ? item.termo : "";
  const selecionavel = typeof onAlternar === "function";
  const data = dataCurta(item.publicado_em);

  return (
    <li
      className="nl-news"
      style={estiloDoAngulo(angulo)}
      data-selected={selecionavel ? String(Boolean(selecionada)) : undefined}
    >
      <a
        className="nl-news-media"
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        tabIndex={-1}
        aria-hidden="true"
      >
        {foto && !fotoFalhou ? (
          <img
            src={foto}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setFotoFalhou(true)}
          />
        ) : (
          <span className="nl-news-fallback">
            <Icon name={meta.icon} size={34} />
          </span>
        )}
        <span className="nl-pill nl-news-pill">
          <Icon name={meta.icon} size={13} />
          {item.topico} + {t(`newsletter.angulo.${angulo}.nome`)}
        </span>
      </a>

      {selecionavel ? (
        <button
          type="button"
          className="nl-news-check"
          aria-pressed={Boolean(selecionada)}
          aria-label={t("newsletter.resultados.selecionar", { titulo: item.titulo })}
          onClick={onAlternar}
        >
          <Icon name="check" size={15} />
        </button>
      ) : null}

      <div className="nl-news-body">
        <h4 className="nl-news-title">
          <a href={href} target="_blank" rel="noopener noreferrer">
            {item.titulo}
          </a>
        </h4>
        {item.resumo ? <p className="nl-news-sum">{item.resumo}</p> : null}
        <div className="nl-news-meta">
          {item.fonte ? (
            <span>
              <Icon name="globe" size={12} />
              {item.fonte}
            </span>
          ) : null}
          {data ? (
            <span>
              <Icon name="clock" size={12} />
              {data}
            </span>
          ) : null}
          {via ? (
            <span>
              <Icon name="arrowRight" size={12} />
              {t("newsletter.via", { termo: via })}
            </span>
          ) : null}
        </div>
      </div>
    </li>
  );
}
