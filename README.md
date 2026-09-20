# PathR

Plataforma de estudos e carreira em tecnologia: a pessoa envia o currículo, a
IA lê, e daí saem um plano de estudos, materiais, vagas que combinam e
candidaturas — com o currículo indo por e-mail quando o anúncio tem contato.

Em produção: <https://pathr.notter.com.br>

## O que tem dentro

| Parte | Stack | Pasta |
|---|---|---|
| API | Python 3.12, FastAPI, Supabase (Postgres + Storage), Alembic | [`backend/`](backend/) |
| Aplicação | React 18, TypeScript, Vite, PWA | [`frontend/`](frontend/) |
| Extensão de navegador | Manifest V3, JS puro | [`extensao/`](extensao/) |
| Infra e implantação | Fly.io (API), Cloudflare Pages (app) | [`deploy/`](deploy/), [`infra/`](infra/) |

Funcionalidades: roadmap gerado por IA, biblioteca de materiais com leitura e
vídeo embutidos, quizzes, treino de idiomas com voz, laboratório de código,
vagas, candidaturas por e-mail, eventos de tecnologia da sua região, amigos
com sequência de estudo em dupla, e cinco idiomas de interface.

## Rodando localmente

Você precisa de um projeto **próprio** no Supabase (o app não fala com o banco
de ninguém por padrão) e de pelo menos uma chave de IA.

```bash
# API
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Linux/macOS: . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local                          # preencha o que está vazio
alembic upgrade head
uvicorn app.main:app --reload --port 8031

# Aplicação
cd frontend
npm install
VITE_API_URL=http://localhost:8031 npm run dev
```

O [`.env.example`](backend/.env.example) documenta todas as variáveis, com o
porquê de cada uma. As que **precisam** de valor para subir: `SUPABASE_URL`,
`SUPABASE_SECRET_KEY`, `DATABASE_URL`, `JWT_SECRET_KEY`, `MFA_ENCRYPTION_KEY`,
`DATA_ENCRYPTION_KEY` e uma chave de IA.

Sem chave de e-mail (Brevo) o app sobe, mas ninguém confirma cadastro. Sem
chave de busca (Tavily/Brave) as abas de vagas e eventos ficam vazias, sem
erro.

### Testes

```bash
cd backend  && python -m pytest -q     # ~950 testes
cd frontend && npx vitest run          # ~290 testes
cd frontend && npx tsc -b --force      # tipos (use --force: o cache mente)
```

## Publicando a sua instalação

Nada aponta para a instalação original, desde que você declare:

- **backend**: `FRONTEND_URL` e `API_URL` — usados no User-Agent das buscas, no
  UID dos arquivos de calendário e no CORS;
- **frontend**: `VITE_API_URL` no build, e `SITE_URL` se quiser que as
  metatags de SEO apontem para o seu domínio;
- **`frontend/public/_headers`**: a CSP traz o host da API — ajuste ao seu.

### Se você publicar um fork

Os textos legais (termos, privacidade, segurança) nomeiam **quem opera** o
serviço e um endereço para pedidos sobre dados. `VITE_OPERADOR` e
`VITE_EMAIL_CONTATO` trocam esses dois valores — mas **isso não basta**: o
texto descreve Supabase, Fly, Brevo e as decisões desta operação. Publicar sem
reescrevê-lo é prometer, em nome de outra pessoa, o que só ela pode cumprir.

`SUPER_ADMIN_EMAILS` e `MODERATOR_EMAILS` começam **vazios**, de propósito:
com um e-mail fixo no código, toda cópia nasceria dando poder de administração
a quem escreveu o projeto. Declare os seus.

## Convenções deste código

Duas que surpreendem quem chega:

1. **O código é escrito em português** — nomes de função, variáveis,
   comentários e mensagens. O projeto nasceu assim e é consistente do começo
   ao fim; metade em cada língua seria pior que qualquer uma das duas.
2. **Comentário explica POR QUE, não O QUE.** A maioria registra a decisão e o
   defeito que a motivou. Se for mudar algo que tem um comentário desses, leia
   antes: ele costuma descrever o problema que volta.

## Contribuindo

Antes de um PR grande, abra uma issue — o projeto tem opiniões fortes sobre
tratamento de dados (nada de valor inventado na tela) e sobre segurança
(currículo e respostas são cifrados no banco).

Rode os testes antes de enviar. Comportamento novo precisa de teste que falhe
sem a mudança.

## Licença

[AGPL-3.0](LICENSE). Em resumo: use, estude, modifique e distribua à vontade —
mas se rodar uma versão modificada **como serviço para outras pessoas**, é
preciso publicar o código dessa versão.
