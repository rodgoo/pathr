/**
 * O que aprender a seguir, a partir do objetivo.
 *
 * A aba de competências mostra o catálogo inteiro — 91 tecnologias agrupadas
 * por categoria — e isso responde "o que existe", não "o que eu deveria
 * estudar". Quem escreve "quero ser fullstack Java" sabe o destino e não
 * necessariamente o caminho, e a lacuna entre os dois é onde alguém gasta
 * meses estudando o que não era o mais importante.
 *
 * Cada sugestão vem com o MOTIVO e com o quanto o mercado usa aquilo. O
 * motivo é o que separa uma recomendação de uma lista de nomes: sem ele, a
 * pessoa não tem como discordar — e discordar de uma sugestão ruim é parte de
 * escolher bem.
 *
 * Fica aqui, e não no painel inicial, porque é aqui que a ação tem
 * consequência: adicionar entra nas suas tags, e o roadmap se refaz a partir
 * delas. Um conselho numa tela onde não dá para agir é só barulho.
 */

import { useState } from "react";
import { tags as tagsApi } from "@/api/endpoints";
import type { TagSuggestion, UserTag } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { useT } from "@/lib/i18n";
import { ACC, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

/**
 * Quanto o mercado usa aquilo, e a cor de cada resposta.
 *
 * `aposta` fica em âmbar de propósito: é a única das três que carrega risco, e
 * pintá-la igual às outras esconderia justamente o que a pessoa precisa saber
 * antes de gastar um mês nela.
 */
const DEMANDA: Record<string, { chave: string; cor: string }> = {
  consolidada: { chave: "perfil.sugestoes.demanda.consolidada", cor: C.verde },
  "em alta": { chave: "perfil.sugestoes.demanda.emAlta", cor: ACC },
  aposta: { chave: "perfil.sugestoes.demanda.aposta", cor: C.ambar },
};

/** Nível com que uma sugestão entra: zero, porque é justamente o que falta. */
const NIVEL_INICIAL = 0;

export function SuggestedTags({ onAdicionada }: { onAdicionada: (nova: UserTag) => void }) {
  const t = useT();
  const sugestoes = useQuery(() => tagsApi.suggestions(), []);
  const [ocupada, setOcupada] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  // As que acabaram de entrar somem da lista sem esperar o servidor: o filtro
  // do que a pessoa já tem acontece na próxima leitura, e até lá a sugestão
  // ficaria na tela como se o clique não tivesse funcionado.
  const [adicionadas, setAdicionadas] = useState<string[]>([]);

  // Enquanto carrega, nada: é um painel de apoio, e um esqueleto aqui
  // competiria com o catálogo, que é o assunto da aba.
  if (sugestoes.loading || sugestoes.error) return null;

  const dados = sugestoes.data;
  if (!dados || !dados.objetivo || dados.sugestoes.length === 0) return null;

  // Idioma se trata no módulo de Idiomas, não como skill (ver SkillsTab).
  const visiveis = dados.sugestoes.filter((item) => !adicionadas.includes(item.name) && item.category !== "idioma");
  if (visiveis.length === 0) return null;

  async function adicionar(sugestao: TagSuggestion) {
    setOcupada(sugestao.name);
    setErro(null);
    try {
      const criada = await tagsApi.add({
        name: sugestao.name,
        category: sugestao.category,
        proficiency: NIVEL_INICIAL,
        // Entra como meta: é o que faz o roadmap passar a cobrir o assunto.
        is_target: true,
      });
      setAdicionadas((atual) => [...atual, sugestao.name]);
      onAdicionada(criada);
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : t("perfil.sugestoes.erroAdicionar"));
    } finally {
      setOcupada(null);
    }
  }

  return (
    <Panel pad={16.8}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2 }}>
        <Kicker>{t("perfil.sugestoes.titulo")}</Kicker>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint, paddingInline: 0 }}
          onClick={sugestoes.reload}
        >
          {t("perfil.sugestoes.rever")}
        </button>
      </div>
      <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "5.6px 0 14px", maxWidth: "72ch" }}>
        {t("perfil.sugestoes.aPartirDe", { objetivo: dados.objetivo })}
      </p>

      {erro ? <ErrorState message={erro} /> : null}

      <div style={{ display: "flex", flexDirection: "column", gap: 8.4 }}>
        {visiveis.map((sugestao) => {
          const demanda = DEMANDA[sugestao.demand] ?? DEMANDA.consolidada;
          return (
            <div
              key={sugestao.name}
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "flex-start",
                gap: 11.2,
                padding: "11.2px 14px",
                borderRadius: 8,
                border: `1px solid ${HAIRLINE}`,
              }}
            >
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8.4, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 14, color: TEXT.strong }}>{sugestao.name}</span>
                  <span style={{ fontSize: 11, color: demanda.cor }}>{t(demanda.chave)}</span>
                  <span style={{ fontSize: 11, color: TEXT.faint }}>{sugestao.category}</span>
                </div>
                {sugestao.reason ? (
                  <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "4px 0 0", lineHeight: 1.5 }}>
                    {sugestao.reason}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: 12.5 }}
                disabled={ocupada === sugestao.name}
                onClick={() => void adicionar(sugestao)}
              >
                <Icon name="plus" size={15} />
                {ocupada === sugestao.name ? t("perfil.sugestoes.adicionando") : t("perfil.sugestoes.adicionar")}
              </button>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
