/**
 * A atividade prática: cores, comentários, e a correção pelo que foi pedido.
 *
 * O que se segura: o realce reconhece comentário nas formas comuns sem
 * confundir `https://`, `--amend` ou `#fff`; juntar os pedaços devolve o texto
 * (senão a cor desalinha da letra); o texto nunca vira HTML; a atividade é
 * enviada no modo `atividade`; e a resposta fora do tema aparece como tal.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { RoadmapNode } from "@/api/types";
import { ActivityPanel } from "@/components/quiz/ActivityPanel";
import { realcar } from "@/lib/realce";
import { mockServer } from "./server";

const comentarios = (fonte: string) =>
  realcar(fonte)
    .filter((p) => p.papel === "comentario")
    .map((p) => p.texto);

describe("realce", () => {
  it("reconhece comentários de várias linguagens", () => {
    expect(comentarios("git push // para subir pro GitHub")).toEqual(["// para subir pro GitHub"]);
    expect(comentarios("ls -la  # lista tudo\n#!/bin/bash")).toEqual(["# lista tudo", "#!/bin/bash"]);
    expect(comentarios("SELECT 1; -- teste")).toEqual(["-- teste"]);
    expect(comentarios("/* bloco\nde duas linhas */ int x;")).toEqual(["/* bloco\nde duas linhas */"]);
    expect(comentarios("<!-- nota --><p>")).toEqual(["<!-- nota -->"]);
  });

  it("não confunde URL, opção e cor com comentário", () => {
    expect(comentarios("git clone https://github.com/a/b.git")).toEqual([]);
    expect(comentarios("git commit --amend -m \"x\"")).toEqual([]);
    expect(comentarios("color: #fff;")).toEqual([]);
  });

  it("colore comando, opção e texto, e devolve o texto inteiro", () => {
    const fonte = 'git commit -m "arquivo de teste"\nconst x = 42; // fim\n\tfoo(bar)';
    const pedacos = realcar(fonte);
    expect(pedacos.map((p) => p.texto).join("")).toBe(fonte);
    const papel = (texto: string) => pedacos.find((p) => p.texto === texto)?.papel;
    expect(papel("git")).toBe("comando");
    expect(papel("-m")).toBe("opcao");
    expect(papel('"arquivo de teste"')).toBe("texto");
    expect(papel("const")).toBe("palavra_chave");
    expect(papel("42")).toBe("numero");
    expect(papel("foo")).toBe("chamada");
  });
});

const node = {
  id: "N1",
  title: "Git e GitHub Actions",
  objectives: ["Configurar repositórios remotos usando Git."],
} as unknown as RoadmapNode;

describe("painel da atividade", () => {
  it("mostra o texto com cores, sem virar HTML, e envia no modo atividade", async () => {
    const servidor = mockServer({
      "GET /roadmap/nodes/N1/draft": () => ({ body: { content: "", updated_at: null } }),
      "PUT /roadmap/nodes/N1/draft": () => ({ body: { content: "", updated_at: null } }),
      "POST /explanations": () => ({
        body: { id: "e1", score: 0, feedback: "Isso não é sobre Git.", gaps: [], sustenta: [], fora_do_tema: true },
      }),
    });
    const user = userEvent.setup();
    const { container } = render(<ActivityPanel node={node} />);
    const campo = await screen.findByLabelText("Sua resposta");

    await user.click(campo);
    await user.paste('<img src=x onerror="alert(1)"> git push // sobe pro GitHub e muito mais texto aqui');
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector('[data-papel="comentario"]')).toHaveTextContent("// sobe pro GitHub");

    await user.click(screen.getByRole("button", { name: /Enviar para correção/ }));
    const envio = servidor.calls.find((c) => c.method === "POST" && c.url === "/explanations");
    expect(envio?.body).toMatchObject({ node_id: "N1", modo: "atividade" });
    expect(await screen.findByText("Não parece uma resposta para esta atividade.")).toBeInTheDocument();
  });
});
