/**
 * A moldura das páginas legais: termos, privacidade e segurança.
 *
 * Abrem com ou sem sessão, e sem chamar a API: são texto. Quem ainda não tem
 * conta precisa ler o que aceita ANTES de criar uma, e quem já tem precisa
 * achar o mesmo texto de dentro das configurações.
 *
 * O texto de cada página mora em um arquivo próprio (Termos.tsx,
 * Privacidade.tsx, Seguranca.tsx) como dados; aqui fica só a forma — topo,
 * abas entre os três documentos, resumo, sumário com âncoras e seções. Uma
 * forma só é um lugar só para acertar responsividade e acessibilidade.
 */

import { useEffect, type MouseEvent, type ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";
import { SeletorDeIdioma } from "@/components/ui/SeletorDeIdioma";
import { useT } from "@/lib/i18n";
import { ACC, ACC3, ACC4, BG, C, HAIRLINE, PANEL, TEXT } from "@/lib/tokens";

export type Navegar = (path: string) => void;

export interface Secao {
  /** Âncora da seção (sem #). */
  id: string;
  titulo: string;
  corpo: ReactNode;
}

export interface DocumentoLegal {
  path: string;
  /** Rótulo curto da aba. */
  aba: string;
  kicker: string;
  titulo: string;
  introducao: string;
  /** Os pontos do "Em resumo", no topo. */
  resumo: string[];
  secoes: Secao[];
}

export const ULTIMA_ATUALIZACAO = "13 de setembro de 2026";

// Um lugar só para quem opera esta instalação: ver lib/operador.ts. O
// reexport mantém quem já importava daqui.
import { EMAIL_CONTATO, OPERADOR } from "@/lib/operador";

export { EMAIL_CONTATO, OPERADOR };

// ---------------------------------------------------------------------------
// Peças de texto, usadas pelos três documentos
// ---------------------------------------------------------------------------

export function P({ children }: { children: ReactNode }) {
  return <p style={{ margin: "0 0 14px", fontSize: 15, lineHeight: 1.75, color: TEXT.strong }}>{children}</p>;
}

export function Lista({ itens }: { itens: ReactNode[] }) {
  return (
    <ul style={{ margin: "0 0 16px", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
      {itens.map((item, indice) => (
        <li key={indice} style={{ display: "flex", gap: 10, fontSize: 15, lineHeight: 1.7, color: TEXT.strong }}>
          <span aria-hidden style={{ flex: "none", width: 5, height: 5, borderRadius: "50%", background: ACC, marginTop: 11 }} />
          <span style={{ minWidth: 0 }}>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function Forte({ children }: { children: ReactNode }) {
  return <strong style={{ color: TEXT.full, fontWeight: 600 }}>{children}</strong>;
}

export function Subtitulo({ children }: { children: ReactNode }) {
  return <h3 style={{ fontSize: 16, fontWeight: 600, margin: "22px 0 10px", color: TEXT.full }}>{children}</h3>;
}

/** Um bloco de destaque: o que vale a pena não perder de vista. */
export function Nota({ children, tom = "acento" }: { children: ReactNode; tom?: "acento" | "atencao" }) {
  const cor = tom === "atencao" ? C.ambar : ACC;
  return (
    <div
      style={{
        margin: "4px 0 18px",
        padding: "12px 16px",
        borderRadius: 10,
        background: tom === "atencao" ? "rgba(207,162,94,.08)" : "rgba(145,132,217,.08)",
        borderLeft: `2px solid ${cor}`,
        fontSize: 14.5,
        lineHeight: 1.7,
        color: TEXT.strong,
      }}
    >
      {children}
    </div>
  );
}

/**
 * Uma lista de itens com nome, finalidade e detalhe — os provedores, os
 * limites de uso. Cartões, e não tabela: numa tela de 400px uma tabela de três
 * colunas vira rolagem lateral, e o cartão só empilha.
 */
export function Fichas({ itens }: { itens: { nome: string; papel: string; detalhe: ReactNode }[] }) {
  return (
    <ul
      style={{
        margin: "0 0 18px",
        padding: 0,
        listStyle: "none",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 250px), 1fr))",
        gap: 10,
      }}
    >
      {itens.map((item) => (
        <li
          key={item.nome}
          style={{ padding: "14px 16px", borderRadius: 12, background: PANEL, boxShadow: `inset 0 0 0 1px ${HAIRLINE}`, minWidth: 0 }}
        >
          <div style={{ fontSize: 14.5, fontWeight: 600, color: TEXT.full }}>{item.nome}</div>
          <div style={{ fontSize: 12, color: ACC4, marginTop: 3, letterSpacing: ".01em" }}>{item.papel}</div>
          <div style={{ fontSize: 13.5, color: TEXT.muted, marginTop: 8, lineHeight: 1.6 }}>{item.detalhe}</div>
        </li>
      ))}
    </ul>
  );
}

/**
 * Link de um documento para outro. Carrega a página inteira em vez de trocar
 * em memória: é raro, e poupa passar a navegação por todo o texto.
 */
export function LinkDoc({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} className="lg-link-interno">
      {children}
    </a>
  );
}

export function EmailContato() {
  return (
    <a href={`mailto:${EMAIL_CONTATO}`} style={{ color: ACC3 }}>
      {EMAIL_CONTATO}
    </a>
  );
}

// ---------------------------------------------------------------------------
// Moldura
// ---------------------------------------------------------------------------

const ESTILO = `
.lg-link-interno { color: ${ACC3}; }
.lg-aba { display: inline-flex; align-items: center; padding: 8px 14px; border-radius: 999px; font-size: 13.5px;
  color: ${TEXT.muted}; text-decoration: none; box-shadow: inset 0 0 0 1px ${HAIRLINE}; white-space: nowrap; }
.lg-aba:hover { color: ${TEXT.full}; }
.lg-aba[aria-current="page"] { color: ${TEXT.full}; background: rgba(145,132,217,.16); box-shadow: inset 0 0 0 1px ${ACC}; }
.lg-aba:focus-visible, .lg-sumario a:focus-visible, .lg-voltar:focus-visible { outline: 2px solid ${ACC4}; outline-offset: 2px; }
.lg-grade { display: grid; grid-template-columns: minmax(0, 1fr); gap: 28px; align-items: start; }
.lg-sumario a { display: block; padding: 6px 10px; border-radius: 8px; color: ${TEXT.muted}; text-decoration: none; font-size: 13.5px; line-height: 1.45; }
.lg-sumario a:hover { color: ${TEXT.full}; background: rgba(233,233,237,.05); }
.lg-sumario-largo { display: none; }
.lg-secao { scroll-margin-top: 84px; }
.lg-voltar { color: ${TEXT.muted}; text-decoration: none; font-size: 13.5px; }
.lg-voltar:hover { color: ${TEXT.full}; }
@media (min-width: 960px) {
  .lg-grade { grid-template-columns: 250px minmax(0, 1fr); gap: 56px; }
  .lg-sumario-largo { display: block; position: sticky; top: 84px; }
  .lg-sumario-estreito { display: none; }
}
`;

function linkInterno(path: string, onNavigate: Navegar) {
  return {
    href: path,
    onClick: (evento: MouseEvent<HTMLAnchorElement>) => {
      // Ctrl/Cmd+clique continua abrindo em aba nova, como qualquer link.
      if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.button !== 0) return;
      evento.preventDefault();
      onNavigate(path);
    },
  };
}

function Sumario({ secoes }: { secoes: Secao[] }) {
  return (
    <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {secoes.map((secao, indice) => (
        <li key={secao.id}>
          <a href={`#${secao.id}`}>
            <span style={{ color: TEXT.faint, marginRight: 8, fontVariantNumeric: "tabular-nums" }}>{indice + 1}.</span>
            {secao.titulo}
          </a>
        </li>
      ))}
    </ol>
  );
}

export function LegalLayout({
  documento,
  documentos,
  onNavigate,
}: {
  documento: DocumentoLegal;
  documentos: DocumentoLegal[];
  onNavigate: Navegar;
}) {
  const t = useT();

  useEffect(() => {
    const anterior = document.title;
    document.title = `${documento.titulo} · PathR`;
    // Trocar de documento pela aba começa do topo, não da altura em que se
    // estava lendo o anterior.
    if (!window.location.hash) document.documentElement.scrollTop = 0;
    return () => {
      document.title = anterior;
    };
  }, [documento]);

  return (
    <div style={{ minHeight: "100dvh", background: BG, color: TEXT.full, fontFamily: "Inter, system-ui, sans-serif" }}>
      <style>{ESTILO}</style>

      <header
        style={{
          position: "sticky", top: 0, zIndex: 10,
          display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
          padding: "14px clamp(16px, 4vw, 40px)",
          background: "rgba(0,0,0,.8)", backdropFilter: "blur(10px)",
          borderBottom: `1px solid ${HAIRLINE}`,
        }}
      >
        <a {...linkInterno("/", onNavigate)} style={{ display: "flex", alignItems: "center", gap: 10, color: TEXT.full, textDecoration: "none" }}>
          <Logo size={28} />
          <span style={{ fontSize: 17, fontWeight: 600 }}>PathR</span>
        </a>
        <a {...linkInterno("/", onNavigate)} className="lg-voltar" style={{ marginLeft: "auto" }}>
          <span aria-hidden>← </span>
          {t("legal.layout.voltar")}
        </a>
      </header>

      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "0 clamp(16px, 4vw, 40px)" }}>
        <nav aria-label={t("legal.layout.abasAria")} style={{ display: "flex", gap: 8, flexWrap: "wrap", padding: "24px 0 0" }}>
          {documentos.map((outro) => (
            <a
              key={outro.path}
              {...linkInterno(outro.path, onNavigate)}
              className="lg-aba"
              aria-current={outro.path === documento.path ? "page" : undefined}
            >
              {outro.aba}
            </a>
          ))}
        </nav>

        <header style={{ padding: "clamp(28px, 6vw, 56px) 0 clamp(24px, 4vw, 36px)", maxWidth: "72ch" }}>
          <div style={{ fontSize: 11.5, letterSpacing: ".14em", textTransform: "uppercase", color: ACC4, fontWeight: 600 }}>
            {documento.kicker}
          </div>
          <h1 style={{ fontSize: "clamp(30px, 5vw, 46px)", lineHeight: 1.1, letterSpacing: "-.03em", fontWeight: 650, margin: "14px 0 14px" }}>
            {documento.titulo}
          </h1>
          <p style={{ fontSize: "clamp(15.5px, 1.6vw, 17px)", lineHeight: 1.7, color: TEXT.muted, margin: 0 }}>{documento.introducao}</p>
          <p style={{ fontSize: 13, color: TEXT.faint, margin: "14px 0 0" }}>
            {t("legal.layout.ultimaAtualizacao")} <time dateTime="2026-09-13">{ULTIMA_ATUALIZACAO}</time>
          </p>
        </header>

        <section
          aria-labelledby="lg-resumo"
          style={{
            padding: "clamp(18px, 3vw, 26px)",
            borderRadius: 18,
            background: `radial-gradient(120% 140% at 0% 0%, rgba(145,132,217,.16), transparent 60%), ${PANEL}`,
            boxShadow: `inset 0 0 0 1px ${HAIRLINE}`,
            marginBottom: "clamp(28px, 5vw, 48px)",
          }}
        >
          <h2 id="lg-resumo" style={{ fontSize: 18, fontWeight: 600, margin: "0 0 14px" }}>{t("legal.layout.resumoTitulo")}</h2>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))", gap: "10px 28px" }}>
            {documento.resumo.map((ponto) => (
              <li key={ponto} style={{ display: "flex", gap: 10, fontSize: 14.5, lineHeight: 1.6, color: TEXT.strong }}>
                <span aria-hidden style={{ color: C.verde, flex: "none" }}>✓</span>
                <span style={{ minWidth: 0 }}>{ponto}</span>
              </li>
            ))}
          </ul>
        </section>

        <div className="lg-grade">
          <aside className="lg-sumario lg-sumario-largo">
            <nav aria-label={t("legal.layout.nestaPagina")}>
              <div style={{ fontSize: 11.5, letterSpacing: ".14em", textTransform: "uppercase", color: TEXT.faint, fontWeight: 600, margin: "0 0 10px 10px" }}>
                {t("legal.layout.nestaPagina")}
              </div>
              <Sumario secoes={documento.secoes} />
            </nav>
          </aside>

          <main style={{ minWidth: 0, maxWidth: "74ch" }}>
            <details className="lg-sumario lg-sumario-estreito" style={{ marginBottom: 28, padding: "12px 14px", borderRadius: 12, boxShadow: `inset 0 0 0 1px ${HAIRLINE}` }}>
              <summary style={{ cursor: "pointer", fontSize: 14, color: TEXT.strong }}>{t("legal.layout.nestaPagina")}</summary>
              <nav aria-label={t("legal.layout.nestaPaginaCompacta")} style={{ marginTop: 8 }}>
                <Sumario secoes={documento.secoes} />
              </nav>
            </details>

            {documento.secoes.map((secao, indice) => (
              <section key={secao.id} id={secao.id} className="lg-secao" aria-labelledby={`${secao.id}-titulo`} style={{ paddingBottom: 28, marginBottom: 28, borderBottom: `1px solid ${HAIRLINE}` }}>
                <h2 id={`${secao.id}-titulo`} style={{ fontSize: "clamp(20px, 2.4vw, 24px)", fontWeight: 600, letterSpacing: "-.015em", margin: "0 0 14px", lineHeight: 1.3 }}>
                  <span style={{ color: ACC, marginRight: 10, fontVariantNumeric: "tabular-nums" }}>{indice + 1}.</span>
                  {secao.titulo}
                </h2>
                {secao.corpo}
              </section>
            ))}

            <p style={{ fontSize: 14, color: TEXT.muted, lineHeight: 1.7, margin: "0 0 8px" }}>
              {t("legal.layout.duvidas")} <EmailContato />.
            </p>
          </main>
        </div>
      </div>

      <footer style={{ maxWidth: 1120, margin: "0 auto", padding: "40px clamp(16px, 4vw, 40px) 48px", display: "flex", flexWrap: "wrap", gap: "10px 18px", alignItems: "center", color: TEXT.faint, fontSize: 13 }}>
        <Logo size={20} />
        <span>{t("legal.layout.rodapeMarca")}</span>
        <nav aria-label={t("legal.layout.rodapeAria")} style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px", marginLeft: "auto" }}>
          {documentos.map((outro) => (
            <a key={outro.path} {...linkInterno(outro.path, onNavigate)} style={{ color: TEXT.muted, textDecoration: "none" }}>
              {outro.aba}
            </a>
          ))}
        </nav>
      </footer>

      {/* Uma moldura só para os três documentos: o seletor entra aqui uma vez e
          vale para termos, privacidade e segurança. Quem chega a estas páginas
          pode não ter conta — a escolha fica no aparelho. */}
      <SeletorDeIdioma flutuante />
    </div>
  );
}
