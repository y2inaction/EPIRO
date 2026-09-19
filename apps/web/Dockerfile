FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production

COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

# next start needs the build output and the config. The previous version also
# copied ./public, which does not exist in this repository, so the image could
# never actually be built.
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.js ./next.config.js

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs && chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["npm", "start"]
