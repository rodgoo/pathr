/**
 * Onboarding pelo currículo: enviar, ler, revisar, importar.
 *
 * Quatro passos, cada um uma requisição, porque só a leitura é lenta e só ela
 * pode falhar por cota de IA — o upload nunca se perde porque o modelo estava
 * fora.
 *
 * O passo de revisão não é cerimônia: a proficiência que a IA estima é
 * palpite sobre o que a pessoa escreveu sobre si, e o roadmap inteiro é
 * construído em cima dela. Corrigir antes custa um minuto; corrigir depois
 * custa refazer o plano.
 */

import { useState } from "react";
import { resumes as resumesApi } from "@/api/endpoints";
import type { ParsedTechnology, Resume } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useMutation, useQuery } from "@/hooks/useApi";
import { ACC, C, TEXT } from "@/lib/tokens";
import { Icon } from "@/components/ui/icons";
import { ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { MASTERY_LABELS, TechnologyRow } from "@/components/profile/TechnologyRow";

export function CvPage() {
  const { state, dispatch } = useAppState();
  const list = useQuery(() => resumesApi.list(), []);
  const [current, setCurrent] = useState<Resume | null>(null);

  const resume =
    current ?? list.data?.find((item) => item.id === state.activeResumeId) ?? null;

  if (list.loading && !resume) return <Loading label="Carregando seus currículos…" />;

  return (
    <div style={{ maxWidth: 1000, ...SCREEN_IN }}>
      <div
        style={{
          fontSize: 11,
          letterSpacing: ".1em",
          textTransform: "uppercase",
          color: ACC,
          marginBottom: 8.4,
        }}
      >
        Base do seu plano
      </div>

      {!resume ? (
        <Upload
          onUploaded={(uploaded) => {
            setCurrent(uploaded);
            dispatch({ type: "openResume", resumeId: uploaded.id });
            list.reload();
          }}
        />
      ) : resume.status === "parsed" ? (
        <Review resume={resume} onDone={() => dispatch({ type: "navigate", screen: "roadmap" })} />
      ) : (
        <Parse resume={resume} onParsed={setCurrent} onRestart={() => setCurrent(null)} />
      )}
    </div>
  );
}


/** Passo 1: o arquivo. */
function Upload({ onUploaded }: { onUploaded: (resume: Resume) => void }) {
  const upload = useMutation((file: File) => resumesApi.upload(file));
  const [dragging, setDragging] = useState(false);

  async function send(file: File | undefined) {
    if (!file) return;
    const result = await upload.run(file);
    if (result) onUploaded(result);
  }

  return (
    <>
      <h1 style={{ fontSize: 32, margin: "0 0 8.4px" }}>Envie seu currículo</h1>
      <p style={{ maxWidth: "62ch", color: "rgba(233,233,237,.7)", fontSize: 14 }}>
        Leio o arquivo, extraio suas competências, estimo o nível de cada uma e monto o roadmap a
        partir do que falta. Você revisa tudo antes de eu gerar.
      </p>

      {upload.error ? <ErrorState message={upload.error} /> : null}

      <label
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void send(event.dataTransfer.files[0]);
        }}
        style={{
          marginTop: 22.4,
          border: `1px dashed ${dragging ? ACC : "rgba(233,233,237,.28)"}`,
          borderRadius: 14,
          padding: "44px 22.4px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 11.2,
          textAlign: "center",
          cursor: upload.pending ? "progress" : "pointer",
          background: dragging
            ? "rgba(145,132,217,.10)"
            : "linear-gradient(180deg,rgba(145,132,217,.05),transparent)",
        }}
      >
        <span style={{ color: ACC }}>
          <Icon name="upload" size={30} />
        </span>
        <div style={{ fontSize: 16 }}>
          {upload.pending ? "Enviando…" : "Arraste o arquivo aqui ou clique para escolher"}
        </div>
        <div style={{ fontSize: 12.5, color: TEXT.muted }}>
          PDF, DOCX, ODT, RTF, TXT ou MD · até 10 MB · fica na sua conta, não é compartilhado
        </div>
        <input
          type="file"
          accept=".pdf,.docx,.odt,.rtf,.txt,.md,application/pdf"
          disabled={upload.pending}
          onChange={(event) => void send(event.target.files?.[0])}
          // Escondido visualmente, mas ainda um input de verdade: sem
          // `pointer-events: none`, que impediria o clique e, com ele, a
          // navegação por teclado e por tecnologia assistiva de chegar aqui.
          style={{
            position: "absolute",
            width: 1,
            height: 1,
            opacity: 0,
            overflow: "hidden",
            clip: "rect(0 0 0 0)",
            whiteSpace: "nowrap",
          }}
        />
      </label>
    </>
  );
}

