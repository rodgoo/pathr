/**
 * Amigos: quem você tem, quem te chamou, e quem talvez valha conhecer.
 *
 * A ordem da tela é a ordem da urgência. Convite recebido vem primeiro —
 * alguém está esperando uma resposta. Depois a busca (quem já sabe quem
 * procura), as sugestões (quem não sabe) e, por último, os amigos e os
 * convites que você mandou.
 *
 * As sugestões vêm do servidor já ordenadas por proximidade — mesma cidade,
 * depois mesma UF — e desempatadas pelo que as duas pessoas têm em comum.
 */

import { useEffect, useState, type ReactNode } from "react";
import { social } from "@/api/endpoints";
import type { PessoaCartao } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { TEXT } from "@/lib/tokens";
import { CartaoPessoa } from "@/components/social/CartaoPessoa";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, SCREEN_IN } from "@/components/ui/primitives";

const ESPERA_BUSCA_MS = 350;

function Grade({ pessoas, onMudou }: { pessoas: PessoaCartao[]; onMudou: () => void }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(250px,1fr))", gap: 11.2 }}>
      {pessoas.map((pessoa) => (
        <CartaoPessoa key={pessoa.username} pessoa={pessoa} onMudou={onMudou} />
      ))}
    </div>
  );
}

function Secao({ titulo, contagem, children }: { titulo: string; contagem?: number; children: ReactNode }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8.4 }}>
        <Kicker>{titulo}</Kicker>
        {contagem !== undefined ? <span style={{ fontSize: 11.5, color: TEXT.faint }}>{contagem}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function AmigosPage() {
  const t = useT();
  const { user } = useAuth();
  const amizades = useQuery(() => social.amigos(), []);
  const sugestoes = useQuery(() => social.sugestoes(), []);

  const [termo, setTermo] = useState("");
  const [achados, setAchados] = useState<PessoaCartao[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [erroBusca, setErroBusca] = useState<string | null>(null);
  const [versaoBusca, setVersaoBusca] = useState(0);

  const limpo = termo.trim().replace(/^@+/, "");

  useEffect(() => {
    if (limpo.length < 2) {
      setAchados(null);
      setErroBusca(null);
      return undefined;
    }
    let vivo = true;
    setBuscando(true);
    setErroBusca(null);
    const timer = window.setTimeout(() => {
      social
        .buscar(limpo)
        .then((lista) => {
          if (vivo) setAchados(lista);
        })
        .catch((caught) => {
          if (vivo) setErroBusca(caught instanceof Error ? caught.message : t("amigos.erroBuscar"));
        })
        .finally(() => {
          if (vivo) setBuscando(false);
        });
    }, ESPERA_BUSCA_MS);
    return () => {
      vivo = false;
      window.clearTimeout(timer);
    };
  }, [limpo, versaoBusca]);

  /** Uma relação mudou: tudo que mostra relação precisa refletir. */
  function recarregar() {
    amizades.reload();
    sugestoes.reload();
    if (limpo.length >= 2) setVersaoBusca((v) => v + 1);
  }

  const dados = amizades.data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22.4, ...SCREEN_IN }}>
      <header>
        <div style={{ fontSize: 12.5, color: TEXT.muted }}>
          {t("amigos.voceEh")} <strong style={{ color: TEXT.strong, fontWeight: 500 }}>@{user?.username}</strong>
        </div>
        <h1 style={{ fontSize: 28, margin: 0 }}>{t("amigos.titulo")}</h1>
      </header>

      {dados && dados.recebidos.length > 0 ? (
        <Secao titulo={t("amigos.convitesRecebidos")} contagem={dados.recebidos.length}>
          <Grade pessoas={dados.recebidos} onMudou={recarregar} />
        </Secao>
      ) : null}

      <section>
        <div className="field" style={{ margin: 0, maxWidth: 520 }}>
          <label htmlFor="amigos-busca">{t("amigos.procurar")}</label>
          <input
            id="amigos-busca"
            className="input"
            type="search"
            placeholder={t("amigos.buscaPlaceholder")}
            autoCapitalize="none"
            spellCheck={false}
            value={termo}
            onChange={(evento) => setTermo(evento.target.value)}
          />
        </div>
        {limpo.length >= 2 ? (
          <div style={{ marginTop: 14 }}>
            {buscando && !achados ? <Loading label={t("amigos.procurando")} /> : null}
            {erroBusca ? <ErrorState message={erroBusca} /> : null}
            {achados && achados.length === 0 && !buscando ? (
              <p style={{ fontSize: 13, color: TEXT.muted, margin: 0 }}>
                {t("amigos.nadaEncontrado")}
              </p>
            ) : null}
            {achados && achados.length > 0 ? <Grade pessoas={achados} onMudou={recarregar} /> : null}
          </div>
        ) : null}
      </section>

      {limpo.length < 2 ? (
        <Secao titulo={t("amigos.sugestoes")}>
          {sugestoes.loading && !sugestoes.data ? <Loading label={t("amigos.procurandoPerto")} /> : null}
          {sugestoes.error ? <ErrorState message={sugestoes.error} onRetry={sugestoes.reload} /> : null}
          {sugestoes.data && sugestoes.data.length === 0 ? (
            <p style={{ fontSize: 13, color: TEXT.muted, margin: 0 }}>
              {t("amigos.semSugestoes")}
            </p>
          ) : null}
          {sugestoes.data && sugestoes.data.length > 0 ? (
            <Grade pessoas={sugestoes.data} onMudou={recarregar} />
          ) : null}
        </Secao>
      ) : null}

      {amizades.loading && !dados ? <Loading label={t("amigos.carregandoAmigos")} /> : null}
      {amizades.error ? <ErrorState message={amizades.error} onRetry={amizades.reload} /> : null}

      {dados ? (
        <Secao titulo={t("amigos.seusAmigos")} contagem={dados.amigos.length}>
          {dados.amigos.length === 0 ? (
            <EmptyState
              title={t("amigos.nenhumAmigo")}
              description={t("amigos.nenhumAmigoDesc")}
            />
          ) : (
            <Grade pessoas={dados.amigos} onMudou={recarregar} />
          )}
        </Secao>
      ) : null}

      {dados && dados.enviados.length > 0 ? (
        <Secao titulo={t("amigos.convitesEnviados")} contagem={dados.enviados.length}>
          <Grade pessoas={dados.enviados} onMudou={recarregar} />
        </Secao>
      ) : null}
    </div>
  );
}
