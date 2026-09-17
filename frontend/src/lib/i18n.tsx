/**
 * O idioma da interface.
 *
 * ## Como o texto sai daqui
 *
 * Todo texto fixo do app mora em `src/i18n/pt.json`, que é a FONTE: escreve-se
 * nele, em português, e os outros quatro idiomas saem dali por tradução
 * (scripts/traduzir.mjs, DeepL). Na tela, `t("chave")` devolve o texto no
 * idioma ativo. Uma chave que ainda não foi traduzida cai no português em vez
 * de sumir — texto faltando é pior que texto no idioma errado.
 *
 * ## Quem escolhe
 *
 * - Sem conta: a escolha do seletor, guardada no aparelho; sem escolha, o
 *   idioma do navegador; sem nada disso, português.
 * - Com conta: o `locale` da conta, que é o que faz o idioma acompanhar a
 *   pessoa entre aparelhos. Quem troca em Configurações grava lá.
 *
 * ## Por que não uma biblioteca
 *
 * O que o app precisa é buscar uma chave e trocar `{nome}` por um valor. Uma
 * biblioteca de i18n traz plural por idioma, formatação ICU e carregamento em
 * cadeia — e custaria mais para ler e depurar do que as linhas abaixo. Número
 * e data continuam com `Intl`, que é do navegador.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import pt from "@/i18n/pt.json";

export const IDIOMAS = [
  { codigo: "pt", nome: "Português", nomeLocal: "Português (Brasil)" },
  { codigo: "en", nome: "English", nomeLocal: "English" },
  { codigo: "es", nome: "Español", nomeLocal: "Español" },
  { codigo: "fr", nome: "Français", nomeLocal: "Français" },
  { codigo: "de", nome: "Deutsch", nomeLocal: "Deutsch" },
] as const;

export type Idioma = (typeof IDIOMAS)[number]["codigo"];
export const IDIOMA_PADRAO: Idioma = "pt";

/** Chave no aparelho. Vale para quem ainda não entrou — quem tem conta carrega
 * o idioma no `locale` dela. */
const CHAVE = "pathr:idioma";

type Dicionario = Record<string, unknown>;

/** Os dicionários que não são o português chegam sob demanda: quem lê em
 * português não baixa os outros quatro. */
const CARREGADORES: Record<Idioma, () => Promise<{ default: Dicionario }>> = {
  pt: () => Promise.resolve({ default: pt as Dicionario }),
  en: () => import("@/i18n/en.json"),
  es: () => import("@/i18n/es.json"),
  fr: () => import("@/i18n/fr.json"),
  de: () => import("@/i18n/de.json"),
};

export function ehIdioma(valor: unknown): valor is Idioma {
  return IDIOMAS.some((item) => item.codigo === valor);
}

/** "pt-BR", "PT_br" e "pt" viram `pt`. Nada reconhecido vira `null`. */
export function normalizarIdioma(bruto: string | null | undefined): Idioma | null {
  const codigo = String(bruto || "").toLowerCase().replace("_", "-").split("-")[0];
  return ehIdioma(codigo) ? codigo : null;
}

export function idiomaGuardado(): Idioma | null {
  try {
    return normalizarIdioma(window.localStorage.getItem(CHAVE));
  } catch {
    return null;
  }
}

function guardar(idioma: Idioma) {
  try {
    window.localStorage.setItem(CHAVE, idioma);
  } catch {
    // Armazenamento bloqueado: o idioma vale para esta visita.
  }
}

function idiomaInicial(): Idioma {
  if (typeof window === "undefined") return IDIOMA_PADRAO;
  const guardado = idiomaGuardado();
  if (guardado) return guardado;
  for (const preferido of window.navigator?.languages ?? []) {
    const casou = normalizarIdioma(preferido);
    if (casou) return casou;
  }
  return normalizarIdioma(window.navigator?.language) ?? IDIOMA_PADRAO;
}

/** O valor de "landing.hero.titulo" dentro do dicionário, ou `undefined`. */
function buscar(dicionario: Dicionario, chave: string): unknown {
  return chave.split(".").reduce<unknown>((atual, parte) => {
    if (atual && typeof atual === "object" && parte in (atual as Dicionario)) {
      return (atual as Dicionario)[parte];
    }
    return undefined;
  }, dicionario);
}

