/**
 * Moldura das telas de entrada.
 *
 * Um cartão sobre o fundo preto, com a marca em cima e um brilho difuso do
 * acento atrás — o preto AMOLED continua sendo o chão. Em tela larga, um
 * painel ao lado diz em três linhas o que a pessoa ganha ao entrar; no celular
 * ele some e fica só o cartão.
 *
 * Diferente do AppShell de propósito: aqui não existe navegação, e mostrar uma
 * barra lateral com links que a pessoa ainda não pode abrir só confunde.
 *
 * O visual mora em `styles/auth.css`, tudo sob `.auth`: os campos e botões
 * ficam mais altos e o primário ganha fundo cheio só nestas telas.
 */

import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useT } from "@/lib/i18n";
import { C, TEXT } from "@/lib/tokens";
import { Icon, type IconName } from "@/components/ui/icons";
import { Logo } from "@/components/ui/Logo";
import { Select, type SelectOption } from "@/components/ui/Select";
import "@/styles/auth.css";

// Título e detalhe de cada benefício vêm do dicionário (authShell.beneficios.<chave>).
const BENEFICIOS: readonly { icone: IconName; tom: string; chave: string }[] = [
  { icone: "refresh", tom: C.azul, chave: "plano" },
  { icone: "flag", tom: C.verde, chave: "idioma" },
  { icone: "suitcase", tom: C.ambar, chave: "vagas" },
];

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  icon,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Símbolo do cartão, ao lado do título. */
  icon?: IconName;
}) {
  const t = useT();
  return (
    <div className="auth">
      <div className="auth-brilho" aria-hidden="true" />

      <div className="auth-grade">
        <div className="auth-painel">
          <span className="auth-kicker">
            <Icon name="road" size={13} />
            {t("authShell.kicker")}
          </span>
          <p className="auth-painel-titulo">
            {t("authShell.tituloPre")} <em>{t("authShell.tituloEnfase")}</em>
          </p>
          <p className="auth-painel-texto">
            {t("authShell.descricao")}
          </p>
          <ul className="auth-beneficios">
            {BENEFICIOS.map((b) => (
              <li key={b.chave}>
                <span className="auth-beneficio-icone" style={{ "--tom": b.tom } as CSSProperties}>
                  <Icon name={b.icone} size={18} />
                </span>
                <span>
                  {t(`authShell.beneficios.${b.chave}.titulo`)}
                  <small>{t(`authShell.beneficios.${b.chave}.detalhe`)}</small>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="auth-coluna">
          <div className="auth-marca">
            <span className="auth-marca-logo">
              <Logo size={28} />
            </span>
            <div className="auth-marca-nome">
              <strong>PathR</strong>
              <span>pathr.notter.com.br</span>
            </div>
          </div>

          <div className="auth-cartao">
            <div className="auth-cabeca">
              {icon ? (
                <span className="auth-selo">
                  <Icon name={icon} size={20} />
                </span>
              ) : null}
              <div style={{ minWidth: 0 }}>
                <h1 className="auth-titulo">{title}</h1>
                {subtitle ? <p className="auth-subtitulo">{subtitle}</p> : null}
              </div>
            </div>
            {children}
          </div>

          {footer ? <div className="auth-rodape">{footer}</div> : null}
        </div>
      </div>
    </div>
  );
}

/**
 * Símbolo à esquerda de um campo. Decorativo: o rótulo já diz o que é.
 */
function SimboloDoCampo({ icon }: { icon?: IconName }) {
  if (!icon) return null;
  return (
    <span className="campo-icone-simbolo">
      <Icon name={icon} size={17} />
    </span>
  );
}

/**
 * Aviso de erro do formulário.
 *
 * `role="alert"` para o leitor de tela anunciar sem a pessoa ter que procurar
 * — quem envia um formulário e não vê nada acontecer precisa saber por quê.
 */
export function FormError({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p
      role="alert"
      style={{
        margin: "0 0 11.2px",
        padding: "8.4px 11.2px",
        borderRadius: 8,
        background: "rgba(207,162,94,.12)",
        borderLeft: "2px solid #cfa25e",
        fontSize: 13,
        color: "rgba(233,233,237,.85)",
      }}
    >
      {children}
    </p>
  );
}

export function Field({
  id,
  label,
  hint,
  icon,
  ...input
}: {
  id: string;
  label: string;
  hint?: string;
  /** Símbolo decorativo à esquerda do texto. */
  icon?: IconName;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="field" style={{ marginBottom: 11.2 }}>
      <label htmlFor={id}>{label}</label>
      {icon ? (
        <div className="campo-icone">
          <SimboloDoCampo icon={icon} />
          <input id={id} className="input" {...input} />
        </div>
      ) : (
        <input id={id} className="input" {...input} />
      )}
      {hint ? (
        <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4 }}>{hint}</div>
      ) : null}
    </div>
  );
}

/**
 * Campo de senha com botão de mostrar/ocultar.
 *
 * Existe porque digitar uma senha longa às cegas, num teclado de celular que
 * corrige sozinho, é a forma mais comum de errar a senha que se sabe. Ver o
 * que se digitou resolve isso sem enfraquecer nada: o valor já está na
 * memória do navegador, e mostrá-lo só expõe para quem está olhando a tela.
 *
 * O botão é um `button` de verdade, alcançável pelo teclado, com
 * `aria-pressed` dizendo o estado — um ícone que muda de desenho não
 * comunica nada a quem usa leitor de tela.
 *
 * O campo volta a ficar oculto quando desmonta: o estado não é global nem
 * persistido, então trocar de tela nunca deixa uma senha visível para trás.
 */
export function PasswordField({
  id,
  label,
  hint,
  icon,
  style,
  ...input
}: {
  id: string;
  label: string;
  hint?: string;
  /** Símbolo decorativo à esquerda do texto. */
  icon?: IconName;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">) {
  const t = useT();
  const [visible, setVisible] = useState(false);

  return (
    <div className="field" style={{ marginBottom: 11.2 }}>
      <label htmlFor={id}>{label}</label>
      <div className={icon ? "campo-icone" : undefined} style={{ position: "relative" }}>
        <SimboloDoCampo icon={icon} />
        <input
          id={id}
          className="input"
          type={visible ? "text" : "password"}
          // Espaço para o botão: sem isso o texto passa por baixo dele. Cabe
          // a versão de 44px que o toque exige, não só a de 30 do mouse.
          style={{ paddingRight: 52, ...style }}
          {...input}
        />
        <button
          type="button"
          // O tamanho vem do CSS porque depende do ponteiro: 30px bastam para
          // o mouse, o dedo precisa de 44. Estilo inline não sabe disso.
          className="olho"
          onClick={() => setVisible((atual) => !atual)}
          aria-pressed={visible}
          aria-label={visible ? t("authShell.ocultarSenha") : t("authShell.mostrarSenha")}
          aria-controls={id}
          title={visible ? t("authShell.ocultarSenha") : t("authShell.mostrarSenha")}
          style={{
            position: "absolute",
            top: "50%",
            right: 6,
            transform: "translateY(-50%)",
            display: "grid",
            placeItems: "center",
            padding: 0,
            border: 0,
            borderRadius: 6,
            background: "transparent",
            color: TEXT.faint,
            cursor: "pointer",
          }}
        >
          <Icon name={visible ? "eyeOff" : "eye"} size={17} />
        </button>
      </div>
      {hint ? (
        <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4 }}>{hint}</div>
      ) : null}
    </div>
  );
}

/** Campo de seleção, com a mesma moldura do `Field` — e a lista do app. */
export function SelectField({
  id,
  label,
  hint,
  options,
  value,
  onChange,
  placeholder,
  required,
}: {
  id: string;
  label: string;
  hint?: string;
  options: readonly SelectOption<string>[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div className="field" style={{ marginBottom: 11.2 }}>
      <label htmlFor={id}>{label}</label>
      <Select
        id={id}
        options={options}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        name={id}
      />
      {hint ? (
        <div style={{ fontSize: 11, color: TEXT.faint, marginTop: 4 }}>{hint}</div>
      ) : null}
    </div>
  );
}
