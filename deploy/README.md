# Deploy — pathr.notter.com.br

O PathR sobe como subdomínio do Notter. Dois hosts, mesmo domínio registrável:

| Host | O que é |
| --- | --- |
| `pathr.notter.com.br` | O app (SPA estático) |
| `api.pathr.notter.com.br` | Esta API |

## Por que dois hosts, e não `/api` no mesmo

Separar deixa o SPA ser servido como arquivo estático puro (cacheável para
sempre, sem passar por um servidor de aplicação) e a API ter o próprio ciclo
de deploy. O custo disso costuma ser o cookie de sessão — mas aqui não há
custo: `pathr.notter.com.br` e `api.pathr.notter.com.br` são **same-site**
(mesmo domínio registrável `notter.com.br`), então `SameSite=Strict` continua
valendo e o cookie acompanha as requisições do app.

Isso só funciona com `COOKIE_DOMAIN=.notter.com.br` — com o ponto na frente.
Sem ele, o cookie fica preso ao host que o emitiu (a API) e o app nunca o
envia.

> Se um dia a API sair de `notter.com.br`, a relação vira cross-site e nada
> abaixo de `SameSite=None` funciona — perdendo a proteção contra CSRF que o
> Strict dá de graça. Não vale a economia.

## Como se chega ao PathR

O PathR é um **site independente**. `pathr.notter.com.br` é o endereço de
verdade: a pessoa chega, cria conta, faz login e usa o app ali. Nada dele roda
dentro do Notter.

O Notter tem só um **atalho** — um link no card "Da mesma autoria", no rodapé
da sidebar, que abre `pathr.notter.com.br` numa aba nova
(`target="_blank"`). É o começo e o fim do acoplamento entre os dois na
experiência de quem usa.

**Nada é compartilhado**, além do link:

| | |
| --- | --- |
| Projeto Supabase | próprio — banco e storage exclusivos do PathR |
| Contas e login | próprios — `pathr_user`, com senha e MFA deste app |
| Sessão | própria — cookie host-only em `api.pathr.notter.com.br`, nunca enviado ao Notter |
| Chaves de IA | próprias — contas e cotas deste app |
| E-mail transacional | próprio — remetente e domínio verificado do PathR |
| Frontend e backend | próprios — outro build, outro serviço, outro deploy |

A única coisa em comum é o **domínio registrável `notter.com.br`**, e ele é
usado para uma coisa só: deixar a sessão do PathR valer entre
`pathr.notter.com.br` e `api.pathr.notter.com.br` com `SameSite=Strict`. São
os dois hosts DELE — o cookie é host-only e nunca chega ao Notter.

Esse atalho é ligado por uma variável no build do Notter:

```
# Notes/frontend/.env.example
VITE_PATHR_URL=https://pathr.notter.com.br
```

Sem ela, o atalho não existe — o Notter é open-source e uma URL embutida faria
toda instalação self-hosted anunciar este app. Diferente do FinanceR, o PathR
não tem allowlist ali: tem cadastro aberto, então esconder o link não
protegeria nada.

## DNS

Na zona `notter.com.br`, dois registros apontando para o host do PathR:

```
pathr        A    <IP do servidor>
api.pathr    A    <IP do servidor>
```

Se o Notter usa Cloudflare, deixe os dois com proxy **desligado** (nuvem
cinza) até o Caddy emitir os certificados — o desafio HTTP-01 do Let's
Encrypt precisa alcançar a porta 80 do servidor diretamente. Depois de o
primeiro certificado sair, o proxy pode ser religado.

## Duas rotas de deploy

| | Render (sem servidor próprio) | Self-host (VPS) |
| --- | --- | --- |
| Backend | `render.yaml` (Blueprint, plano free) | `docker-compose.prod.yml` + Caddy |
| Frontend | Cloudflare Pages (build estático) | o mesmo compose serve o `dist/` |
| TLS | do Render / Cloudflare | Caddy, Let's Encrypt automático |
| Custo | zero | a VPS |
| Ressalva | dorme após 15 min sem tráfego (30-60s no primeiro acesso) | sempre ligado |

### O ponto que decide se a sessão funciona

O cookie é `SameSite=Strict`, o que exige API e app no **mesmo domínio
registrável**. Com o host padrão do Render (`pathr-backend.onrender.com`)
contra `pathr.notter.com.br`, isso é cross-site: o navegador não envia o
cookie, e a pessoa entra e cai de volta no login.

