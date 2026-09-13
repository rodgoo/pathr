/**
 * O único caminho por onde uma URL de fora vira link clicável.
 *
 * Os endereços de artigo, vaga e curso não são nossos: vêm de busca na web,
 * de APIs de vagas, de resposta de modelo de IA. Um `href` montado direto com
 * eles aceita `javascript:alert(document.cookie)` — e o React 18 ainda
 * renderiza esse href (só avisa no console). Um resultado de busca ou uma
 * vaga maliciosa executaria código no PathR no primeiro clique.
 *
 * Aqui só `http:` e `https:` passam. O resto devolve `undefined`, e um `<a>`
 * sem `href` é texto inerte: a pessoa vê o nome do link e não consegue
 * disparar nada. Melhor um link morto do que um que executa.
 */
export function linkExterno(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const endereco = new URL(url.trim());
    return endereco.protocol === "https:" || endereco.protocol === "http:" ? endereco.href : undefined;
  } catch {
    return undefined;
  }
}
