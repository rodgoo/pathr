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
 *
 * Salvar sozinho só funciona se a tela DISSER que salvou, e disser ao lado do
 * campo que a pessoa acabou de mexer. Um aviso no topo da página, longe do
 * cursor, não é confirmação — é o mesmo silêncio de antes. Por isso o estado
 * de salvamento carrega qual campo o produziu, e cada painel mostra só o seu.
 */

import { useEffect, useRef, useState } from "react";
import { profile as profileApi } from "@/api/endpoints";
import type { Profile } from "@/api/types";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, SIZE, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { RegiaoDasVagas } from "./RegiaoDasVagas";

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

/** Os campos que salvam sozinhos. O estado de salvamento nomeia um deles para
 * a confirmação aparecer no painel certo. */
type Campo = "destino" | "contexto" | "horas" | "regiao";

type Salvamento =
  | { campo: Campo; estado: "salvando" }
  | { campo: Campo; estado: "salvo" }
  | { campo: Campo; estado: "erro"; mensagem: string }
  | null;

/** O texto livre vira lista de metas: uma linha, um item. O banco guarda
 * lista porque o gerador lê item a item. */
function metas(texto: string): string[] {
  return texto
    .split("\n")
    .map((linha) => linha.trim())
    .filter(Boolean);
}

export function ObjectiveTab() {
  const carregado = useQuery(() => profileApi.get(), []);
  const [perfil, setPerfil] = useState<Profile | null>(null);
  const [contexto, setContexto] = useState("");
  // O que já está no servidor. Sem isto, sair do campo sem ter digitado nada
  // dispararia uma escrita e anunciaria "salvo" para quem só passou o cursor.
  const [contextoSalvo, setContextoSalvo] = useState("");
  const [salvamento, setSalvamento] = useState<Salvamento>(null);
  const temporizador = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!carregado.data) return;
    setPerfil(carregado.data);
    const texto = (carregado.data.goals ?? []).map(String).join("\n");
    setContexto(texto);
    setContextoSalvo(texto);
  }, [carregado.data]);

  // O "salvo" some sozinho depois de um tempo; se o componente sair antes
  // disso, o timer pendente escreveria em estado que não existe mais.
  useEffect(() => () => window.clearTimeout(temporizador.current), []);

  if (carregado.loading) return <Loading />;
  if (carregado.error) return <ErrorState message={carregado.error} onRetry={carregado.reload} />;
  if (!perfil) return null;

  async function salvar(mudanca: Partial<Profile>, campo: Campo) {
    // Um salvamento novo cancela o "salvo" do anterior — sem isso, o timer
    // antigo apagaria a confirmação deste antes da hora.
    window.clearTimeout(temporizador.current);
    setSalvamento({ campo, estado: "salvando" });
    setPerfil((atual) => (atual ? { ...atual, ...mudanca } : atual));
    try {
      await profileApi.update(mudanca);
      if (mudanca.goals) setContextoSalvo(metas(contexto).join("\n"));
      setSalvamento({ campo, estado: "salvo" });
      temporizador.current = window.setTimeout(() => setSalvamento(null), 2500);
    } catch (caught) {
      setSalvamento({
        campo,
        estado: "erro",
        mensagem: caught instanceof Error ? caught.message : "Não consegui salvar.",
      });
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
          <Estado salvamento={salvamento} campo="destino" />
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
                onClick={() => void salvar({ target_role: destino.titulo }, "destino")}
                style={{
                  display: "flex",
                  gap: 9,
                  alignItems: "flex-start",
                  textAlign: "left",
                  padding: 11.2,
                  borderRadius: 8,
                  cursor: "pointer",
                  font: "inherit",
                  fontSize: SIZE.corpo,
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
            onBlur={() => {
              // Compara o texto JA normalizado dos dois lados. `contextoSalvo`
              // guarda o que o servidor tem, que passou por `metas()`; comparar
              // com o texto cru faria uma linha em branco no fim contar como
              // mudanca e gravar de novo a cada saida do campo.
              const proximo = metas(contexto).join("\n");
              if (proximo === contextoSalvo) return;
              void salvar({ goals: metas(contexto) }, "contexto");
            }}
          />
          {/* O aviso e a confirmacao moram na mesma linha, colada no campo:
              o topo do painel fica longe demais do cursor de quem acabou de
              sair do textarea para servir de resposta. */}
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 8.4,
              margin: "5.6px 0 0",
              minHeight: 16,
            }}
          >
            <span style={{ fontSize: 11.5, color: TEXT.faint }}>
              Salva sozinho quando você sai do campo — não há botão a apertar.
            </span>
            <Estado salvamento={salvamento} campo="contexto" />
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginTop: 8.4 }}>
          {ATALHOS.map((atalho) => (
            <button
              key={atalho}
              type="button"
              onClick={() => {
                const proximo = contexto ? `${contexto}\n${atalho}` : atalho;
                setContexto(proximo);
                void salvar({ goals: metas(proximo) }, "contexto");
              }}
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
        <div style={{ display: "flex", alignItems: "baseline", gap: 11.2, marginBottom: 5.6 }}>
          <Kicker>Horas por semana</Kicker>
          <Estado salvamento={salvamento} campo="horas" />
        </div>
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
                onClick={() => void salvar({ weekly_hours: horas }, "horas")}
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

      <RegiaoDasVagas
        perfil={perfil}
        salvar={(mudanca) => void salvar(mudanca, "regiao")}
        estado={<Estado salvamento={salvamento} campo="regiao" />}
      />
    </div>
  );
}

/**
 * O que aconteceu com o último salvamento DESTE campo.
 *
 * Cada painel monta o seu; o estado carrega qual campo o gerou, então a
 * confirmação nasce ao lado do que a pessoa mexeu em vez de num canto da tela
 * que ela não está olhando.
 */
function Estado({ salvamento, campo }: { salvamento: Salvamento; campo: Campo }) {
  if (!salvamento || salvamento.campo !== campo) return null;
  const cor =
    salvamento.estado === "salvo" ? C.verde : salvamento.estado === "erro" ? C.rosa : TEXT.faint;
  return (
    <span
      role="status"
      style={{ fontSize: 11.5, color: cor, whiteSpace: "nowrap" }}
    >
      {salvamento.estado === "salvando" ? "salvando…" : null}
      {salvamento.estado === "salvo" ? "salvo" : null}
      {salvamento.estado === "erro" ? `não salvou — ${salvamento.mensagem}` : null}
    </span>
  );
}
