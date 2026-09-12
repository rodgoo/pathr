/**
 * O logo de cada linguagem de programação, pelo id que o servidor usa.
 *
 * Os ids são os de `backend/app/services/code_lab.py` (`LINGUAGENS`). Os SVGs
 * vêm do Devicon e moram em `assets/linguagens` — ver o LICENSE.md de lá para
 * a origem e o que foi alterado.
 *
 * `<img>` e não SVG embutido: são arquivos de terceiro, e como imagem eles
 * não executam nada nem herdam estilo do app. O Vite embute os pequenos no
 * bundle e o service worker guarda o resto, então abrem também offline.
 */

import type { ReactNode } from "react";
import { Icon } from "@/components/ui/icons";
import bash from "@/assets/linguagens/bash.svg";
import c from "@/assets/linguagens/c.svg";
import cplusplus from "@/assets/linguagens/cplusplus.svg";
import csharp from "@/assets/linguagens/csharp.svg";
import dart from "@/assets/linguagens/dart.svg";
import go from "@/assets/linguagens/go.svg";
import java from "@/assets/linguagens/java.svg";
import javascript from "@/assets/linguagens/javascript.svg";
import kotlin from "@/assets/linguagens/kotlin.svg";
import php from "@/assets/linguagens/php.svg";
import python from "@/assets/linguagens/python.svg";
import ruby from "@/assets/linguagens/ruby.svg";
import rust from "@/assets/linguagens/rust.svg";
import swift from "@/assets/linguagens/swift.svg";
import typescript from "@/assets/linguagens/typescript.svg";

const LOGOS: Record<string, string> = {
  python,
  javascript,
  typescript,
  java,
  csharp,
  go,
  rust,
  c,
  cpp: cplusplus,
  php,
  ruby,
  kotlin,
  swift,
  dart,
  bash,
};

/**
 * O ícone da linguagem, ou `null` para uma que o app ainda não conhece.
 *
 * `alt=""` de propósito: o ícone fica sempre ao lado do nome, e anunciar
 * "Python, Python" a cada opção só dobraria o que o leitor de tela diz.
 */
export function iconeDaLinguagem(id: string): ReactNode {
  // SQL não é um produto com logo; o genérico de banco diz exatamente o que é.
  if (id === "sql") return <Icon name="db" size={18} />;
  const logo = LOGOS[id];
  return logo ? <img src={logo} alt="" width={18} height={18} /> : null;
}
