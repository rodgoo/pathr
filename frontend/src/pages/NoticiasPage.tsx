/**
 * Notícias: eventos e anúncios de tecnologia perto da sua cidade.
 *
 * A busca (Tavily/Brave, várias fontes) e a organização por IA acontecem no
 * servidor, na primeira vez que a tela é aberta depois de um tempo sem
 * ninguém pedir aquela região (services/noticias.py). Aqui só se mostra o
 * resultado: data, gratuito ou pago, prazo de inscrição — e, quando o texto
 * de origem não trazia prazo nenhum, a frase fixa que o servidor manda em
 * `inscricao_texto`, nunca inventada na tela.
 */

import { useEffect, useState } from "react";
import { noticias as noticiasApi, profile as profileApi } from "@/api/endpoints";
import type { EventoDeNoticia } from "@/api/types";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { useT } from "@/lib/i18n";
import { Icon } from "@/components/ui/icons";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";

export function NoticiasPage() {
  const t = useT();
  const perfil = useQuery(() => profileApi.get(), []);
  const eventos = useQuery(() => noticiasApi.list(), []);
  const lista = eventos.data?.eventos ?? [];
  const atualizando = eventos.data?.atualizando ?? false;

  // O servidor saiu para procurar AGORA, em segundo plano. A tela já mostrou o
  // que havia; daqui a pouco pede de novo, duas vezes, e para. Antes isto era
  // um "Buscando eventos…" que prendia a tela enquanto o servidor lia dezenas
  // de páginas — e que às vezes nunca terminava.
  useEffect(() => {
    if (!atualizando) return;
    let tentativas = 0;
    const relogio = setInterval(() => {
      tentativas += 1;
      eventos.reload();
      if (tentativas >= 2) clearInterval(relogio);
    }, 20_000);
    return () => clearInterval(relogio);
  }, [atualizando, eventos]);

  return (
    <div style={{ ...SCREEN_IN, display: "flex", flexDirection: "column", gap: 16.8 }}>
      <header>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>{t("noticias.kicker")}</Kicker>
        <h1 style={{ fontSize: 23, fontWeight: 500, margin: 0 }}>{t("noticias.titulo")}</h1>
        <p style={{ fontSize: 13, color: TEXT.muted, margin: "8.4px 0 0", maxWidth: "72ch" }}>
          {perfil.data?.city
            ? t("noticias.descricaoComCidade", {
                cidade: `${perfil.data.city}${perfil.data.state ? ` - ${perfil.data.state}` : ""}`,
              })
            : t("noticias.descricaoSemCidade")}
        </p>
      </header>

      {eventos.error ? <ErrorState message={eventos.error} onRetry={eventos.reload} /> : null}
      {eventos.loading && !eventos.data ? <Loading label={t("noticias.carregando")} /> : null}

      {atualizando ? (
        <Panel pad={11.2}>
          <p style={{ margin: 0, fontSize: 12.5, color: TEXT.muted }}>
            <Icon name="refresh" size={13} style={{ verticalAlign: "-2px", marginRight: 6 }} aria-hidden />
            {t("noticias.procurando")}
          </p>
        </Panel>
      ) : null}

      {!eventos.loading && lista.length === 0 && !eventos.error ? (
        <EmptyState
          title={t("noticias.vazio.titulo")}
          description={
            perfil.data?.city ? t("noticias.vazio.comCidade") : t("noticias.vazio.semCidade")
          }
        />
      ) : null}

      {lista.map((evento) => (
        <EventoCard
          key={evento.id}
          evento={evento}
          onMudou={(atualizado) =>
            eventos.set((atuais) => ({
              ...atuais,
              eventos: atuais.eventos.map((item) => (item.id === atualizado.id ? atualizado : item)),
            }))
          }
        />
      ))}
    </div>
  );
}

