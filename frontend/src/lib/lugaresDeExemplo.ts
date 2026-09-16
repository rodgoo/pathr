/**
 * De onde são as pessoas de exemplo da página de apresentação.
 *
 * O cartão de exemplo mostra cidade e região porque é assim que a sugestão de
 * pessoas funciona de verdade — ela aproxima quem está perto. Mas "Vitória ·
 * ES" para quem abriu o site em alemão não diz nada: o exemplo deixa de
 * ilustrar e vira ruído.
 *
 * Então o lugar acompanha o idioma, e é sorteado a cada troca: quem mexe no
 * seletor vê a página inteira mudar, inclusive o exemplo.
 *
 * Lista escrita à mão, e curta, de propósito: são cidades conhecidas onde há
 * mercado de tecnologia, e nenhuma delas passa pelo tradutor automático (nome
 * próprio traduzido vira outra cidade — "Vitória" já virou "Victory" uma vez).
 */

import type { PessoaCartao } from "@/api/types";
import { IDIOMA_PADRAO, type Idioma } from "@/lib/i18n";

export interface Lugar {
  cidade: string;
  /** Estado, província ou país — o que a pessoa de lá usaria. */
  uf: string;
}

const LUGARES: Record<Idioma, Lugar[]> = {
  pt: [
    { cidade: "Vitória", uf: "ES" },
    { cidade: "Belo Horizonte", uf: "MG" },
    { cidade: "Curitiba", uf: "PR" },
    { cidade: "Recife", uf: "PE" },
    { cidade: "Florianópolis", uf: "SC" },
    { cidade: "Porto Alegre", uf: "RS" },
  ],
  en: [
    { cidade: "Austin", uf: "TX" },
    { cidade: "Manchester", uf: "UK" },
    { cidade: "Toronto", uf: "ON" },
    { cidade: "Dublin", uf: "IE" },
    { cidade: "Seattle", uf: "WA" },
    { cidade: "Melbourne", uf: "AU" },
  ],
  es: [
    { cidade: "Bogotá", uf: "CO" },
    { cidade: "Ciudad de México", uf: "MX" },
    { cidade: "Valencia", uf: "ES" },
    { cidade: "Buenos Aires", uf: "AR" },
    { cidade: "Medellín", uf: "CO" },
    { cidade: "Santiago", uf: "CL" },
  ],
  fr: [
    { cidade: "Lyon", uf: "FR" },
    { cidade: "Nantes", uf: "FR" },
    { cidade: "Bruxelles", uf: "BE" },
    { cidade: "Montréal", uf: "QC" },
    { cidade: "Toulouse", uf: "FR" },
    { cidade: "Genève", uf: "CH" },
  ],
  de: [
    { cidade: "Hamburg", uf: "DE" },
    { cidade: "München", uf: "DE" },
    { cidade: "Leipzig", uf: "DE" },
    { cidade: "Wien", uf: "AT" },
    { cidade: "Zürich", uf: "CH" },
    { cidade: "Köln", uf: "DE" },
  ],
};

/** Nomes que soam de quem fala aquele idioma. Também não se traduzem. */
const NOMES: Record<Idioma, string[]> = {
  pt: ["Marina Costa", "Lucas Rocha", "Beatriz Almeida", "Rafael Nunes", "Camila Torres", "Diego Martins"],
  en: ["Emily Carter", "James Bennett", "Olivia Hughes", "Daniel Foster", "Sophie Turner", "Aaron Mitchell"],
  es: ["Lucía Fernández", "Mateo Ruiz", "Valentina Soto", "Javier Morales", "Carmen Ortega", "Andrés Vidal"],
  fr: ["Camille Durand", "Hugo Lefèvre", "Léa Moreau", "Antoine Girard", "Chloé Rousseau", "Maxime Dubois"],
  de: ["Lena Schmidt", "Jonas Weber", "Mia Hoffmann", "Felix Braun", "Hannah König", "Tobias Richter"],
};

/**
 * Combinações de stack que existem juntas na vida real, com o objetivo que
 * combina com elas. Sortear tecnologias soltas produziria um cartão com
 * "Java, React, Django" — ninguém estuda isso ao mesmo tempo, e o exemplo
 * perderia a credibilidade justamente na tela que apresenta o produto.
 */
const PERFIS: { stack: string[]; objetivo: string; senioridade: string }[] = [
  { stack: ["Java", "Spring Boot", "PostgreSQL", "Docker"], objetivo: "landing.perfis.javaSpring", senioridade: "pleno" },
  { stack: ["React", "TypeScript", "Node.js"], objetivo: "landing.perfis.fullstackTs", senioridade: "junior" },
  { stack: ["Python", "Django", "PostgreSQL"], objetivo: "landing.perfis.pythonBackend", senioridade: "pleno" },
  { stack: ["Go", "Kubernetes", "Docker"], objetivo: "landing.perfis.plataforma", senioridade: "senior" },
  { stack: ["C#", ".NET", "SQL Server"], objetivo: "landing.perfis.dotnet", senioridade: "pleno" },
  { stack: ["Kotlin", "Android", "Firebase"], objetivo: "landing.perfis.android", senioridade: "junior" },
];

function sortear<T>(lista: readonly T[], quantos: number): T[] {
  const restantes = [...lista];
  const sorteados: T[] = [];
  while (sorteados.length < quantos && restantes.length > 0) {
    sorteados.push(...restantes.splice(Math.floor(Math.random() * restantes.length), 1));
  }
  return sorteados;
}

/** `quantos` lugares diferentes do idioma, sorteados. */
export function lugaresDeExemplo(idioma: Idioma, quantos: number): Lugar[] {
  return sortear(LUGARES[idioma] ?? LUGARES[IDIOMA_PADRAO], quantos);
}

/**
 * As duas pessoas do cartão de exemplo, sorteadas para o idioma.
 *
 * A primeira chega como sugestão (dá para adicionar) e a segunda como convite
 * recebido (dá para aceitar ou recusar): é o que deixa o visitante mexer nos
 * dois caminhos sem sair da página.
 *
 * `objetivo` volta como chave de dicionário — ver o comentário abaixo.
 */
export function pessoasDeExemplo(idioma: Idioma): PessoaCartao[] {
  const nomes = sortear(NOMES[idioma] ?? NOMES[IDIOMA_PADRAO], 2);
  const lugares = lugaresDeExemplo(idioma, 2);
  const perfis = sortear(PERFIS, 2);

  return nomes.map((nome, posicao) => {
    const perfil = perfis[posicao] ?? PERFIS[posicao];
    const lugar = lugares[posicao] ?? lugares[0];
    const recebido = posicao === 1;
    return {
      username: nome.toLowerCase().normalize("NFD").replace(/[^a-z ]/g, "").trim().replace(/ +/g, "_"),
      name: nome,
      has_avatar: false,
      city: lugar.cidade,
      state: lugar.uf,
      // A CHAVE do objetivo, não o texto: quem mostra traduz na hora, e o
      // cartão acompanha a troca de idioma sem ser sorteado de novo.
      objetivo: perfil.objetivo,
      cargo: null,
      senioridade: perfil.senioridade,
      stack: perfil.stack,
      relacao: recebido ? "recebido" : "nenhuma",
      friendship_id: recebido ? "exemplo" : null,
      // Quem chegou como convite tem a mesma stack; o outro, duas em comum.
      em_comum: recebido ? perfil.stack : perfil.stack.slice(0, 2),
      mesma_stack: recebido,
    };
  });
}