/**
 * Passo 2: a leitura.
 *
 * A chamada demora de 2 a 15 segundos — é uma requisição de IA de verdade, e
 * a lista de etapas existe para a espera ter forma em vez de ser um spinner
 * mudo.
 */
function Parse({
  resume,
  onParsed,
  onRestart,
}: {
  resume: Resume;
  onParsed: (resume: Resume) => void;
  onRestart: () => void;
}) {
  const parse = useMutation(() => resumesApi.parse(resume.id));

  async function run() {
    const result = await parse.run();
    if (result) onParsed(result);
  }

  const steps = [
    "Separando seções: experiência, formação, projetos",
    "Reconhecendo tecnologias citadas e o contexto de uso",
    "Estimando nível por tempo de uso e responsabilidade",
    "Cruzando com a meta para achar as lacunas",
  ];

  return (
    <>
      <h1 style={{ fontSize: 32, margin: "0 0 8.4px" }}>Ler o currículo</h1>
      <p style={{ maxWidth: "62ch", color: "rgba(233,233,237,.7)", fontSize: 14 }}>
        {resume.filename} · {Math.round(resume.size_bytes / 1024)} KB
      </p>

      {parse.error ? <ErrorState message={parse.error} onRetry={run} /> : null}
      {resume.error && !parse.error ? (
        <p
          style={{
            marginTop: 14,
            padding: "11.2px 14px",
            borderRadius: 8,
            background: "rgba(207,162,94,.10)",
            borderLeft: `2px solid ${C.ambar}`,
            fontSize: 12.5,
          }}
        >
          {resume.error}. Vou mandar o arquivo inteiro para o modelo ler visualmente.
        </p>
      ) : null}

      <Panel pad={22.4} style={{ marginTop: 22.4 }}>
        {parse.pending ? (
          <>
            <div
              aria-hidden
              style={{
                height: 3,
                borderRadius: 2,
                background: "rgba(233,233,237,.12)",
                overflow: "hidden",
                position: "relative",
                marginBottom: 16.8,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: `linear-gradient(90deg,transparent,${ACC},transparent)`,
                  animation: "noc-sweep 1.1s linear infinite",
                }}
              />
            </div>
            <ol
              aria-live="polite"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 5.6,
                fontSize: 12.5,
                color: "rgba(233,233,237,.65)",
                listStyle: "none",
                margin: 0,
                padding: 0,
              }}
            >
              {steps.map((step) => (
                <li key={step} style={{ display: "flex", gap: 8.4, alignItems: "baseline" }}>
                  <span aria-hidden style={{ color: ACC }}>
                    ›
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8.4, alignItems: "center" }}>
            <button type="button" className="btn btn-primary" onClick={run}>
              Ler currículo
            </button>
            <button type="button" className="btn btn-ghost" onClick={onRestart}>
              Enviar outro arquivo
            </button>
          </div>
        )}
      </Panel>
    </>
  );
}


/**
 * Passo 3 e 4: revisar o que a IA leu e importar.
 *
 * Cada tecnologia mostra a FRASE do currículo que sustentou a estimativa.
 * Sem isso a pessoa não tem como julgar se um "nível 4 em Java" veio de três
 * anos liderando ou de uma linha na lista de palavras-chave.
 */