function aplicar(texto: string, valores?: Record<string, string | number>): string {
  if (!valores) return texto;
  return texto.replace(/\{(\w+)\}/g, (inteiro, nome: string) =>
    nome in valores ? String(valores[nome]) : inteiro,
  );
}

export type Traduzir = (chave: string, valores?: Record<string, string | number>) => string;

/**
 * Tradução em português, sem React.
 *
 * Para código que não é componente (lib/dashboard.ts, por exemplo): ele recebe
 * o tradutor da tela quando há um, e cai aqui quando roda solto — num teste ou
 * antes de a tela montar.
 */
export const traduzirPt: Traduzir = (chave, valores) => {
  const achado = buscar(pt as Dicionario, chave);
  return typeof achado === "string" ? aplicar(achado, valores) : chave;
};

interface Contexto {
  idioma: Idioma;
  /** Troca o idioma da tela e o guarda no aparelho. Gravar na conta é de quem
   * chamou (Configurações), que é onde há sessão. */
  trocarIdioma: (idioma: Idioma) => void;
  t: Traduzir;
}

const IdiomaContexto = createContext<Contexto | null>(null);

export function IdiomaProvider({
  children,
  idioma: idiomaDaConta,
}: {
  children: ReactNode;
  /** O idioma da conta, quando há uma. Sobrepõe o do aparelho. */
  idioma?: Idioma | null;
}) {
  const [idioma, setIdioma] = useState<Idioma>(idiomaInicial);
  const [dicionario, setDicionario] = useState<Dicionario>(pt as Dicionario);

  // A conta manda: entrar num aparelho novo traz o idioma de quem entrou.
  useEffect(() => {
    if (idiomaDaConta) {
      setIdioma(idiomaDaConta);
      guardar(idiomaDaConta);
    }
  }, [idiomaDaConta]);

  useEffect(() => {
    let vivo = true;
    void CARREGADORES[idioma]()
      .then((modulo) => {
        if (vivo) setDicionario(modulo.default);
      })
      .catch(() => {
        // Dicionário que não carregou (rede): fica o português, que já está aqui.
        if (vivo) setDicionario(pt as Dicionario);
      });
    if (typeof document !== "undefined") document.documentElement.lang = idioma;
    return () => {
      vivo = false;
    };
  }, [idioma]);

  const trocarIdioma = useCallback((novo: Idioma) => {
    setIdioma(novo);
    guardar(novo);
  }, []);

  const t = useCallback<Traduzir>(
    (chave, valores) => {
      const achado = buscar(dicionario, chave) ?? buscar(pt as Dicionario, chave);
      // A chave crua na tela é feia de propósito: aparece no teste e no uso, e
      // some assim que a chave entra no pt.json.
      return typeof achado === "string" ? aplicar(achado, valores) : chave;
    },
    [dicionario],
  );

  const valor = useMemo<Contexto>(() => ({ idioma, trocarIdioma, t }), [idioma, trocarIdioma, t]);

  return <IdiomaContexto.Provider value={valor}>{children}</IdiomaContexto.Provider>;
}

/** O contexto de fora do provider. É uma CONSTANTE — e não um objeto novo a
 * cada render — porque `t` entra em dependências de `useEffect`/`useCallback`:
 * um `t` recriado a cada render dispararia esses efeitos em laço (um componente
 * que busca dados ao montar nunca estabilizaria). `traduzirPt` já é estável. */
const SEM_PROVIDER: Contexto = {
  idioma: IDIOMA_PADRAO,
  trocarIdioma: () => {},
  t: traduzirPt,
};

function usarContexto(): Contexto {
  // Fora do provider (um teste que renderiza um componente solto): português,
  // sem quebrar a tela.
  return useContext(IdiomaContexto) ?? SEM_PROVIDER;
}

export function useT(): Traduzir {
  return usarContexto().t;
}

export function useIdioma(): { idioma: Idioma; trocarIdioma: (idioma: Idioma) => void } {
  const { idioma, trocarIdioma } = usarContexto();
  return { idioma, trocarIdioma };
}
