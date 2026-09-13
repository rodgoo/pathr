/**
 * Perfil e competências.
 *
 * Os dois grupos de tags são a ideia do produto tornada visível: o que já
 * está comprovado (contorno cheio) contra o que o plano ainda deve
 * (tracejado). Clicar em qualquer um marca ou desmarca como meta de estudo —
 * e isso muda o roadmap na próxima geração.
 */

import type { CSSProperties } from "react";
import { courses as coursesApi, profile as profileApi, tags as tagsApi } from "@/api/endpoints";
import type { OwnedCourse, UserTag } from "@/api/types";
import { useAppState } from "@/hooks/useAppState";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@/hooks/useApi";
import { ACC, ACC4, C, HAIRLINE, TEXT } from "@/lib/tokens";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Kicker, Meter, Panel, SCREEN_IN } from "@/components/ui/primitives";
import { Avatar } from "@/components/profile/Avatar";
import { TagButton } from "@/components/profile/TagButton";
import { MASTERY_LABELS } from "@/components/profile/TechnologyRow";
import { Icon } from "@/components/ui/icons";
import { linkParaLinkedIn } from "@/pages/CoursesPage";

import { linkExterno } from "@/lib/linkExterno";
export function ProfilePage() {
  const { user } = useAuth();
  const { dispatch } = useAppState();
  const overview = useQuery((signal) => profileApi.overview(signal), []);
  const tags = useQuery(() => tagsApi.mine(), []);
  const certificados = useQuery(() => coursesApi.mine(), []);

  if (overview.loading || tags.loading) return <Loading label="Carregando seu perfil…" />;
  if (overview.error) return <ErrorState message={overview.error} onRetry={overview.reload} />;
  if (tags.error) return <ErrorState message={tags.error} onRetry={tags.reload} />;
  if (!overview.data || !tags.data) return null;

  const { profile, streak, roadmap } = overview.data;

  // Os três grupos são os MESMOS do gerador de roadmap (ver
  // backend/app/services/roadmap_builder.py: build_prompt). Antes a tela
  // dividia em "tem nível" e "não tem", o que juntava N1 com N5 e sugeria que
  // só o N0 entrava no plano — duas afirmações falsas.
  //
  // Nenhum nível fica de fora: o que muda é a FORMA do módulo. Até N2 é
  // ensino; de N3 para cima é revisão curta. A ordem abaixo é a ordem em que
  // o plano ataca os assuntos.
  // O idioma tem nível próprio (CEFR), medido e mostrado no módulo de Idiomas.
  const tecnicas = tags.data.filter((tag) => tag.category !== "idioma");
  const dominadas = tecnicas.filter((tag) => tag.proficiency >= 3);
  const parciais = tecnicas.filter((tag) => tag.proficiency > 0 && tag.proficiency < 3);
  const doZero = tecnicas.filter((tag) => tag.proficiency === 0);

  const toggle = async (tagId: string, next: boolean) => {
    // Atualiza a tela antes da resposta: a escrita é pequena e previsível, e
    // esperar o servidor para pintar um botão já clicado faz a interface
    // parecer travada.
    tags.set((current) =>
      current.map((tag) => (tag.id === tagId ? { ...tag, is_target: next } : tag)),
    );
    await tagsApi.update(tagId, { is_target: next });
  };

  return (
    <div style={SCREEN_IN}>
      <h1 style={{ fontSize: 28, margin: "0 0 5.6px" }}>Perfil e tags</h1>
      <p
        style={{
          margin: "0 0 16.8px",
          fontSize: 13.5,
          color: "rgba(233,233,237,.6)",
          maxWidth: "62ch",
        }}
      >
        O que está marcado aqui alimenta o roadmap. Desmarcar uma tag tira os módulos ligados a ela
        da próxima geração; marcar uma nova recalcula o prazo.
      </p>

      <IdentityCard
        name={user?.name ?? ""}
        username={user?.username ?? ""}
        profile={profile}
        streak={streak}
        roadmap={roadmap}
        onEdit={() => dispatch({ type: "navigate", screen: "config", settingsTab: "conta" })}
      />

      {tecnicas.length === 0 ? (
        <EmptyState
          title="Nenhuma competência ainda"
          description="Envie seu currículo para eu extrair as tecnologias, ou adicione uma a uma em Configurações, aba Skills."
          action={
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => dispatch({ type: "navigate", screen: "cv" })}
            >
              <Icon name="upload" size={15} />
              Enviar currículo
            </button>
          }
        />
      ) : (
        <Panel pad={16.8}>
          <TagGroup
            title={`Você domina · ${dominadas.length}`}
            hint="N3 ou mais — entram como revisão curta: o caso difícil, a armadilha de produção e exercícios de nível avançado. Nunca do zero"
            tags={dominadas}
            onToggle={toggle}
          />
          <TagGroup
            title={`O plano começa por aqui · ${parciais.length}`}
            hint="N1 e N2 — entram para aprofundar, e vêm primeiro: a distância é curta e o resultado aparece nas primeiras semanas"
            tags={parciais}
            onToggle={toggle}
            style={{ marginTop: 16.8 }}
          />
          <TagGroup
            title={`Do zero · ${doZero.length}`}
            hint="N0 — também entram. O que o objetivo exige vai cedo, por ser o mais longo; o resto fica para o fim e é o primeiro a sair se as horas não fecharem"
            tags={doZero}
            dashed
            onToggle={toggle}
            style={{ marginTop: 16.8 }}
          />
          <ScaleLegend />
        </Panel>
      )}

      <Certificados
        lista={certificados.data ?? []}
        carregando={certificados.loading}
        onVerCursos={() => dispatch({ type: "navigate", screen: "cursos" })}
      />
    </div>
  );
}


