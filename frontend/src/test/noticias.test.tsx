/**
 * A aba de Notícias.
 *
 * O que se segura, cada item vindo de algo que a pessoa viu na tela:
 *
 * - a lista aparece NA HORA, com o que o servidor já tem, mesmo enquanto ele
 *   procura mais — antes a tela ficava presa num "Buscando eventos…";
 * - o cartaz do evento é mostrado;
 * - "Adicionar ao Google Agenda" é um LINK que abre a agenda, porque no
 *   computador um `.ics` baixado não faz nada para quem usa agenda no
 *   navegador. O `.ics` continua disponível, como segunda opção.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppStateProvider } from "@/hooks/useAppState";
import { NoticiasPage } from "@/pages/NoticiasPage";
import { mockServer } from "./server";

const evento = {
  id: "e1",
  titulo: "Meetup de Python",
  resumo: "Encontro da comunidade.",
  local: "Centro de Convenções",
  cidade: "Vitória",
  estado: "ES",
  data_inicio: "2026-10-28",
  data_fim: null,
  gratuito: true,
  preco_info: null,
  inscricao_inicio: null,
  inscricao_fim: null,
  inscricao_texto: "Datas de inscrição ainda não foram definidas",
  url_ingresso: "https://sympla.com.br/meetup-python",
  imagem: "https://img.exemplo/cartaz.jpg",
  eu_vou: false,
};

function monta(corpo: { eventos: unknown[]; atualizando: boolean }) {
  mockServer({
    "GET /profile": () => ({ body: { user_id: "u1", city: "Vitória", state: "ES" } }),
    "GET /noticias": () => ({ body: corpo }),
  });
  return render(
    <AppStateProvider>
      <NoticiasPage />
    </AppStateProvider>,
  );
}

describe("notícias", () => {
  it("mostra os eventos que já existem enquanto o servidor procura mais", async () => {
    monta({ eventos: [evento], atualizando: true });

    // O evento aparece — a tela NÃO fica presa esperando a busca terminar.
    expect(await screen.findByText("Meetup de Python")).toBeInTheDocument();
    // E o aviso explica o que está acontecendo, em vez de um giro sem fim.
    expect(screen.getByText(/Procurando eventos novos/)).toBeInTheDocument();
  });

  it("sem busca em andamento, não mostra o aviso", async () => {
    monta({ eventos: [evento], atualizando: false });

    expect(await screen.findByText("Meetup de Python")).toBeInTheDocument();
    expect(screen.queryByText(/Procurando eventos novos/)).not.toBeInTheDocument();
  });

  it("mostra a data real e o cartaz do evento", async () => {
    const { container } = monta({ eventos: [evento], atualizando: false });

    expect(await screen.findByText(/28 de out\. de 2026/)).toBeInTheDocument();
    const imagem = container.querySelector("img");
    expect(imagem).toHaveAttribute("src", evento.imagem);
  });

  it("oferece o Google Agenda como link, com as datas do evento", async () => {
    monta({ eventos: [evento], atualizando: false });

    const link = await screen.findByRole("link", { name: /Google Agenda/ });
    const endereco = new URL(link.getAttribute("href") ?? "");

    expect(endereco.origin + endereco.pathname).toBe(
      "https://calendar.google.com/calendar/render",
    );
    // Fim EXCLUSIVO: um evento de um dia termina no dia seguinte, senão a
    // agenda do Google mostra um dia a menos.
    expect(endereco.searchParams.get("dates")).toBe("20261028/20261029");
    expect(endereco.searchParams.get("text")).toBe("Meetup de Python");
    expect(link).toHaveAttribute("target", "_blank");

    // O .ics continua ali, para Outlook, Apple e celular.
    expect(screen.getByRole("button", { name: /\.ics/ })).toBeInTheDocument();
  });

  it("evento com campo faltando não derruba a tela inteira", async () => {
    // Aconteceu em produção: um evento sem data fazia o link do Google Agenda
    // estourar DENTRO do render, e a aba inteira virava "Alguma coisa quebrou
    // ao desenhar o conteúdo" — por causa de um evento só.
    const semData = { ...evento, data_inicio: null, data_fim: null, imagem: null, resumo: null };
    monta({ eventos: [semData], atualizando: false });

    expect(await screen.findByText("Meetup de Python")).toBeInTheDocument();
    // O botão de agenda some (não há o que agendar), mas a tela fica de pé.
    expect(screen.queryByRole("link", { name: /Google Agenda/ })).not.toBeInTheDocument();
  });

  it("sem nenhum evento, explica em vez de ficar vazia", async () => {
    monta({ eventos: [], atualizando: false });

    expect(await screen.findByText(/Nenhum evento/i)).toBeInTheDocument();
  });
});
