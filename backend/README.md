# PathR — backend

API do PathR. FastAPI sobre um projeto Supabase **exclusivo deste app** —
banco, storage, chaves de IA e remetente de e-mail são todos próprios. O
Notter só oferece um link que abre `pathr.notter.com.br` numa aba nova; não há
nada compartilhado entre os dois em runtime.

## Rodar

```bash
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r requirements-dev.txt
cp .env.example .env.local                        # preencha
python -m scripts.bootstrap                       # migrations + bucket + catálogo
uvicorn app.main:app --reload --port 8031
```

O `bootstrap` prepara um projeto Supabase novo do zero e é idempotente; use
`--check` para diagnosticar sem escrever. Ver deploy/README.md.

`http://localhost:8031/docs` lista os 51 endpoints (desligado em produção).

```bash
pytest        # 31 testes, 100% offline — sem banco, sem chave, sem rede
```

## Como está montado

```
app/
  config.py          Settings. Todo segredo com default vazio: o app sobe sem eles.
  database.py        Cliente Supabase com retry de conexão e de 429/503.
  security.py        Argon2id, TOTP, Fernet, JWT, bloqueio por tentativas. Funções puras.
  deps.py            Quem está chamando (cookie ou Bearer) e de onde (IP real).
  ai_providers.py    Rotação entre provedores de IA. Portado do Notter.
  models.py          O schema. 28 tabelas, todas com prefixo pathr_.
  routers/           auth, profile, resumes, tags, roadmap, library, quizzes, english
  services/          text_extract, resume_parser, tag_catalog, tag_seed,
                     roadmap_builder, progress, email
```

### Sessão

Um par de cookies HttpOnly: JWT curto (`pathr_access`, 30 min) que carrega o
id da linha de sessão, e token opaco longo (`pathr_refresh`, 30 dias). O JWT
carregar o `sid` é o que faz "sair de todos os dispositivos" valer
imediatamente — sem isso, um JWT revogado seguiria aceito até expirar.

O refresh **rotaciona**: cada uso queima o token e emite outro, guardando de
qual veio. Se um token já usado reaparecer, isso é cookie copiado, e a
resposta é derrubar todas as sessões daquele usuário.

### O nível decide a forma do módulo

O plano não exclui nada por nível — ele muda o FORMATO. Até N2 é módulo de
ensino. De N3 para cima é revisão: um checkpoint de no máximo 2h com o caso
difícil, a armadilha de produção e a decisão de arquitetura, e exercícios de
nível avançado. Nunca do zero — quem está em N4 lendo "o que é um container"
fecha o app.

A revisão tem teto (uma por fase, 10% do orçamento de horas) e é a segunda
coisa cortada quando o prazo não fecha, depois do que está em zero e o
objetivo não exige. Reforço é bom; gastar metade do prazo repassando o que a
pessoa já sabe, não.

### Avisos entre aparelhos

`GET /events` é um canal SSE por usuário: quando uma escrita passa, todas as
telas abertas daquela conta recebem um empurrão para reconsultar. O aviso não
carrega dado — carregar criaria uma segunda forma de o cliente aprender a
verdade, e duas formas divergem.

Quem publica é um middleware (`AvisaOutrasTelas` em `app/main.py`), não cada
rota. São mais de vinte endpoints de escrita e o produto ganha outros toda
semana; uma chamada por rota é uma lista que envelhece calada — a rota nova
nasce sem o aviso, os outros aparelhos param de ver aquela mudança, e nada
quebra para denunciar.

`services/eventos.py` tem duas camadas. A fila em memória entrega a quem está
ouvindo NESTE processo; o `LISTEN/NOTIFY` do Postgres leva o aviso às outras
máquinas — a Fly pode ter mais de uma no ar. A segunda exige conexão DIRETA
com o banco: o pooler em modo transação do Supabase (porta 6543) não suporta
`LISTEN`, e nesse caso o listener registra o motivo e o app segue com avisos
restritos à própria máquina. É degradação por desenho, não falha: o cliente
reconfere ao voltar ao foco, então nada aqui precisa de garantia de entrega.

### Rotação de IA

`app/ai_providers.py`, portado do Notter pelo mesmo motivo que o levou a
existir lá: uma cota de tier gratuito estourada derrubaria de uma vez a
leitura de currículo, a geração de roadmap, os quizzes e o módulo de idioma.

- **Várias chaves por provedor.** `GEMINI_API_KEY=k1,k2,k3` vira três
  candidatos com cotas independentes.
- **Cooldown persistido** em `pathr_ai_provider_cooldown`. Persistir importa
  porque o processo reinicia e a cota diária não.
- **Nunca desiste cedo.** Candidato em cooldown é rebaixado para o fim da
  fila, nunca removido.

As chaves de IA são **exclusivas do PathR** — contas e cotas próprias. Por
isso o cooldown vive numa tabela deste banco: ele reflete a cota daqui, e não a
de terceiros.

### Leitura de currículo

Quatro requisições, uma por etapa, porque só a segunda é lenta e só ela pode
falhar por cota de terceiro:

1. `POST /resumes` — recebe, guarda no Storage, responde na hora.
2. `POST /resumes/{id}/parse` — chama a IA.
3. `GET /resumes/{id}` — o que a IA leu, para revisão.
4. `POST /resumes/{id}/apply` — só depois da revisão vira `pathr_user_tag`.

O PDF vai **inteiro para o modelo** (`generate_json_with_media`), não só o
texto extraído: currículo é documento visual, e a extração de texto intercala
colunas e perde as barras de nível. De quebra, resolve PDF escaneado por OCR
do próprio modelo. Se o Gemini estiver sem cota, cai para o texto extraído
com a rotação completa — pior qualidade, mas responde.

Reenviar o mesmo arquivo não gasta IA: o SHA-256 é chave.

### Proficiência

A escala é 0..5 e a **confiança** é o que separa palpite de evidência:

| Origem | confidence | Por quê |
| --- | --- | --- |
| currículo | 0,4 | é o que a pessoa escreveu sobre si |
| edição manual | 0,8 | ela afirmou conscientemente |
| módulo concluído | +0,2, teto 3 | estudou; não prova domínio |
| quiz | +0,25 | a única evidência de verdade |

Só o quiz sobe além de 3, e só nos extremos (>=80% sobe, <40% desce). A faixa
do meio não mexe em nada: um 60% não é evidência de nada em particular, e
oscilar o perfil a cada quiz faria o roadmap se reescrever sem motivo.

## Decisões que talvez surpreendam

- **Um worker por instância.** O espelho de cooldown da rotação vive em
  memória por processo. Escalar é subir instâncias.
- **PostgREST, não SQLAlchemy, em runtime.** SQLModel existe só para o
  Alembic descrever o schema; os routers falam com o banco por `supabase-py`.
- **O prefixo `pathr_` ficou, mesmo com banco próprio.** Não é mais para
  evitar colisão: é para evitar `user`, palavra reservada no Postgres.
  Prefixar só essa tabela seria a exceção que se esquece. O filtro em
  `alembic/env.py` continua como rede contra um `DATABASE_URL` apontado para o
  banco errado. Nenhuma migration rodou ainda, então tirar o prefixo segue
  barato.
- **A suíte é offline.** Roda em 1 segundo sem chave e sem rede — é o que faz
  alguém executá-la antes de commitar.
