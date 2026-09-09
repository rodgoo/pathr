/**
 * Os idiomas que a pessoa estuda, cada um com a própria régua.
 *
 * O módulo nasceu inglês-só. A tela agora lista os nove idiomas do catálogo e
 * cada um se liga por conta própria — o banco passou a ter uma linha por
 * (usuário, idioma), então dois idiomas ligados são dois níveis medidos, dois
 * baralhos de vocabulário e duas metas.
 *
 * A escolha da PROVA é o que dá sentido ao nível. O app mede sempre em CEFR —
 * aplicar IELTS ou TOEFL de verdade exigiria banco de itens calibrado por
 * examinador, que nenhum LLM substitui — e mostra o resultado na régua que a
 * pessoa usa. Quem estuda para o IELTS quer ler "7.0", não "C1", e os dois são
 * o mesmo ponto. A tela diz isso em vez de esconder.
 *
 * A tabela de equivalência vive só no servidor. Copiá-la para cá faria as duas
 * divergirem na primeira correção feita de um lado só, e a meta passaria a
 * apontar para um nível diferente do que a tela mostra.
 */

import { useEffect, useState } from "react";
import { languages as languagesApi } from "@/api/endpoints";
import type { LanguageCatalogEntry, LanguageProfile } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

const METAS_DIARIAS = [10, 15, 30];

export function LanguageSettings() {
  const catalogo = useQuery(() => languagesApi.catalog(), []);
  const meus = useQuery(() => languagesApi.profiles(), []);
  const [perfis, setPerfis] = useState<LanguageProfile[]>([]);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (meus.data) setPerfis(meus.data);
  }, [meus.data]);

  if (catalogo.loading || meus.loading) return <Loading />;
  if (catalogo.error) return <ErrorState message={catalogo.error} onRetry={catalogo.reload} />;
  if (meus.error) return <ErrorState message={meus.error} onRetry={meus.reload} />;

  const porIdioma = new Map(perfis.map((perfil) => [perfil.language, perfil]));

  async function salvar(codigo: string, mudanca: Partial<LanguageProfile>) {
    setOcupado(codigo);
    setErro(null);
    try {
      const atualizado = await languagesApi.update(codigo, mudanca);
      setPerfis((atual) => [
        ...atual.filter((perfil) => perfil.language !== codigo),
        atualizado,
      ]);
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar.");
    } finally {
      setOcupado(null);
    }
  }

  const ligados = perfis.filter((perfil) => perfil.enabled).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2 }}>
          <Kicker>Idiomas</Kicker>
          <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
            {ligados === 0
              ? "nenhum no plano"
              : `${ligados} ${ligados === 1 ? "idioma" : "idiomas"} no plano`}
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "5.6px 0 0", maxWidth: "74ch" }}>
          Ligue os idiomas que fazem parte do seu plano e escolha em que escala quer acompanhar o
          nível. O nivelamento mede sempre no CEFR e converte para a prova que você escolher —{" "}
          <strong style={{ color: TEXT.strong, fontWeight: 500 }}>
            o app não aplica IELTS, TOEFL ou JLPT
          </strong>
          , ele estima onde você está e mostra na régua que você usa.
        </p>
      </Panel>

      {erro ? <ErrorState message={erro} /> : null}

      {(catalogo.data ?? []).map((idioma) => (
        <CartaoDeIdioma
          key={idioma.codigo}
          idioma={idioma}
          perfil={porIdioma.get(idioma.codigo)}
          ocupado={ocupado === idioma.codigo}
          onSalvar={(mudanca) => void salvar(idioma.codigo, mudanca)}
        />
      ))}
    </div>
  );
}

