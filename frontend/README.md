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
  api/          client (fetch + renovação de sessão), endpoints tipados, types
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
  hooks/        useAuth (sessão), useApi (busca/escrita), useAppState (UI), useLocation
  lib/          tokens, dashboard, highlight, moduleStatus
  pages/        uma por tela, mais as de autenticação
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
backend). A tela diz isso e guarda o rascunho no navegador em vez de fingir
que enviou.
