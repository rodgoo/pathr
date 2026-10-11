/**
 * /newsletter — o arquivo das edições que saíram para o e-mail do admin.
 *
 * O e-mail some na caixa de entrada; isto não. Lê `GET /newsletter`, que só
 * o super admin alcança (404 para as outras contas), e mostra cada edição
 * como chegou: agrupada por tecnologia, com a foto e o link de cada matéria.
 * Existe fora das Configurações porque é leitura, e quem lê não quer a tela
 * de ajustes no caminho.
 *
 * O link de cada matéria e a foto passam por `linkExterno` (em
 * NewsletterCard): o endereço veio de uma busca na web, e só http/https vira
 * `href`.
 */

import { newsletter, type EdicaoNewsletter, type MateriaNewsletter } from "@/api/endpoints";
import { useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { Icon } from "@/components/ui/icons";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { MateriaCard } from "@/components/admin/NewsletterCard";
import "@/styles/newsletter.css";

interface Props {
  onNavigate: (path: string) => void;
}

function partesDaData(iso: string): { dia: string; mes: string } {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return { dia: "·", mes: "" };
  return {
    dia: String(d.getDate()).padStart(2, "0"),
    mes: d.toLocaleDateString(undefined, { month: "short" }).replace(".", ""),
  };
}

function agrupar(itens: MateriaNewsletter[]): [string, MateriaNewsletter[]][] {
  const grupos = new Map<string, MateriaNewsletter[]>();
  for (const item of itens) grupos.set(item.topico, [...(grupos.get(item.topico) ?? []), item]);
  return [...grupos.entries()];
}

function Edicao({ edicao }: { edicao: EdicaoNewsletter }) {
  const t = useT();
  const { dia, mes } = partesDaData(edicao.enviada_em);
  return (
    <article className="nl-card nl-edition" aria-label={edicao.assunto}>
      <header className="nl-edition-head">
        <span className="nl-date" aria-hidden="true">
          <b>{dia}</b>
          <span>{mes}</span>
        </span>
        <div style={{ minWidth: 0 }}>
          <h2 className="nl-edition-title">{edicao.assunto}</h2>
          <p className="nl-edition-meta">
            {edicao.quantidade === 1
              ? t("newsletter.materias.uma")
              : t("newsletter.materias.varias", { n: edicao.quantidade })}{" "}
            · {t(`newsletter.historico.${edicao.tipo}`)}
          </p>
        </div>
      </header>

      {agrupar(edicao.itens).map(([tema, itens]) => (
        <section key={tema} className="nl-tech" aria-label={tema}>
          <h3 className="nl-tech-head">
            {tema}
            <span className="nl-tech-count">
              {itens.length === 1
                ? t("newsletter.materias.uma")
                : t("newsletter.materias.varias", { n: itens.length })}
            </span>
          </h3>
          <ul className="nl-grid">
            {itens.map((item) => (
              <MateriaCard key={item.url} item={item} />
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}

export function NewsletterPage({ onNavigate }: Props) {
  const t = useT();
  const edicoes = useQuery(() => newsletter.edicoes(), []);
  const lista = edicoes.data?.edicoes ?? [];

  return (
    <main className="nl-page">
      <header className="nl-page-head">
        <span className="nl-hero-icon">
          <Icon name="mail" size={22} />
        </span>
        <div style={{ minWidth: 0 }}>
          <p className="nl-kicker">{t("newsletter.kicker")}</p>
          <h1>{t("newsletter.pagina.titulo")}</h1>
        </div>
        <div className="nl-page-actions">
          <button type="button" className="btn btn-secondary" onClick={() => onNavigate("/")}>
            <Icon name="arrowLeft" size={15} />
            {t("newsletter.pagina.voltar")}
          </button>
        </div>
      </header>
      <p className="nl-hero-sub" style={{ marginTop: -8 }}>
        {t("newsletter.pagina.sub")}
      </p>

      {edicoes.loading && !edicoes.data ? <Loading label={t("newsletter.pagina.carregando")} /> : null}
      {edicoes.error ? <ErrorState message={edicoes.error} onRetry={edicoes.reload} /> : null}
      {edicoes.data && lista.length === 0 ? (
        <EmptyState
          title={t("newsletter.pagina.vazioTitulo")}
          description={t("newsletter.pagina.vazioTexto")}
        />
      ) : null}
      {lista.map((edicao) => (
        <Edicao key={edicao.id} edicao={edicao} />
      ))}
    </main>
  );
}
