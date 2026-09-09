#!/bin/sh
# Roda as migrations pendentes e SÓ ENTÃO sobe o servidor.
#
# Duas razões para ser um script, e não um comando composto no render.yaml:
#
# 1. **A ordem importa.** Sem `alembic upgrade head` no boot, uma migration
#    nova só chega ao banco se alguém lembrar de rodá-la à mão depois do
#    deploy. Até lá, toda rota que tocar a tabela nova responde 500 porque o
#    PostgREST não reconhece o schema. Rodar como parte do boot elimina essa
#    janela — e se a migration falhar, o deploy falha alto (o Render marca o
#    serviço como não saudável) em vez de subir com app e banco fora de
#    sincronia em silêncio.
#
# 2. **O Render não tokeniza `sh -c "a && b"` como se espera** — trata a
#    string inteira como um único nome de comando e falha com "not found".
#    Um arquivo de script não depende desse detalhe. (O Notter passou por
#    isso; ver o comentário no render.yaml de lá.)
#
# `$PORT` vem do Render. Localmente, o docker-compose.prod.yml define 8031.
set -e

alembic upgrade head

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8031}" \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips "*"
