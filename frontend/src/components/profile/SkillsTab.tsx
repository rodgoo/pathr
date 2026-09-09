/**
 * O catálogo de competências, agrupado por categoria.
 *
 * A tela mostra o catálogo INTEIRO, e não só o que a pessoa já tem. É a
 * diferença entre "edite sua lista" e "monte sua lista": quem chega aqui
 * geralmente não sabe o que deveria estudar, e uma caixa de busca vazia não
 * responde essa pergunta. Agrupar por categoria também mostra o buraco — dá
 * para ver que há sete bancos no catálogo e nenhum no seu plano.
 *
 * Cada linha carrega as três decisões de uma vez: entrar no plano (a caixa), o
 * nível atual (N0 a N5) e o que isso significa (o rótulo à direita). O nível é
 * o campo honesto do produto — dizer "já sou N4 aqui" é o que impede o roadmap
 * de ensinar o que a pessoa já faz.
 *
 * Tudo grava na hora, sem botão salvar, e de forma otimista: a linha responde
 * ao clique e volta atrás se o servidor recusar.
 */

import { useState } from "react";
import { tags as tagsApi } from "@/api/endpoints";
import type { Tag, UserTag } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { MASTERY_LABELS } from "./TechnologyRow";

/**
 * A ordem das categorias na tela, e o nome que cada uma mostra.
 *
 * A ordem não é alfabética nem por tamanho: é a ordem em que as decisões
 * costumam ser tomadas. Linguagem primeiro porque é a escolha que condiciona
 * todas as outras; metodologia e idioma por último porque acompanham em vez de
 * definir. Categoria que exista no banco e não esteja aqui aparece no fim, com
 * o próprio slug — sumir da tela é pior que sair fora de ordem.
 */
const CATEGORIAS: readonly { slug: string; label: string }[] = [
  { slug: "linguagem", label: "Linguagens" },
  { slug: "frontend", label: "Frontend" },
  { slug: "backend", label: "Backend" },
  { slug: "banco", label: "Bancos de dados" },
  { slug: "dados", label: "Dados" },
  { slug: "ia", label: "IA" },
  { slug: "devops", label: "DevOps" },
  { slug: "cloud", label: "Cloud" },
  { slug: "arquitetura", label: "Arquitetura" },
  { slug: "testes", label: "Testes" },
  { slug: "seguranca", label: "Segurança" },
  { slug: "mobile", label: "Mobile" },
  { slug: "ferramenta", label: "Ferramentas" },
  { slug: "metodologia", label: "Metodologia" },
  { slug: "soft-skill", label: "Comportamental" },
  { slug: "idioma", label: "Idiomas" },
];

/** A partir de que nível o plano para de ensinar o assunto. Vem do gerador de
 * roadmap, que cobre o caminho até N3 — acima disso, ensinar seria repetir. */
const DOMINADO = 3;

export function SkillsTab() {
  const { state, dispatch } = useAppState();
  const termo = state.skillSearch.trim().toLowerCase();

  // O catálogo inteiro de uma vez. São 91 linhas — pedir por categoria seriam
  // quinze requisições para montar uma tela só.
  const catalogo = useQuery(() => tagsApi.catalog("", ""), []);
  const minhas = useQuery(() => tagsApi.mine(), []);
  const [ocupada, setOcupada] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  if (catalogo.loading || minhas.loading) return <Loading />;
  if (catalogo.error) return <ErrorState message={catalogo.error} onRetry={catalogo.reload} />;
  if (minhas.error) return <ErrorState message={minhas.error} onRetry={minhas.reload} />;

  const porTag = new Map((minhas.data ?? []).map((item) => [item.tag_id, item]));
  const visiveis = (catalogo.data ?? []).filter(
    (tag) => !termo || tag.name.toLowerCase().includes(termo),
  );

  const conhecidas = new Set(CATEGORIAS.map((categoria) => categoria.slug));
  const extras = [...new Set(visiveis.map((tag) => tag.category))]
    .filter((slug) => !conhecidas.has(slug))
    .map((slug) => ({ slug, label: slug }));

  const grupos = [...CATEGORIAS, ...extras]
    .map((categoria) => ({
      ...categoria,
      itens: visiveis.filter((tag) => tag.category === categoria.slug),
    }))
    .filter((grupo) => grupo.itens.length > 0);

  async function entrar(tag: Tag, nivel: number) {
    setOcupada(tag.id);
    setErro(null);
    try {
      const criada = await tagsApi.add({
        tag_id: tag.id,
        proficiency: nivel,
        // Quem marca N3 ou mais não quer que o plano ensine aquilo; abaixo
        // disso, entra como meta de estudo.
        is_target: nivel < DOMINADO,
      });
      minhas.set((atual) => [...(atual ?? []), criada]);
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui adicionar.");
    } finally {
      setOcupada(null);
    }
  }

  async function sair(minha: UserTag) {
    setErro(null);
    minhas.set((atual) => atual.filter((item) => item.id !== minha.id));
    try {
      await tagsApi.remove(minha.id);
    } catch (caught) {
      minhas.set((atual) => [...atual, minha]);
      setErro(caught instanceof Error ? caught.message : "Não consegui remover.");
    }
  }

  async function ajustar(minha: UserTag, nivel: number) {
    setErro(null);
    const anterior = minha.proficiency;
    minhas.set((atual) =>
      atual.map((item) =>
        item.id === minha.id ? { ...item, proficiency: nivel, is_target: nivel < DOMINADO } : item,
      ),
    );
    try {
      await tagsApi.update(minha.id, { proficiency: nivel, is_target: nivel < DOMINADO });
    } catch (caught) {
      minhas.set((atual) =>
        atual.map((item) => (item.id === minha.id ? { ...item, proficiency: anterior } : item)),
      );
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar o nível.");
    }
  }

  const total = (minhas.data ?? []).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 11.2 }}>
          <Kicker>Skills do plano</Kicker>
          <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
            {total} no perfil
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "5.6px 0 11.2px", maxWidth: "72ch" }}>
          Marque o que faz parte do seu plano e diga o nível que você já tem. O roadmap cobre o
          caminho de onde você está até N3 — o que estiver em N3 ou acima ele não ensina de novo.
        </p>
        <div className="field" style={{ margin: 0 }}>
          <label htmlFor="skill-search">Filtrar por nome</label>
          <input
            id="skill-search"
            className="input"
            type="search"
            placeholder="ex: Kafka, Terraform"
            value={state.skillSearch}
            onChange={(event) => dispatch({ type: "setSkillSearch", value: event.target.value })}
          />
        </div>
      </Panel>

      {erro ? <ErrorState message={erro} /> : null}

      {grupos.map((grupo) => {
        const noPlano = grupo.itens.filter((tag) => porTag.has(tag.id)).length;
        return (
          <Panel key={grupo.slug} pad={16.8}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "baseline",
                gap: 11.2,
                marginBottom: 11.2,
              }}
            >
              <Kicker>{grupo.label}</Kicker>
              <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.faint }}>
                {noPlano} de {grupo.itens.length} no plano
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {grupo.itens.map((tag) => (
                <LinhaDeSkill
                  key={tag.id}
                  tag={tag}
                  minha={porTag.get(tag.id)}
                  ocupada={ocupada === tag.id}
                  onEntrar={(nivel) => void entrar(tag, nivel)}
                  onSair={(minha) => void sair(minha)}
                  onNivel={(minha, nivel) => void ajustar(minha, nivel)}
                />
              ))}
            </div>
          </Panel>
        );
      })}

      {grupos.length === 0 ? (
        <Panel pad={16.8}>
          <p style={{ fontSize: 13, color: TEXT.muted, margin: 0 }}>
            Nenhuma tecnologia com “{state.skillSearch}”. Tente outro termo — o catálogo tem 91
            entradas.
          </p>
        </Panel>
      ) : null}
    </div>
  );
}