function CartaoDeIdioma({
  idioma,
  perfil,
  ocupado,
  onSalvar,
}: {
  idioma: LanguageCatalogEntry;
  perfil?: LanguageProfile;
  ocupado: boolean;
  onSalvar: (mudanca: Partial<LanguageProfile>) => void;
}) {
  const ligado = Boolean(perfil?.enabled);
  const exameAtual =
    idioma.exames.find((exame) => exame.id === (perfil?.exam ?? "cefr")) ?? idioma.exames[0];

  return (
    <Panel pad={16.8}>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 11.2,
          cursor: "pointer",
          opacity: ocupado ? 0.6 : 1,
        }}
      >
        <input
          type="checkbox"
          checked={ligado}
          disabled={ocupado}
          onChange={() => onSalvar({ enabled: !ligado })}
          style={{ flex: "none", accentColor: "#9184d9" }}
        />
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ fontSize: 15, color: ligado ? TEXT.full : TEXT.muted }}>
            {idioma.nome}
          </span>
          <span style={{ fontSize: 12, color: TEXT.faint, marginLeft: 8 }}>{idioma.nativo}</span>
        </span>
        {perfil?.cefr_level ? (
          <span
            style={{
              fontSize: 11.5,
              padding: "2px 8px",
              borderRadius: 5,
              border: `1px solid ${ACC}`,
              color: ACC4,
            }}
          >
            {/* O nível na régua escolhida, com o CEFR ao lado: a conversão é a
                promessa do módulo, e escondê-la deixaria a pessoa sem como
                conferir de onde saiu o número. */}
            {perfil.exam_level ?? perfil.cefr_level}
            {perfil.exam !== "cefr" && perfil.exam_level ? ` · ${perfil.cefr_level}` : ""}
          </span>
        ) : (
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>sem nivelamento</span>
        )}
      </label>

      {ligado ? (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${HAIRLINE}` }}>
          <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>
            Acompanhar o nível na escala de
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
            {idioma.exames.map((exame) => {
              const ativo = exame.id === exameAtual?.id;
              return (
                <button
                  key={exame.id}
                  type="button"
                  aria-pressed={ativo}
                  disabled={ocupado}
                  title={exame.descricao}
                  // Trocar de exame limpa a meta: "7.0" não quer dizer nada no
                  // JLPT, e manter o valor antigo deixaria uma meta que a
                  // conversão não reconhece.
                  onClick={() => onSalvar({ exam: exame.id, exam_target: null })}
                  style={{
                    padding: "5px 11px",
                    borderRadius: 6,
                    font: "inherit",
                    fontSize: 12.5,
                    cursor: "pointer",
                    border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.16)"}`,
                    background: ativo ? "rgba(145,132,217,.13)" : "transparent",
                    color: ativo ? ACC4 : TEXT.muted,
                  }}
                >
                  {exame.nome}
                </button>
              );
            })}
          </div>

          {exameAtual ? (
            <>
              <p
                style={{
                  fontSize: 11.5,
                  color: TEXT.faint,
                  margin: "8.4px 0 11.2px",
                  maxWidth: "72ch",
                }}
              >
                {exameAtual.descricao}
              </p>

              <div style={{ fontSize: 11.5, color: TEXT.faint, marginBottom: 5.6 }}>
                Meta {exameAtual.id === "cefr" ? "" : `no ${exameAtual.nome}`}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
                {exameAtual.faixas.map((faixa) => {
                  const ativo = perfil?.exam_target === faixa.rotulo;
                  return (
                    <button
                      key={faixa.rotulo}
                      type="button"
                      aria-pressed={ativo}
                      disabled={ocupado}
                      title={
                        faixa.nota
                          ? `${faixa.nota} — equivale a ${faixa.cefr} no CEFR`
                          : `Equivale a ${faixa.cefr} no CEFR`
                      }
                      onClick={() => onSalvar({ exam_target: faixa.rotulo })}
                      style={{
                        padding: "5px 11px",
                        borderRadius: 6,
                        font: "inherit",
                        fontSize: 12.5,
                        cursor: "pointer",
                        border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.16)"}`,
                        background: ativo ? "rgba(145,132,217,.13)" : "transparent",
                        color: ativo ? ACC4 : TEXT.muted,
                      }}
                    >
                      {faixa.rotulo}
                      {exameAtual.id !== "cefr" ? (
                        <span style={{ fontSize: 10, color: TEXT.faint, marginLeft: 5 }}>
                          {faixa.cefr}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>

              {perfil?.exam_target ? (
                <p style={{ fontSize: 11.5, color: C.verde, margin: "8.4px 0 0" }}>
                  Meta {perfil.exam_target}
                  {exameAtual.id !== "cefr" && perfil.target_cefr
                    ? ` — o app vai medir isso como ${perfil.target_cefr} no CEFR.`
                    : "."}
                </p>
              ) : null}

              <div style={{ fontSize: 11.5, color: TEXT.faint, margin: "14px 0 5.6px" }}>
                Tempo por dia — sai do mesmo orçamento de horas do roadmap
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
                {METAS_DIARIAS.map((minutos) => {
                  const ativo = perfil?.daily_goal_min === minutos;
                  return (
                    <button
                      key={minutos}
                      type="button"
                      aria-pressed={ativo}
                      disabled={ocupado}
                      onClick={() => onSalvar({ daily_goal_min: minutos })}
                      style={{
                        padding: "5px 11px",
                        borderRadius: 6,
                        font: "inherit",
                        fontSize: 12.5,
                        cursor: "pointer",
                        border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.16)"}`,
                        background: ativo ? "rgba(145,132,217,.13)" : "transparent",
                        color: ativo ? ACC4 : TEXT.muted,
                      }}
                    >
                      {minutos} min
                    </button>
                  );
                })}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}
