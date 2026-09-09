# Notter Estudos (PathR) — frontend

O app em `pathr.notter.com.br`. React 18 + TypeScript em Vite, estilizado com
o design system Nocturne. Fala com `api.pathr.notter.com.br` — não existe mais
nenhum dado de exemplo no código.

## Rodar

```
npm install
npm run dev        # http://localhost:5173 (cai para outra porta se ocupada)
npm run build      # typecheck + bundle em dist/
npm test           # vitest, jsdom
```

`VITE_API_URL` aponta para a API; sem ela o cliente usa
`https://localhost:8031`, que é a porta do backend em desenvolvimento.

## Como está montado

```
src/
  api/          client (fetch + renovação de sessão), endpoints tipados, types, errors
  components/
    auth/       moldura das telas de entrada
    dashboard/  KPIs, constância, sequência, fases, retomar, a seguir
    english/    nivelamento e ajustes do módulo de idioma
    layout/     AppShell e a barra lateral
    library/    a linha da biblioteca
    profile/    tag, tecnologia lida do currículo, conta, skills
    quiz/       quiz, material e atividade do módulo
    roadmap/    timeline, colunas, matriz, geração do plano
    ui/         Panel, Kicker, Meter, Segmented, Chip, ChoiceList, estados, ícones
  hooks/        useAuth (sessão), useApi (busca/escrita), useAppState (UI),
                useLocation, useOffline (fila e rede), useMediaQuery (forma)
  lib/          tokens, dashboard, highlight, moduleStatus, curadoria
  offline/      IndexedDB, cache de leitura, fila de escrita, projeções, status
  pwa/          service worker (modelo) e registro
  pages/        uma por tela, mais as de autenticação e a do material aberto
  styles/       nocturne.css (cópia do design system), app.css
  test/         reducer, derivações, autenticação, telas, fluxo do currículo
  types/        vocabulário de interface (as formas de dado ficam em api/types)
```

### Duas fontes de estado, de propósito

`useAppState` guarda só **escolhas de interface** — qual tela, qual aba, o que
está digitado numa busca. Todo dado de domínio vem do servidor por `useQuery`.
Guardar uma cópia no reducer criaria duas fontes de verdade que divergem no
primeiro erro de rede; foi exatamente isso que os dados de exemplo faziam
antes.

### Sessão

Cookie HttpOnly, nunca `localStorage`: o token não passa pelo JavaScript,
então um XSS não leva a sessão. Quando um 401 chega, o cliente chama
`/auth/refresh` uma vez e repete o pedido — e essa renovação é **compartilhada**
entre chamadas concorrentes. Cinco 401 simultâneos fazem um refresh, não
cinco; cinco rotacionariam o token cinco vezes e quatro seriam lidas pelo
backend como reuso de token roubado, derrubando a sessão inteira.

### Estados de tela

