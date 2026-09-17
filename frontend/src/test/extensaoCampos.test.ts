/**
 * O reconhecimento de campos da PathR Extension.
 *
 * O que se segura: o rótulo é achado onde quer que o site o tenha posto; a
 * mesma pergunta escrita de jeitos diferentes cai na mesma chave; o
 * preenchimento dispara os eventos que um site em React precisa ver; e o que a
 * extensão NÃO responde sozinha continua não respondendo — caixa de aceite,
 * pergunta sensível e pergunta aberta sobre a vaga.
 *
 * O arquivo testado é o da extensão, não uma cópia: é ele que roda no
 * navegador, e um teste sobre cópia não garante nada.
 */

import { beforeAll, describe, expect, it } from "vitest";

type Plano = {
  preenchiveis: { rotulo: string; chave: string; valor: string; origem: string; tipo: string }[];
  pendentes: { rotulo: string; chave: string; motivo: string }[];
  total: number;
};

type Campos = {
  chave: (pergunta: string) => string;
  rotuloDe: (campo: Element) => string;
  analisar: (dados: Record<string, unknown>) => Plano;
  preencher: (plano: unknown[], curriculo: unknown) => Promise<{ feitos: unknown[]; falhas: unknown[] }>;
};

let Campos: Campos;

beforeAll(async () => {
  // @ts-expect-error — JS puro, sem tipos: a extensão não passa pelo build do
  // app, e é exatamente o arquivo que roda no navegador que queremos testar.
  await import("../../../extensao/src/campos.js");
  Campos = (window as unknown as { PathRCampos: Campos }).PathRCampos;
});

function montar(html: string) {
  document.body.innerHTML = html;
  // jsdom devolve 0x0 para tudo; `visivel()` desiste de campo sem caixa, então
  // damos um tamanho a todo mundo — é o layout que o navegador daria.
  for (const campo of Array.from(document.querySelectorAll("input, textarea, select"))) {
    campo.getBoundingClientRect = () => ({ width: 120, height: 32 }) as DOMRect;
  }
}

describe("chave da pergunta", () => {
  it("junta as formas da mesma pergunta", () => {
    expect(Campos.chave("Nome completo")).toBe("nome");
    expect(Campos.chave("Full name")).toBe("nome");
    expect(Campos.chave("Qual é o seu nome?")).toBe("nome");

    expect(Campos.chave("Currículo")).toBe("curriculo");
    expect(Campos.chave("Resume")).toBe("curriculo");
    expect(Campos.chave("Anexe seu CV")).toBe("curriculo");

    expect(Campos.chave("Endereço")).toBe("endereco");
    expect(Campos.chave("Logradouro")).toBe("endereco");
  });

  it("não confunde cidade com idade", () => {
    // "cidade" contém "idade": com substring crua, todo campo de cidade virava
    // pergunta sensível e ficava sem resposta.
    expect(Campos.chave("Cidade")).toBe("cidade");
    expect(Campos.chave("Qual sua idade?")).toBe("sensivel:idade");
  });

  it("prefere a forma mais longa", () => {
    // "pretensao salarial" tem de ganhar de "pretensao", e não depender da
    // ordem em que os sinônimos foram escritos.
    expect(Campos.chave("Pretensão salarial")).toBe("pretensao");
    expect(Campos.chave("Primeiro nome")).toBe("primeiro_nome");
  });

  it("pergunta desconhecida vira chave própria, reaproveitável", () => {
    expect(Campos.chave("Você já usou Kubernetes em produção?")).toBe(
      "livre:voce ja usou kubernetes em producao",
    );
  });
});