function Review({ resume, onDone }: { resume: Resume; onDone: () => void }) {
  const parsed = "tecnologias" in resume.parsed ? resume.parsed : null;
  const [technologies, setTechnologies] = useState<ParsedTechnology[]>(
    parsed?.tecnologias ?? [],
  );
  const [dropped, setDropped] = useState<Set<string>>(new Set());
  const apply = useMutation(() =>
    resumesApi.apply(resume.id, {
      tecnologias: technologies.filter((item) => !dropped.has(item.nome)),
      aplicar_perfil: true,
    }),
  );

  const kept = technologies.filter((item) => !dropped.has(item.nome));

  async function confirm() {
    const result = await apply.run();
    if (result) onDone();
  }

  return (
    <>
      <h1 style={{ fontSize: 32, margin: "0 0 8.4px" }}>Revise o que eu li</h1>
      <p style={{ maxWidth: "62ch", color: "rgba(233,233,237,.7)", fontSize: 14 }}>
        Estimei o nível de cada tecnologia pelo tempo de uso e pela responsabilidade descrita.
        Ajuste o que estiver errado — o plano é montado a partir disto.
      </p>

      {apply.error ? <ErrorState message={apply.error} onRetry={confirm} /> : null}

      <div
        style={{
          marginTop: 22.4,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))",
          gap: 11.2,
        }}
      >
        <Panel>
          <Kicker style={{ display: "block", marginBottom: 11.2 }}>Extraído do currículo</Kicker>
          <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>
            {[
              { label: "Nome", value: parsed?.nome },
              { label: "Cargo atual", value: parsed?.cargo_atual },
              { label: "Senioridade", value: parsed?.senioridade },
              {
                label: "Experiência",
                value: parsed?.anos_experiencia ? `${parsed.anos_experiencia} anos` : "",
              },
              { label: "Cidade", value: parsed?.cidade },
            ]
              .filter((field) => field.value)
              .map((field) => (
                <div key={field.label}>
                  <div style={{ fontSize: 11, color: TEXT.muted, marginBottom: 2.8 }}>
                    {field.label}
                  </div>
                  <div style={{ fontSize: 14 }}>{field.value}</div>
                </div>
              ))}
          </div>
        </Panel>

        <Panel style={{ gridColumn: "span 2" }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "baseline",
              gap: 8.4,
              marginBottom: 11.2,
            }}
          >
            <Kicker>Tecnologias · {kept.length}</Kicker>
            <span style={{ fontSize: 11.5, color: TEXT.muted }}>
              ajuste o nível ou remova o que não faz parte do plano
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 5.6 }}>
            {technologies.map((technology) => (
              <TechnologyRow
                key={technology.nome}
                technology={technology}
                dropped={dropped.has(technology.nome)}
                onLevel={(level) =>
                  setTechnologies((current) =>
                    current.map((item) =>
                      item.nome === technology.nome ? { ...item, proficiencia: level } : item,
                    ),
                  )
                }
                onToggle={() =>
                  setDropped((current) => {
                    const next = new Set(current);
                    if (next.has(technology.nome)) next.delete(technology.nome);
                    else next.add(technology.nome);
                    return next;
                  })
                }
              />
            ))}
          </div>

          <div
            style={{
              marginTop: 16.8,
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: 11.2,
            }}
          >
            <button
              type="button"
              className="btn btn-primary"
              onClick={confirm}
              disabled={apply.pending || kept.length === 0}
            >
              {apply.pending ? "Importando…" : `Importar ${kept.length} competências`}
            </button>
            <span style={{ fontSize: 12, color: TEXT.muted }}>
              {kept.filter((item) => item.proficiencia === 0).length} entram como meta de estudo
            </span>
          </div>
        </Panel>
      </div>

      <p style={{ marginTop: 14, fontSize: 11.5, color: TEXT.faint }}>
        Escala: {MASTERY_LABELS.map((label, index) => `N${index} ${label}`).join(" · ")}
      </p>
    </>
  );
}