Antes de usar em produção, adicione o domínio customizado
`api.pathr.notter.com.br` ao serviço (Render → Settings → Custom Domains,
disponível no plano free) e aponte o CNAME. Só então `COOKIE_DOMAIN` e
`COOKIE_SAMESITE=strict` do `render.yaml` fazem sentido.

> Baixar para `COOKIE_SAMESITE=none` faria a sessão funcionar em qualquer
> domínio, ao preço da proteção contra CSRF que o Strict dá de graça. Serve
> para um ambiente de teste; não para produção.

## Antes do primeiro deploy

### 1. Crie o projeto Supabase (manual)

supabase.com → **New project**, exclusivo do PathR. É o único passo que não dá
para automatizar daqui: é uma ação na sua conta.

Anote, em Project Settings → API e → Database:

- `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` — a string do **pooler** (`aws-...pooler.supabase.com`), não
  a do host direto: `db.<ref>.supabase.co` resolve só em IPv6 e o Render não
  alcança.

### 2. Preencha o `.env.local` e rode o bootstrap

```bash
cd backend
cp .env.example .env.local        # preencha
python -m scripts.bootstrap --check   # diagnostica sem escrever
python -m scripts.bootstrap           # aplica
```

Ele faz os três passos que um projeto novo precisa, em ordem, e confere cada
um:

| | |
| --- | --- |
| migrations | cria as 28 tabelas `pathr_` |
| bucket | cria `pathr-resumes`, **privado** |
| catálogo | insere as 91 tags base |

É idempotente — rodar de novo não duplica nada. A verificação prévia recusa
credenciais ainda com o valor de exemplo **antes** de escrever qualquer coisa,
para não deixar metade dos passos aplicados no banco errado.

O catálogo importa mais do que parece: sem ele cada currículo cria tags do zero
e sem apelidos, e o CV que escreve "postgres" e o que escreve "PostgreSQL"
viram dois assuntos diferentes. (`scripts/seed_tags.py` faz só essa parte, se
precisar reexecutar isolado.)

No Render, rode pelo Shell do serviço; no self-host,
`docker compose -f docker-compose.prod.yml run --rm pathr-backend python -m scripts.bootstrap`.

## Subir

```bash
cp backend/.env.example .env.local     # preencha tudo
cat >> .env.local <<'EOF'
DOMAIN_APP=pathr.notter.com.br
DOMAIN_API=api.pathr.notter.com.br
ACME_EMAIL=voce@exemplo.com
EOF

docker compose -f docker-compose.prod.yml up -d --build
```

O Caddy emite e renova os certificados sozinho. Portas 80 e 443 precisam
estar abertas.

## Migrations

O schema vive no projeto Supabase do próprio PathR, com todas as tabelas
prefixadas `pathr_`. O prefixo não é mais para evitar colisão — é para evitar
`user`, palavra reservada no Postgres. O filtro do Alembic
(`backend/alembic/env.py`) continua como rede de proteção: um `DATABASE_URL`
apontado por engano para outro banco produz uma migration vazia em vez de uma
que apaga o que não reconhece.

```bash
docker compose -f docker-compose.prod.yml run --rm pathr-backend alembic upgrade head
```

Use a string de conexão do **pooler** (`aws-...pooler.supabase.com`) em
`DATABASE_URL`: o host direto `db.<ref>.supabase.co` resolve apenas em IPv6.

## Storage

Crie o bucket `pathr-resumes` no Supabase como **privado**. É onde ficam os
PDFs de currículo; o backend lê e escreve com a service_role key, e nenhum
arquivo é servido diretamente ao navegador.

## Provedores de IA

Ao menos `GEMINI_API_KEY` precisa estar configurada: o Gemini é o único
provedor com visão nas configurações deste app, e é ele que lê o PDF do
currículo direto (preservando layout de duas colunas e resolvendo PDF
escaneado por OCR). Os outros quatro entram na rotação do caminho de texto.

Cada chave aceita **lista separada por vírgula** — `GEMINI_API_KEY=k1,k2,k3`
vira três candidatos com cotas independentes. É a forma mais barata de
aumentar o teto diário sem pagar nada.

## Operação

- Saúde: `https://api.pathr.notter.com.br/health`
- O `/docs` fica desligado em produção (`ENVIRONMENT=production`) — ele
  descreveria toda a superfície de autenticação para quem estivesse olhando.
- Um worker só por instância, de propósito: o espelho em memória do cooldown
  da rotação de IA é por processo. Escalar é subir instâncias, não workers.
