# Build do SPA. O resultado é estático — quem serve é o Caddy (ou uma CDN,
# se um dia o app sair deste host).
FROM node:22-alpine AS build

WORKDIR /app

# Dependências primeiro: enquanto o lockfile não mudar, esta camada é
# reaproveitada e um deploy que só mexeu em src/ não reinstala nada.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# A URL da API entra em tempo de BUILD porque o Vite substitui
# import.meta.env.* no bundle — não há como ler variável de ambiente depois,
# num arquivo estático servido por CDN.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# Imagem final mínima: só o dist, para o volume compartilhado com o Caddy.
FROM alpine:3.20
WORKDIR /app
COPY --from=build /app/dist ./dist