/**
 * Uma tecnologia do catálogo.
 *
 * A caixa e os níveis fazem coisas diferentes de propósito: a caixa decide se
 * entra no plano, os níveis dizem onde a pessoa está. Clicar num nível de algo
 * que ainda não está no plano ADICIONA já com aquele nível — obrigar dois
 * cliques para dizer "eu sei React, nível 4" seria burocracia.
 */
function LinhaDeSkill({
  tag,
  minha,
  ocupada,
  onEntrar,
  onSair,
  onNivel,
}: {
  tag: Tag;
  minha?: UserTag;
  ocupada: boolean;
  onEntrar: (nivel: number) => void;
  onSair: (minha: UserTag) => void;
  onNivel: (minha: UserTag, nivel: number) => void;
}) {
  const dentro = Boolean(minha);
  const nivel = minha?.proficiency ?? 0;
  const dominado = dentro && nivel >= DOMINADO;

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 11.2,
        padding: "8.4px 11.2px",
        borderRadius: 8,
        background: dentro ? "rgba(145,132,217,.07)" : "transparent",
        boxShadow: dentro ? "inset 0 0 0 1px rgba(145,132,217,.22)" : "none",
        opacity: ocupada ? 0.6 : 1,
      }}
    >
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          cursor: "pointer",
          flex: 1,
          minWidth: 140,
        }}
      >
        <input
          type="checkbox"
          checked={dentro}
          disabled={ocupada}
          onChange={() => (minha ? onSair(minha) : onEntrar(1))}
          style={{ flex: "none", accentColor: "#9184d9" }}
        />
        <span style={{ fontSize: 13.5, color: dentro ? TEXT.full : TEXT.muted }}>{tag.name}</span>
      </label>

      <div
        role="radiogroup"
        aria-label={`Nível em ${tag.name}`}
        style={{ display: "flex", gap: 2.8, flex: "none" }}
      >
        {MASTERY_LABELS.map((rotulo, valor) => {
          const ativo = dentro && nivel === valor;
          return (
            <button
              key={valor}
              type="button"
              role="radio"
              aria-checked={ativo}
              title={`N${valor} — ${rotulo}`}
              disabled={ocupada}
              onClick={() => (minha ? onNivel(minha, valor) : onEntrar(valor))}
              style={{
                minWidth: 30,
                padding: "3px 6px",
                borderRadius: 5,
                font: "inherit",
                fontSize: 10.5,
                cursor: "pointer",
                border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.12)"}`,
                background: ativo ? "rgba(145,132,217,.16)" : "transparent",
                color: ativo ? ACC4 : "rgba(233,233,237,.38)",
              }}
            >
              N{valor}
            </button>
          );
        })}
      </div>

      <span
        style={{
          flex: "none",
          minWidth: 88,
          textAlign: "right",
          fontSize: 11.5,
          color: !dentro ? TEXT.faint : dominado ? C.verde : ACC4,
        }}
      >
        {!dentro ? "fora do plano" : dominado ? "já dominado" : "a evoluir"}
      </span>
    </div>
  );
}