Toda tela ligada ao servidor desenha os quatro: carregando, erro (com "tentar
de novo"), vazio (com o que fazer a respeito) e pronto. Os três primeiros vêm
de `components/ui/States.tsx` — cada tela inventando o seu é como um app passa
a ter cinco vazios diferentes dizendo a mesma coisa.

## No celular

O app instala na tela de início do iPhone pelo Safari (Compartilhar →
"Adicionar à Tela de Início") e abre em tela cheia, sem barra de endereço.

### O material abre como tela

Vídeo e artigo abrem em `pages/ResourcePage`, com endereço próprio no estado
de navegação, botão de voltar e o progresso no topo. Antes eles expandiam a
própria linha da lista: uma moldura dentro de outra, dentro do painel, dentro
da moldura do app — e num celular sobravam uns 300px de largura para o player.

O "voltar" leva de volta a de ONDE se veio (a biblioteca ou a aba de material
do módulo), e a aba de origem continua acesa na barra de baixo enquanto o
material está aberto.

### Duas formas, não uma encolhida

Acima de 720px de largura: barra lateral. Abaixo: cabeçalho fino, conteúdo, e
uma barra fixa embaixo com quatro destinos e um "Mais". Não é a mesma tela
espremida — a lateral comeria metade de uma tela de 402px, e o que sobraria é
texto de estudo numa coluna estreita demais para ler.

`useMediaQuery` decide isso no render, e não no CSS, porque quase toda a
interface é estilo inline: uma `@media` não alcançaria a maior parte dela.

### As áreas do aparelho

`--safe-top`, `--safe-bottom`, `--safe-left` e `--safe-right`, em
`styles/app.css`, carregam os `env(safe-area-inset-*)`. Passam por variáveis e
não por `env()` espalhado pelos componentes porque `env()` não se sobrescreve
— com a indireção dá para simular um iPhone num navegador de desktop e MEDIR
se algum botão caiu sob a barra de status (que precisa ficar livre para o
gesto da central de controle) ou sob a barra de gestos.

### Toque

`@media (pointer: coarse)` leva todo alvo a 44px, o piso da diretriz da Apple,
e todo campo a 16px — abaixo disso o Safari do iPhone dá zoom na página ao
focar o campo, e o zoom não volta sozinho. Por isso nenhum `<input>` deste app
carrega `fontSize` em estilo inline: inline venceria a regra e traria o zoom de
volta.

### Uma escala, não oito

`SIZE` em `lib/tokens.ts`: `rotulo` (11), `apoio` (12.5), `corpo` (14). Toda
ação usa `corpo` — o mesmo tamanho do `.btn`. Antes disto os controles do app
usavam oito combinações de tamanho e peso, e dois botões vizinhos saíam com
corpos diferentes.

Cuidado com `font: "inherit"`: é um atalho, e zera o `fontSize` declarado
ANTES dele. Dois botões herdavam 15px por causa dessa ordem.

## Offline

O app abre e registra progresso sem rede. São duas camadas separadas de
propósito:

**O casco** (`pwa/`) é um service worker que guarda HTML, JavaScript, CSS e
ícones. É o que faz o app ABRIR no metrô. Ele não toca em nada da API: as
respostas dela têm dono, precisam sumir no logout e alimentam a fila de
escrita, e nada disso um service worker sabe.

**Os dados** (`offline/`) ficam em IndexedDB:

- **Cache de leitura.** Toda resposta de GET é guardada. Se a próxima falhar
  por rede, o cliente devolve a última conhecida — incluindo a de `/auth/me`,
  que é o que mantém a sessão reconhecida offline em vez de cair na tela de
  entrada.
- **Fila de escrita.** As escritas de progresso marcadas como enfileiráveis
  (`PATCH /roadmap/nodes/{id}`, `PUT /library/{id}/progress`, o rascunho da
  atividade) entram numa fila e sobem quando a rede volta. Só entra o que é
  idempotente: repetir um `POST /quizzes/{id}/submit` corrigiria o quiz duas
  vezes.
- **Projeção.** A fila é aplicada por cima do cache na leitura. Sem isso,
  marcar um módulo no avião e fechar o app faria o progresso "voltar" ao
  reabrir — a escrita continuaria guardada, mas ninguém acredita num app que
  mostra o contrário do que registrou.

Um 4xx do servidor continua sendo erro na tela. Cache e fila valem só para
falha de REDE: um pedido que chegou e foi recusado precisa aparecer.

## Sincronia entre aparelhos

Nada de conta mora só no navegador — não há `localStorage` em código de
produção, e o IndexedDB é espelho para offline, não fonte da verdade. Então
quem ABRE uma tela já vê o estado certo em qualquer aparelho. O problema é a
tela que JÁ ESTAVA aberta, e ele é resolvido em duas camadas:

1. **Aviso em tempo real.** `offline/eventos.ts` mantém um `EventSource` em
   `GET /events` enquanto a aba está visível. O servidor não manda conteúdo:
   manda um empurrão para reconsultar, e quem sabe pedir os dados continua
   sendo o `useQuery`. Duas formas de o cliente aprender a verdade seriam duas
   formas de divergir.
2. **Reconferência ao voltar ao foco**, se faz mais de 20s desde a última
   resposta do servidor. É a rede de segurança: se o canal cair, se a
   hospedagem tiver mais de uma máquina sem `LISTEN/NOTIFY`, ou se o navegador
   não suportar SSE, as telas ainda se corrigem sozinhas.

Duas particularidades que parecem detalhe e não são:

- **O canal só existe com a aba visível.** Uma conexão SSE aberta é uma
  requisição em voo, e a hospedagem da API suspende a máquina quando não há
  nenhuma. Um celular esquecido aberto no bolso seguraria a máquina no ar por
  nada — e o valor de um aviso em tempo real para uma tela que ninguém está
  vendo é zero.
- **Toda escrita manda `X-Pathr-Client`** com o id desta aba, e o aviso volta
  com ele em `origem`. Quem escreveu ignora o próprio eco: a tela dele já está
  atualizada, e reconsultar por causa do próprio POST seria uma requisição a
  mais por escrita, em todo aparelho.

## Diferenças em relação ao protótipo

O design canvas (`design/Notter Estudos.dc.html`) descrevia um app com dados
fixos. Três coisas mudaram ao ligar no servidor:

- **O quiz corrige no fim, não a cada clique.** O gabarito está no servidor, e
  é no envio que a proficiência por tag é atualizada com evidência. A tela de
  revisão mostra cada questão com o que foi escolhido, o certo e o porquê.
  (O nivelamento de idioma segue item a item: lá o backend expõe uma rota de
  resposta por item, porque é ela que calibra a dificuldade do próximo lote.)
- **O painel começa vazio.** Sem plano gerado não há o que resumir, então a
  tela vira convite ao onboarding em vez de um painel de zeros.
- **Configurações tem três abas, não cinco.** "Objetivo" virou a própria
  geração do plano, na tela do roadmap — o objetivo só existe no momento em
  que um plano é gerado. "Avisos" saiu: o backend ainda não tem preferências
  de notificação.

## O que ainda não existe

A correção automática da atividade prática (`POST /activities` não existe no
backend). A tela diz isso; o rascunho é gravado no servidor e, sem rede, na
fila offline.

O offline cobre leitura e progresso. **Não** cobre o que precisa do servidor
na hora: gerar um plano, corrigir um quiz, responder o nivelamento de idioma,
buscar material novo. Essas telas dão erro sem rede, e é o certo — fingir que
deram certo esconderia a falha até a próxima abertura do app.
