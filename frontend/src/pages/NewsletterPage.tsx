/**
 * /newsletter — o arquivo das edições que saíram para o e-mail do admin.
 *
 * O e-mail some na caixa de entrada; isto não. Lê `GET /newsletter`, que só
 * o super admin alcança (404 para as outras contas), e mostra cada edição
 * agrupada por tecnologia, como chegou. A página existe fora das Configurações
 * porque é leitura, e quem lê não quer a tela de ajustes no caminho.
 *
 * O link de cada matéria passa por `linkExterno`: o endereço veio de uma
 * busca na web e só http/https vira `href`.
 */

import { newsletter, type EdicaoNewsletter, type MateriaNewsletter } from "@/api/endpoints";
import { useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { linkExterno } from "@/lib/linkExterno";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { ACC, ACC4, TEXT } from "@/lib/tokens";

interface Props {
  onNavigate: (path: string) => void;
}

function dataLegivel(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

function agrupar(itens: MateriaNewsletter[]): [string, MateriaNewsletter[]][] {
  const grupos = new Map<string, MateriaNewsletter[]>();
  for (const item of itens) grupos.set(item.topico, [...(grupos.get(item.topico) ?? []), item]);
  return [...grupos.entries()];
}

function Edicao({ edicao }: { edicao: EdicaoNewsletter }) {
  const t = useT();
  return (
    <Panel pad={16.8} style={{ marginBottom: 14 }}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 4 }}>
        {dataLegivel(edicao.enviada_em)} · {t(`newsletter.tipo.${edicao.tipo}`)} ·{" "}
        {t("newsletter.materias", { n: edicao.quantidade })}
      </Kicker>
      <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>{edicao.assunto}</h2>
      {agrupar(edicao.itens).map(([tema, itens]) => (
        <section key={tema} style={{ marginTop: 14 }}>
          <h3 style={{ margin: 0, fontSize: 15, color: TEXT.full }}>{tema}</h3>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {itens.map((item) => {
              const via =
                item.termo && item.termo.toLowerCase() !== item.topico.toLowerCase() ? item.termo : "";
              const foto = linkExterno(item.imagem)?.startsWith("https://") ? linkExterno(item.imagem) : undefined;
              return (
                <li key={item.url} style={{ padding: "10px 0", borderTop: "1px solid rgba(233,233,237,.08)" }}>
                  {foto ? (
                    <img
                      src={foto}
                      alt=""
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                      style={{
                        display: "block",
                        width: "100%",
                        maxWidth: 480,
                        maxHeight: 240,
                        objectFit: "cover",
                        borderRadius: 8,
                        marginBottom: 8,
                        border: "1px solid rgba(233,233,237,.12)",
                      }}
                    />
                  ) : null}
                  <div style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: ACC4 }}>
                    {item.topico} + {t(`newsletter.angulo.${item.categoria}`)}
                    {via ? <span style={{ color: TEXT.faint }}> · {t("newsletter.via", { termo: via })}</span> : null}
                  </div>
                  <a
                    href={linkExterno(item.url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ display: "block", fontSize: 15, color: TEXT.full, textDecoration: "none", marginTop: 2 }}
                  >
                    {item.titulo}
                  </a>
                  {item.resumo ? (
                    <p style={{ margin: "4px 0 0", fontSize: 13, color: TEXT.muted, lineHeight: 1.55 }}>
                      {item.resumo}
                    </p>
                  ) : null}
                  <div style={{ fontSize: 11.5, color: TEXT.faint, marginTop: 4 }}>
                    {[item.fonte, item.publicado_em ? dataLegivel(item.publicado_em) : ""].filter(Boolean).join(" · ")}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </Panel>
  );
}

export function NewsletterPage({ onNavigate }: Props) {
  const t = useT();
  const edicoes = useQuery(() => newsletter.edicoes(), []);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "28px 16px 56px", ...SCREEN_IN }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "baseline", marginBottom: 6 }}>
        <h1 style={{ fontSize: 28, margin: 0 }}>{t("newsletter.pagina.titulo")}</h1>
        <button type="button" className="btn btn-ghost" onClick={() => onNavigate("/")}>
          {t("newsletter.pagina.voltar")}
        </button>
      </div>
      <p style={{ margin: "0 0 18px", fontSize: 13.5, color: TEXT.muted, maxWidth: "62ch" }}>
        {t("newsletter.pagina.subtitulo")}
      </p>

      {edicoes.loading ? <Loading label={t("newsletter.pagina.carregando")} /> : null}
      {edicoes.error ? <ErrorState message={edicoes.error} onRetry={edicoes.reload} /> : null}
      {edicoes.data && edicoes.data.edicoes.length === 0 ? (
        <p style={{ fontSize: 13.5, color: TEXT.muted }}>
          {t("newsletter.pagina.vazio")}{" "}
          <a href="/" style={{ color: ACC }}>
            {t("newsletter.pagina.configurar")}
          </a>
        </p>
      ) : null}
      {edicoes.data?.edicoes.map((edicao) => <Edicao key={edicao.id} edicao={edicao} />)}
    </main>
  );
}