function formatarData(iso: string | null): string {
  if (!iso) return "";
  const [ano, mes, dia] = iso.split("-").map(Number);
  return new Date(ano, (mes ?? 1) - 1, dia ?? 1).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function EventoCard({
  evento,
  onMudou,
}: {
  evento: EventoDeNoticia;
  onMudou: (atualizado: EventoDeNoticia) => void;
}) {
  const t = useT();
  const [erro, setErro] = useState<string | null>(null);
  const [baixando, setBaixando] = useState(false);
  const confirmar = useMutation(() => noticiasApi.confirmar(evento.id));
  const cancelar = useMutation(() => noticiasApi.cancelar(evento.id));

  async function alternarPresenca() {
    setErro(null);
    const resposta = evento.eu_vou ? await cancelar.run() : await confirmar.run();
    if (resposta === null && (confirmar.error || cancelar.error)) {
      setErro(confirmar.error || cancelar.error);
      return;
    }
    onMudou({ ...evento, eu_vou: !evento.eu_vou });
  }

  async function baixarIcs() {
    setErro(null);
    setBaixando(true);
    try {
      const blob = (await noticiasApi.ics(evento.id)) as Blob;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${evento.titulo}.ics`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setErro(t("noticias.erroCalendario"));
    } finally {
      setBaixando(false);
    }
  }

  /**
   * O endereço que abre o evento já preenchido no Google Agenda.
   *
   * No computador, baixar um `.ics` só ajuda quem tem Outlook ou Calendário
   * instalado e associado ao formato — para quem vive de agenda no navegador,
   * o arquivo cai na pasta de downloads e não acontece nada. O link abre a
   * agenda na hora; o `.ics` continua aqui ao lado para Outlook, Apple e
   * celular.
   *
   * As datas vão no formato do Google (AAAAMMDD), e o fim é EXCLUSIVO: um
   * evento de um dia termina no dia seguinte, senão a agenda mostra um dia a
   * menos.
   */
  function noGoogleAgenda(): string | null {
    // Sem data não há o que agendar — e, principalmente, não se pode deixar um
    // campo ausente derrubar a tela: isto roda DENTRO do render, e um throw
    // aqui apaga a aba inteira ("Alguma coisa quebrou ao desenhar o conteúdo")
    // por causa de um evento só.
    if (!evento.data_inicio) return null;
    const soDigitos = (iso: string) => iso.replace(/-/g, "");
    const diaSeguinte = (iso: string) => {
      const d = new Date(`${iso}T12:00:00`);
      d.setDate(d.getDate() + 1);
      return soDigitos(d.toISOString().slice(0, 10));
    };
    const inicio = soDigitos(evento.data_inicio);
    const fim = diaSeguinte(evento.data_fim || evento.data_inicio);
    const onde = [evento.local, evento.cidade, evento.estado].filter(Boolean).join(", ");
    const parametros = new URLSearchParams({
      action: "TEMPLATE",
      text: evento.titulo,
      dates: `${inicio}/${fim}`,
      details: `${evento.resumo || ""}

${evento.url_ingresso}`.trim(),
      location: onde,
    });
    return `https://calendar.google.com/calendar/render?${parametros.toString()}`;
  }

  const agenda = noGoogleAgenda();
  const periodo =
    evento.data_fim && evento.data_fim !== evento.data_inicio
      ? `${formatarData(evento.data_inicio)} – ${formatarData(evento.data_fim)}`
      : formatarData(evento.data_inicio);

  return (
    <Panel pad={16.8}>
      <div style={{ display: "flex", gap: 11.2, alignItems: "flex-start", flexWrap: "wrap" }}>
        {evento.imagem ? (
          // `onError` some com a imagem em vez de deixar o ícone de quebrado:
          // o endereço vem do site do evento e pode sair do ar a qualquer hora.
          <img
            src={evento.imagem}
            alt=""
            loading="lazy"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
            style={{
              width: 96,
              height: 96,
              objectFit: "cover",
              borderRadius: 10,
              border: `1px solid ${HAIRLINE}`,
              background: "rgba(233,233,237,.04)",
            }}
          />
        ) : null}
        <div style={{ flex: 1, minWidth: 240 }}>
          <h2 style={{ fontSize: 16, fontWeight: 500, margin: 0, color: TEXT.full }}>{evento.titulo}</h2>
          <p style={{ margin: "4px 0 0", fontSize: 12.5, color: TEXT.muted }}>
            {periodo}
            {evento.local ? ` · ${evento.local}` : ""}
            {evento.cidade ? ` · ${evento.cidade}${evento.estado ? ` - ${evento.estado}` : ""}` : ""}
          </p>
        </div>
        {evento.gratuito === true ? (
          <span className="tag" style={{ color: C.verde }}>
            {t("noticias.gratuito")}
          </span>
        ) : evento.gratuito === false ? (
          <span className="tag tag-outline" style={{ color: C.ambar }}>
            {t("noticias.pago")}
            {evento.preco_info ? ` · ${evento.preco_info}` : ""}
          </span>
        ) : null}
      </div>

      {evento.resumo ? (
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "11.2px 0 0", lineHeight: 1.55 }}>{evento.resumo}</p>
      ) : null}

      <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "8.4px 0 0" }}>
        <Icon name="clock" size={12} style={{ verticalAlign: "-1.5px", marginRight: 4 }} aria-hidden />
        {evento.inscricao_texto
          ? evento.inscricao_texto
          : t("noticias.inscricao", {
              inicio: formatarData(evento.inscricao_inicio),
              fim: formatarData(evento.inscricao_fim),
            })}
      </p>

      <div style={{ display: "flex", gap: 8.4, flexWrap: "wrap", marginTop: 14 }}>
        <a
          className="btn btn-primary"
          href={evento.url_ingresso}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none" }}
        >
          <Icon name="externalLink" size={15} />
          {t("noticias.abrirIngresso")}
        </a>

        {agenda ? (
        <a
          className="btn btn-secondary"
          href={agenda}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none" }}
        >
          {/* Não há ícone de calendário no conjunto; o relógio é o mais
              próximo e já marca a linha de prazo logo acima. */}
          <Icon name="clock" size={15} />
          {t("noticias.googleAgenda")}
        </a>
        ) : null}

        <button type="button" className="btn btn-ghost" disabled={baixando} onClick={() => void baixarIcs()}>
          <Icon name="download" size={15} />
          {baixando ? t("noticias.baixando") : t("noticias.baixarIcs")}
        </button>

        <button
          type="button"
          className={evento.eu_vou ? "btn btn-primary" : "btn btn-ghost"}
          aria-pressed={evento.eu_vou}
          disabled={confirmar.pending || cancelar.pending}
          onClick={() => void alternarPresenca()}
          style={evento.eu_vou ? { marginLeft: "auto" } : { marginLeft: "auto", color: ACC4 }}
        >
          <Icon name="check" size={15} />
          {evento.eu_vou ? t("noticias.euVou.confirmado") : t("noticias.euVou.botao")}
        </button>
      </div>

      {erro ? <ErrorState message={erro} /> : null}
      {evento.eu_vou ? (
        <p style={{ fontSize: 11, color: TEXT.faint, margin: "8.4px 0 0", borderTop: `1px solid ${HAIRLINE}`, paddingTop: 8.4 }}>
          {t("noticias.euVou.explicacao")}
        </p>
      ) : null}
    </Panel>
  );
}
