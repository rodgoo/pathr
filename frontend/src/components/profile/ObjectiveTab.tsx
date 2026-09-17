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
import { useT } from "@/lib/i18n";
import { ACC, ACC4, C, SIZE, TEXT } from "@/lib/tokens";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel } from "@/components/ui/primitives";
import { RegiaoDasVagas } from "./RegiaoDasVagas";

/** As áreas, na ordem em que aparecem no filtro. */
const AREAS = [
  "Fullstack",
  "Frontend",
  "Backend",
  "Mobile",
  "Dados",
  "IA e ML",
  "DevOps e Cloud",
  "Qualidade (QA)",
  "Segurança",
  "Carreira",
] as const;
type Area = (typeof AREAS)[number];

/** Destinos prontos. O título vira `target_role`; o detalhe explica o recorte,
 * porque "Fullstack Java pleno" quer dizer coisas diferentes para quem foca em
 * vaga internacional e para quem foca em arquitetura. */
// Os oito primeiros títulos são os de antes, sem uma letra mudada: quem já
// escolheu um deles continua vendo a opção marcada. O título vira o
// `target_role`, que o roadmap, as vagas (o papel no título da vaga) e os
// cursos leem — por isso cada um cita a área e as tecnologias do caminho.
const DESTINOS: readonly { titulo: string; detalhe: string; area: Area }[] = [
  { area: "Fullstack", titulo: "Fullstack Java pleno, sem depender de IA para codar", detalhe: "ênfase em escrever do zero e revisar" },
  { area: "Fullstack", titulo: "Fullstack Java pleno com foco em vagas internacionais", detalhe: "inclui entrevista técnica em inglês" },
  { area: "Backend", titulo: "Especialista backend Java, arquitetura e system design", detalhe: "menos frontend, mais desenho de sistema" },
  { area: "Dados", titulo: "Migrar de frontend para dados e engenharia de plataforma", detalhe: "SQL, pipelines e infraestrutura" },
  { area: "Carreira", titulo: "Sair de júnior para pleno na empresa atual", detalhe: "foco em entregar sozinho e revisar código" },
  { area: "Carreira", titulo: "Preparação intensiva para entrevistas", detalhe: "algoritmos, system design e comportamental" },
  { area: "Carreira", titulo: "Fundar um produto próprio", detalhe: "do MVP ao deploy, com custo controlado" },
  { area: "Carreira", titulo: "Ainda decidindo — quero um plano amplo", detalhe: "cobre base ampla e ajusta depois" },

  { area: "Fullstack", titulo: "Fullstack JavaScript/TypeScript com React e Node.js", detalhe: "do front ao back numa linguagem só" },
  { area: "Fullstack", titulo: "Fullstack Python com Django ou FastAPI e React", detalhe: "APIs em Python e interface moderna" },
  { area: "Frontend", titulo: "Desenvolvedor frontend React com TypeScript", detalhe: "componentes, estado, testes e performance" },
  { area: "Frontend", titulo: "Desenvolvedor frontend Angular para sistemas corporativos", detalhe: "RxJS, formulários e integração com APIs" },
  { area: "Frontend", titulo: "Frontend com foco em acessibilidade, design system e UX", detalhe: "HTML semântico, CSS e componentes reutilizáveis" },
  { area: "Backend", titulo: "Desenvolvedor backend Node.js e TypeScript com APIs e microsserviços", detalhe: "NestJS, filas, bancos e observabilidade" },
  { area: "Backend", titulo: "Desenvolvedor backend Python com FastAPI e dados", detalhe: "APIs, SQL, testes e deploy" },
  { area: "Backend", titulo: "Desenvolvedor backend .NET e C# para empresas", detalhe: "ASP.NET, Entity Framework e Azure" },
  { area: "Backend", titulo: "Desenvolvedor backend Go para sistemas de alta performance", detalhe: "concorrência, gRPC e Kubernetes" },
  { area: "Mobile", titulo: "Desenvolvedor mobile com Flutter", detalhe: "Android e iOS com um código só" },
  { area: "Mobile", titulo: "Desenvolvedor mobile React Native", detalhe: "aproveita JavaScript e React no celular" },
  { area: "Mobile", titulo: "Desenvolvedor Android nativo com Kotlin", detalhe: "Jetpack Compose e arquitetura moderna" },
  { area: "Dados", titulo: "Analista de dados com SQL, Python e Power BI", detalhe: "consultas, dashboards e storytelling com dados" },
  { area: "Dados", titulo: "Engenheiro de dados com Spark, Airflow e cloud", detalhe: "pipelines, data lake e qualidade de dados" },
  { area: "IA e ML", titulo: "Cientista de dados e machine learning com Python", detalhe: "estatística, modelos e avaliação" },
  { area: "IA e ML", titulo: "Engenheiro de IA com LLMs, RAG e agentes", detalhe: "integração de modelos em produtos reais" },
  { area: "DevOps e Cloud", titulo: "DevOps e SRE com Docker, Kubernetes e CI/CD", detalhe: "automação, observabilidade e confiabilidade" },
  { area: "DevOps e Cloud", titulo: "Engenheiro cloud AWS com certificação", detalhe: "arquitetura na AWS e infraestrutura como código" },
  { area: "Qualidade (QA)", titulo: "QA e automação de testes com Cypress, Playwright e APIs", detalhe: "testes end-to-end, de API e em pipeline" },
  { area: "Segurança", titulo: "Segurança da informação e AppSec para desenvolvedores", detalhe: "OWASP, pentest de aplicações e código seguro" },
  { area: "Carreira", titulo: "Primeiro emprego em tecnologia, do zero", detalhe: "lógica, Git, uma linguagem e portfólio" },
  { area: "Carreira", titulo: "Transição de carreira para tecnologia", detalhe: "vinda de outra área, no seu ritmo" },
  { area: "Carreira", titulo: "Tech lead: liderança técnica e arquitetura", detalhe: "decisões técnicas, code review e mentoria" },
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
  const t = useT();
  const carregado = useQuery(() => profileApi.get(), []);
  const [perfil, setPerfil] = useState<Profile | null>(null);
  const [contexto, setContexto] = useState("");
  // O que já está no servidor. Sem isto, sair do campo sem ter digitado nada
  // dispararia uma escrita e anunciaria "salvo" para quem só passou o cursor.
  const [contextoSalvo, setContextoSalvo] = useState("");
  const [salvamento, setSalvamento] = useState<Salvamento>(null);
  // O filtro de área dos destinos. Abre na área do destino já escolhido.
  const [area, setArea] = useState<Area | "Todas">("Todas");
  const temporizador = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!carregado.data) return;
    setPerfil(carregado.data);
    const escolhido = DESTINOS.find((d) => d.titulo === carregado.data?.target_role);
    if (escolhido) setArea(escolhido.area);
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
        mensagem: caught instanceof Error ? caught.message : t("perfil.objetivo.erroSalvar"),
      });
    }
  }

  const destinoLivre =
    Boolean(perfil.target_role) && !DESTINOS.some((d) => d.titulo === perfil.target_role);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
      <Panel pad={16.8}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 11.2, marginBottom: 11.2 }}>
          <Kicker>{t("perfil.objetivo.ondeChegar")}</Kicker>
          <span style={{ fontSize: 11.5, color: TEXT.faint }}>
            {t("perfil.objetivo.escolhaOuDescreva")}
          </span>
          <Estado salvamento={salvamento} campo="destino" />
        </div>

        {/* Muitos destinos: a área filtra, e "Todas" mostra a lista inteira. */}
        <div role="group" aria-label={t("perfil.objetivo.areaLabel")} style={{ display: "flex", flexWrap: "wrap", gap: 5.6, marginBottom: 11.2 }}>
          {(["Todas", ...AREAS] as const).map((opcao) => {
            const ativa = area === opcao;
            return (
              <button
                key={opcao}
                type="button"
                aria-pressed={ativa}
                onClick={() => setArea(opcao)}
                style={{
                  padding: "5px 11px",
                  borderRadius: 999,
                  font: "inherit",
                  fontSize: 12,
                  cursor: "pointer",
                  border: `1px solid ${ativa ? ACC : "rgba(233,233,237,.14)"}`,
                  background: ativa ? "rgba(145,132,217,.13)" : "transparent",
                  color: ativa ? ACC4 : TEXT.muted,
                }}
              >
                {opcao}
              </button>
            );
          })}
        </div>

        <div
          role="radiogroup"
          aria-label={t("perfil.objetivo.destinoPlanoLabel")}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 8.4,
          }}
        >
          {DESTINOS.filter((destino) => area === "Todas" || destino.area === area).map((destino) => {
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
            {t("perfil.objetivo.destinoLivre", { destino: perfil.target_role ?? "" })}
          </p>
        ) : null}
      </Panel>

      <Panel pad={16.8}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 11.2, marginBottom: 5.6 }}>
          <Kicker>{t("perfil.objetivo.textoLivre")}</Kicker>
          <span
            style={{
              fontSize: 10.5,
              padding: "1px 6px",
              borderRadius: 5,
              border: `1px solid ${ACC}`,
              color: ACC4,
            }}
          >
            {t("perfil.objetivo.geraPlanoInteiro")}
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "70ch" }}>
          {t("perfil.objetivo.textoLivreDescricao")}
        </p>

        <div className="field">
          <label htmlFor="objetivo-livre">{t("perfil.objetivo.contextoLabel")}</label>
          <textarea
            id="objetivo-livre"
            className="input"
            rows={5}
            style={{ resize: "vertical", lineHeight: 1.5 }}
            placeholder={t("perfil.objetivo.contextoPlaceholder")}
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
              {t("perfil.objetivo.salvaSozinho")}
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
          <Kicker>{t("perfil.objetivo.horasPorSemana")}</Kicker>
          <Estado salvamento={salvamento} campo="horas" />
        </div>
        <p style={{ fontSize: 12.5, color: TEXT.muted, margin: "0 0 11.2px", maxWidth: "70ch" }}>
          {t("perfil.objetivo.horasDescricao")}
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
  const t = useT();
  if (!salvamento || salvamento.campo !== campo) return null;
  const cor =
    salvamento.estado === "salvo" ? C.verde : salvamento.estado === "erro" ? C.rosa : TEXT.faint;
  return (
    <span
      role="status"
      style={{ fontSize: 11.5, color: cor, whiteSpace: "nowrap" }}
    >
      {salvamento.estado === "salvando" ? t("perfil.objetivo.salvando") : null}
      {salvamento.estado === "salvo" ? t("perfil.objetivo.salvo") : null}
      {salvamento.estado === "erro" ? t("perfil.objetivo.naoSalvou", { mensagem: salvamento.mensagem }) : null}
    </span>
  );
}