/**
 * Os certificados que a pessoa marcou como "já possuo" na aba Cursos.
 *
 * Moram aqui, e não só em Cursos, porque são credencial: o que se tem, junto
 * das competências. O atalho para o LinkedIn fica em cada um — é para isso
 * que a pessoa foi atrás do certificado.
 */
function Certificados({
  lista,
  carregando,
  onVerCursos,
}: {
  lista: OwnedCourse[];
  carregando: boolean;
  onVerCursos: () => void;
}) {
  return (
    <Panel pad={16.8} style={{ marginTop: 11.2 }}>
      <section aria-label="Certificados">
        {/* "Ver cursos" na linha do título, e a explicação embaixo: com os três
            na mesma linha flexível, no celular o botão sobrava sozinho numa
            linha própria. */}
        <div style={{ display: "flex", alignItems: "center", gap: 8.4 }}>
          <Kicker>{`Certificados · ${lista.length}`}</Kicker>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ marginLeft: "auto", fontSize: 12.5, flex: "none" }}
            onClick={onVerCursos}
          >
            <Icon name="award" size={15} />
            Ver cursos
          </button>
        </div>
        <p style={{ margin: "2px 0 8.4px", fontSize: 11.5, color: TEXT.faint }}>
          Marcados como "já possuo" na aba Cursos
        </p>
        {carregando ? null : lista.length === 0 ? (
          <p style={{ margin: 0, fontSize: 12.5, color: TEXT.muted }}>
            Nenhum ainda. Em Cursos, marque "Já possuo" nos certificados que você tem.
          </p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {lista.map((curso, posicao) => (
              <li
                key={curso.id}
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: "4px 11.2px",
                  padding: "8.4px 0",
                  borderTop: posicao === 0 ? "none" : `1px solid ${HAIRLINE}`,
                }}
              >
                <Icon name="award" size={16} style={{ color: curso.gratuito ? C.verde : C.ambar, flex: "none" }} />
                <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                  <a href={linkExterno(curso.url)} target="_blank" rel="noreferrer noopener" style={{ color: TEXT.full, fontSize: 14 }}>
                    {curso.titulo}
                  </a>
                  <div style={{ fontSize: 12, color: TEXT.muted }}>
                    {curso.emissor}
                    {curso.tags.length ? ` · ${curso.tags.join(", ")}` : ""}
                  </div>
                </div>
                <a
                  href={linkParaLinkedIn(curso)}
                  target="_blank"
                  rel="noreferrer noopener"
                  style={{ fontSize: 12.5, color: ACC }}
                >
                  Adicionar ao LinkedIn
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Panel>
  );
}

function IdentityCard({
  name,
  username,
  profile,
  streak,
  roadmap,
  onEdit,
}: {
  name: string;
  username: string;
  profile: import("@/api/types").Profile;
  streak: import("@/api/types").Streak;
  roadmap: import("@/api/types").RoadmapSummary | null;
  onEdit: () => void;
}) {
  const fields = [
    { label: "Cargo", value: profile.current_role },
    { label: "Senioridade", value: profile.seniority },
    {
      label: "Experiência",
      value: profile.years_experience ? `${profile.years_experience} anos` : null,
    },
    { label: "Disponibilidade", value: `${profile.weekly_hours}h por semana` },
    { label: "Sequência", value: `${streak.current} dias` },
    { label: "XP", value: String(streak.total_xp) },
  ].filter((field) => field.value);

  return (
    <Panel
      tone="section"
      pad={16.8}
      style={{ marginBottom: 11.2, display: "flex", flexDirection: "column", gap: 11.2 }}
    >
      {/* Foto, nome e "Editar perfil" numa linha que nunca quebra. Antes o
          bloco de texto tinha largura mínima e, no celular, descia inteiro
          para baixo da foto — deixando um vão vazio ao lado dela. */}
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <Avatar nome={name} editavel />
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
          {/* O @ embaixo do nome: é por ele que as outras contas te acham, e
              ele precisa estar à vista no lugar onde a pessoa se reconhece. */}
          <span style={{ fontSize: 22, lineHeight: 1.2, overflowWrap: "anywhere" }}>{name}</span>
          {username ? <span style={{ fontSize: 13, color: ACC4, marginTop: -4 }}>@{username}</span> : null}
          <button type="button" className="btn btn-ghost" style={{ fontSize: 12.5, marginTop: 2 }} onClick={onEdit}>
            <Icon name="pencil" size={15} />
            Editar perfil
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 11.2 }}>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(128px,1fr))",
            gap: 11.2,
          }}
        >
          {fields.map((field) => (
            <div key={field.label} style={{ minWidth: 0 }}>
              <div style={{ fontSize: 10.5, color: TEXT.muted }}>{field.label}</div>
              <div style={{ fontSize: 14 }}>{field.value}</div>
            </div>
          ))}
        </div>

        {roadmap ? (
          <div style={{ paddingTop: 11.2, borderTop: "1px solid rgba(233,233,237,.14)" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "baseline",
                gap: 8.4,
                marginBottom: 5.6,
              }}
            >
              <span style={{ fontSize: 12.5, color: "rgba(233,233,237,.7)" }}>{roadmap.title}</span>
              <span style={{ marginLeft: "auto", fontSize: 11.5, color: TEXT.muted }}>
                {roadmap.done_nodes} de {roadmap.total_nodes} · {roadmap.progress_pct}%
              </span>
            </div>
            <Meter pct={roadmap.progress_pct} color={ACC4} height={4} label="Progresso do plano" />
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function TagGroup({
  title,
  hint,
  tags,
  dashed,
  onToggle,
  style,
}: {
  title: string;
  hint: string;
  tags: UserTag[];
  dashed?: boolean;
  onToggle: (tagId: string, next: boolean) => void;
  style?: CSSProperties;
}) {
  return (
    <div style={style}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "baseline",
          gap: 8.4,
          marginBottom: 11.2,
        }}
      >
        <Kicker>{title}</Kicker>
        <span style={{ fontSize: 11.5, color: TEXT.faint }}>{hint}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5.6 }}>
        {tags.map((tag) => (
          <TagButton
            key={tag.id}
            tag={tag}
            dashed={dashed}
            onToggle={() => onToggle(tag.id, !tag.is_target)}
          />
        ))}
      </div>
    </div>
  );
}

function ScaleLegend() {
  return (
    <div style={{ marginTop: 16.8, paddingTop: 14, borderTop: "1px solid rgba(233,233,237,.12)" }}>
      <Kicker tone="muted" style={{ display: "block", marginBottom: 8.4 }}>
        Escala de domínio
      </Kicker>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
          gap: 8.4,
        }}
      >
        {MASTERY_LABELS.map((label, level) => (
          <div key={label} style={{ display: "flex", alignItems: "baseline", gap: 6, minWidth: 0 }}>
            <span
              style={{ fontSize: 11, fontFamily: "ui-monospace, Menlo, monospace", color: ACC4 }}
            >
              N{level}
            </span>
            <span style={{ fontSize: 12.5 }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