describe("onde está o rótulo", () => {
  it("acha em aria-label, label for, label em volta, texto ao lado e placeholder", () => {
    montar(`
      <input id="a" aria-label="Pretensão salarial" />
      <label for="b">Telefone</label><input id="b" />
      <label>LinkedIn <input id="c" /></label>
      <div><span>Cidade</span><input id="d" /></div>
      <input id="e" placeholder="Seu e-mail" />
      <input id="f" name="github_url" />
    `);
    const rotulo = (id: string) => Campos.rotuloDe(document.getElementById(id) as Element);

    expect(Campos.chave(rotulo("a"))).toBe("pretensao");
    expect(Campos.chave(rotulo("b"))).toBe("telefone");
    expect(Campos.chave(rotulo("c"))).toBe("linkedin");
    expect(Campos.chave(rotulo("d"))).toBe("cidade");
    expect(Campos.chave(rotulo("e"))).toBe("email");
    // Último recurso: o nome do campo no HTML.
    expect(Campos.chave(rotulo("f"))).toBe("github");
  });

  it("autocomplete manda mais que o rótulo", () => {
    // O site diz, em padrão da web, o que quer ali. Vale mais que texto — e não
    // depende do idioma da página.
    montar(`<input id="a" autocomplete="family-name" placeholder="Apellido" />`);
    const plano = Campos.analisar({ respostas: {}, perfil: { sobrenome: "Souza" } });
    expect(plano.preenchiveis[0].chave).toBe("sobrenome");
  });
});

describe("o plano de preenchimento", () => {
  const dados = {
    respostas: { pretensao: "R$ 9.000" },
    perfil: { nome: "Ana Souza", email: "ana@exemplo.com", cidade: "Campinas" },
  };

  it("separa o que sabe do que precisa perguntar", () => {
    montar(`
      <input aria-label="Nome completo" />
      <input aria-label="Pretensão salarial" />
      <input aria-label="Qual seu gênero?" />
      <textarea aria-label="Por que você quer trabalhar aqui?"></textarea>
      <input aria-label="Quantos anos de xadrez?" />
    `);

    const plano = Campos.analisar(dados);
    const porChave = Object.fromEntries(plano.preenchiveis.map((i) => [i.chave, i]));

    expect(porChave.nome.valor).toBe("Ana Souza");
    expect(porChave.nome.origem).toBe("perfil");
    // Veio do banco de respostas, não do perfil — a tela diz isso a quem confere.
    expect(porChave.pretensao.origem).toBe("banco");

    const motivos = Object.fromEntries(plano.pendentes.map((i) => [i.motivo, i.rotulo]));
    expect(motivos.sensivel).toBe("Qual seu gênero?");
    expect(motivos.aberta).toBe("Por que você quer trabalhar aqui?");
    expect(motivos.desconhecida).toBe("Quantos anos de xadrez?");
  });

  it("nunca marca caixa de aceite sozinho", () => {
    montar(`<label><input type="checkbox" /> Li e aceito os termos de uso</label>`);

    const plano = Campos.analisar(dados);

    // Concordar é ato de quem se candidata, não do programa.
    expect(plano.preenchiveis).toHaveLength(0);
    expect(plano.pendentes[0].motivo).toBe("escolha");
  });

  it("não repete a mesma pergunta feita duas vezes na página", () => {
    montar(`<input aria-label="Nome completo" /><input aria-label="Full name" />`);

    expect(Campos.analisar(dados).preenchiveis).toHaveLength(1);
  });
});

describe("preencher de verdade", () => {
  it("dispara os eventos que um site em React precisa ver", async () => {
    montar(`<input aria-label="Cidade" />`);
    const campo = document.querySelector("input") as HTMLInputElement;
    const vistos: string[] = [];
    for (const evento of ["input", "change", "blur"]) {
      campo.addEventListener(evento, () => vistos.push(evento));
    }

    const plano = Campos.analisar({ respostas: {}, perfil: { cidade: "Campinas" } });
    const resultado = await Campos.preencher(plano.preenchiveis, null);

    expect(campo.value).toBe("Campinas");
    expect(resultado.feitos).toHaveLength(1);
    // `value = x` puro não basta: o React ignora a mudança que ele não viu.
    expect(vistos).toEqual(["input", "change", "blur"]);
  });

  it("escolhe a opção de um select mesmo escrita diferente", async () => {
    montar(`
      <label for="uf">Estado</label>
      <select id="uf"><option value="">Escolha</option><option value="SP">São Paulo - SP</option></select>
    `);

    const plano = Campos.analisar({ respostas: {}, perfil: { estado: "São Paulo" } });
    await Campos.preencher(plano.preenchiveis, null);

    expect((document.getElementById("uf") as HTMLSelectElement).value).toBe("SP");
  });
});
