/**
 * Objetivo: para onde o plano leva.
 *
 * É a entrada mais determinante do produto. O roadmap cobre a distância entre
 * o que a pessoa sabe e onde ela quer chegar — sem o destino, o gerador só tem
 * metade da conta e monta um plano genérico.
 *
 * Duas formas de responder, e as duas gravam no mesmo lugar. Os destinos
 * prontos existem porque escrever um objetivo do zero é difícil e a maioria
 * das pessoas se reconhece numa das opções. O texto livre existe porque quem
 * sabe exatamente o que quer não deve ser espremido numa lista.
 *
 * Salva ao sair do campo, e não num botão "Salvar": um formulário de
 * configuração com botão faz a pessoa achar que perdeu o que digitou quando
 * troca de aba.
 */

import { useEffect, useState } from "react";
import { profile as profileApi } from "@/api/endpoints";
import type { Profile } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";

/** Destinos prontos. O título vira `target_role`; o detalhe explica o recorte,
 * porque "Fullstack Java pleno" quer dizer coisas diferentes para quem foca em
 * vaga internacional e para quem foca em arquitetura. */
const DESTINOS: readonly { titulo: string; detalhe: string }[] = [
  {
    titulo: "Fullstack Java pleno, sem depender de IA para codar",
    detalhe: "ênfase em escrever do zero e revisar",
  },
  {
    titulo: "Fullstack Java pleno com foco em vagas internacionais",
    detalhe: "inclui entrevista técnica em inglês",
  },
  {
    titulo: "Especialista backend Java, arquitetura e system design",
    detalhe: "menos frontend, mais desenho de sistema",
  },
  {
    titulo: "Migrar de frontend para dados e engenharia de plataforma",
    detalhe: "SQL, pipelines e infraestrutura",
  },
  {
    titulo: "Sair de júnior para pleno na empresa atual",
    detalhe: "foco em entregar sozinho e revisar código",
  },
  {
    titulo: "Preparação intensiva para entrevistas",
    detalhe: "algoritmos, system design e comportamental",
  },
  { titulo: "Fundar um produto próprio", detalhe: "do MVP ao deploy, com custo controlado" },
  {
    titulo: "Ainda decidindo — quero um plano amplo",
    detalhe: "cobre base ampla e ajusta depois",
  },
];

/** Trechos que a pessoa cola no texto livre com um clique: são as restrições
 * que mais mudam o plano e que mais se esquece de citar. */
const ATALHOS = [
  "Tenho 8h por semana",
  "Quero entrevista em inglês",
  "Sem depender de IA para codar",
  "Prazo de 6 meses",
];

const HORAS = [4, 6, 8, 10, 15, 20];

