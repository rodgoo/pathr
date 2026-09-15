/**
 * O desafio anti-robô do cadastro (Cloudflare Turnstile).
 *
 * Só existe quando `VITE_TURNSTILE_SITE_KEY` está configurada — sem ela o
 * componente não desenha nada e o cadastro segue como sempre. Na maioria das
 * vezes o Turnstile resolve sozinho, sem pedir clique: a pessoa real nem nota,
 * e o script que cria contas em série para.
 *
 * O token vale uma vez. Depois de um envio que falhou (senha fraca, e-mail
 * recusado), a tela troca a `key` do componente e ele pede um novo.
 */

import { useEffect, useRef } from "react";

const SITE_KEY = (import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined) ?? "";
const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render: (elemento: HTMLElement, opcoes: Record<string, unknown>) => string;
  remove: (id: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

export const turnstileLigado = Boolean(SITE_KEY);

let carregando: Promise<void> | null = null;

function carregarScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (!carregando) {
    carregando = new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = SCRIPT;
      tag.async = true;
      tag.onload = () => resolve();
      tag.onerror = () => {
        carregando = null;
        reject(new Error("turnstile"));
      };
      document.head.appendChild(tag);
    });
  }
  return carregando;
}

export function Turnstile({ onToken }: { onToken: (token: string | null) => void }) {
  const caixa = useRef<HTMLDivElement>(null);
  const aviso = useRef(onToken);
  aviso.current = onToken;

  useEffect(() => {
    if (!SITE_KEY) return;
    let id: string | null = null;
    let vivo = true;
    void carregarScript()
      .then(() => {
        if (!vivo || !caixa.current || !window.turnstile) return;
        id = window.turnstile.render(caixa.current, {
          sitekey: SITE_KEY,
          theme: "dark",
          language: "pt-br",
          callback: (token: string) => aviso.current(token),
          "expired-callback": () => aviso.current(null),
          "error-callback": () => aviso.current(null),
        });
      })
      .catch(() => aviso.current(null));
    return () => {
      vivo = false;
      if (id && window.turnstile) window.turnstile.remove(id);
    };
  }, []);

  if (!SITE_KEY) return null;
  return <div ref={caixa} style={{ margin: "4px 0 12px", minHeight: 65 }} />;
}
