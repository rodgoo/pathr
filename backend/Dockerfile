# Imagem do backend do PathR.
#
# slim e não alpine: os wheels de cryptography, argon2-cffi e pillow existem
# prontos para glibc, e no alpine (musl) o pip os compilaria do zero — build
# de minutos em vez de segundos, para economizar poucos megabytes.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# As dependências vêm antes do código de propósito: enquanto
# requirements.txt não mudar, o Docker reaproveita esta camada e um deploy
# que só mexeu em app/ não reinstala nada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY alembic.ini start.sh ./
RUN chmod +x start.sh

# Usuário sem privilégio: se alguém escapar do processo, escapa como ninguém.
RUN useradd --create-home --uid 10001 pathr && chown -R pathr:pathr /app
USER pathr

# Só documenta a porta do deploy self-host; no Render quem manda é $PORT.
EXPOSE 8031

# Migrations e depois o servidor — ver start.sh. Um worker só: o espelho em
# memória do cooldown da rotação de IA é por processo, então escalar aqui é
# subir instâncias, não workers.
CMD ["sh", "start.sh"]