export function ObjectiveTab() {
  const carregado = useQuery(() => profileApi.get(), []);
  const [perfil, setPerfil] = useState<Profile | null>(null);
  const [contexto, setContexto] = useState("");
  const [salvo, setSalvo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!carregado.data) return;
    setPerfil(carregado.data);
    // `goals` é lista no banco (o gerador lê item a item). Aqui vira um texto
    // só: junta na leitura, separa por linha na escrita.
    setContexto((carregado.data.goals ?? []).map(String).join("\n"));
  }, [carregado.data]);

  if (carregado.loading) return <Loading />;
  if (carregado.error) return <ErrorState message={carregado.error} onRetry={carregado.reload} />;
  if (!perfil) return null;

  async function salvar(mudanca: Partial<Profile>) {
    setErro(null);
    setPerfil((atual) => (atual ? { ...atual, ...mudanca } : atual));
    try {
      await profileApi.update(mudanca);
      setSalvo(true);
      window.setTimeout(() => setSalvo(false), 2500);
    } catch (caught) {
      setErro(caught instanceof Error ? caught.message : "Não consegui salvar.");
    }
  }

  const destinoLivre =
    Boolean(perfil.target_role) && !DESTINOS.some((d) => d.titulo === perfil.target_role);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 11.2, marginBottom: 11.2 }}>
          <Kicker>Onde você quer chegar</Kicker>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            escolha um destino ou descreva o seu abaixo
          </span>
          {salvo ? (
            <span role="status" style={{ marginLeft: "auto", fontSize: 11.5, color: C.verde }}>
              salvo
            </span>
          ) : null}
        </div>

        <div
          role="radiogroup"
          aria-label="Destino do plano"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 8.4,
          }}
        >
          {DESTINOS.map((destino) => {
            const ativo = perfil.target_role === destino.titulo;
            return (
              <button
                key={destino.titulo}
                type="button"
                role="radio"
                aria-checked={ativo}
                onClick={() => void salvar({ target_role: destino.titulo })}
                style={{
                  display: "flex",
                  gap: 9,
                  alignItems: "flex-start",
                  textAlign: "left",
                  padding: 11.2,
                  borderRadius: 8,
                  cursor: "pointer",
                  font: "inherit",
                  background: ativo ? "rgba(145,132,217,.13)" : "transparent",
                  border: `1px solid ${ativo ? ACC : "rgba(233,233,237,.14)"}`,
                  color: TEXT.full,
                }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 13,
                    height: 13,
                    marginTop: 3,
                    flex: "none",
                    borderRadius: "50%",
                    border: `1px solid ${ativo ? ACC4 : "rgba(233,233,237,.35)"}`,
                    background: ativo ? ACC4 : "transparent",
                  }}
                />
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: "block", fontSize: 13.5, lineHeight: 1.35 }}>
                    {destino.titulo}
                  </span>
                  <span
                    style={{ display: "block", fontSize: 11.5, color: TEXT.faint, marginTop: 4 }}
                  >
                    {destino.detalhe}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        {destinoLivre ? (
          <p style={{ fontSize: 11.5, color: TEXT.faint, margin: "11.2px 0 0" }}>
            Seu destino atual foi escrito por você: “{perfil.target_role}”. Escolher um da lista
            substitui.
          </p>
        ) : null}
      </Panel>

      <Panel pad={16.8}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 11.2, marginBottom: 5.6 }}>
          <Kicker>Descreva em texto livre</Kicker>
          <span
            style={{
              fontSize: 10.5,
              padding: "1px 6px",
              borderRadius: 5,
              border: `1px solid ${ACC}`,
              color: ACC4,
            }}
          >
            gera o plano inteiro
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "70ch" }}>
          Conte onde você está, para onde quer ir e o que atrapalha. A partir disso o roadmap sai
          por fases, a Biblioteca busca vídeo e artigo das tecnologias certas, e os quizzes saem no
          seu nível.
        </p>

        <div className="field">
          <label htmlFor="objetivo-livre">Contexto para a geração do plano</label>
          <textarea
            id="objetivo-livre"
            className="input"
            rows={5}
            style={{ resize: "vertical", lineHeight: 1.5 }}
            placeholder="ex: sou frontend há 3 anos, quero virar fullstack Java sem depender de IA para codar, tenho 8h por semana e quero passar em entrevista técnica em inglês até junho"
            value={contexto}
            onChange={(event) => setContexto(event.target.value)}
            // Salva ao sair do campo. Um botão faria a pessoa achar que perdeu
            // o texto ao trocar de aba — e este é o campo mais caro de perder.
            onBlur={() =>
              void salvar({
                goals: contexto
                  .split("\n")
                  .map((linha) => linha.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 8.4 }}>
          {ATALHOS.map((atalho) => (
            <button
              key={atalho}
              type="button"
              onClick={() => setContexto((atual) => (atual ? `${atual}\n${atalho}` : atalho))}
              style={{
                padding: "5px 10px",
                borderRadius: 6,
                font: "inherit",
                fontSize: 12,
                cursor: "pointer",
                border: "1px dashed rgba(233,233,237,.22)",
                background: "transparent",
                color: TEXT.muted,
              }}
            >
              {atalho}
            </button>
          ))}
        </div>
      </Panel>

      <Panel pad={16.8}>
        <Kicker style={{ display: "block", marginBottom: 5.6 }}>Horas por semana</Kicker>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "70ch" }}>
          O plano é dimensionado por isto, e não pelo ideal do assunto. Um plano que exige 20h de
          quem tem 6h não é ambicioso — é um plano abandonado na terceira semana.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
          {HORAS.map((horas) => {
            const ativo = perfil.weekly_hours === horas;
            return (
              <button
                key={horas}
                type="button"
                aria-pressed={ativo}
                onClick={() => void salvar({ weekly_hours: horas })}
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
                {horas}h
              </button>
            );
          })}
        </div>
      </Panel>

      {erro ? <ErrorState message={erro} /> : null}
    </div>
  );
}
