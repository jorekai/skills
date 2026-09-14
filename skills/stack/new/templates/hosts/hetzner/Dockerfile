# The container for {{NAME}} on a host the project rents. Two stages: one that installs and
# builds, one that carries only what runs. The app lives under /srv/app and runs as its own user.
FROM node:{{NODE}}-alpine AS build
WORKDIR /srv/app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps ./apps
COPY packages ./packages
COPY tsconfig.base.json tsconfig.json stack.yaml ./
RUN pnpm install --frozen-lockfile
RUN pnpm --filter web build

FROM node:{{NODE}}-alpine AS run
WORKDIR /srv/app
ENV NODE_ENV=production
ENV PORT=3000
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /srv/app/apps/web/.next/standalone ./
COPY --from=build --chown=app:app /srv/app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=app:app /srv/app/apps/web/public ./apps/web/public
USER app
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
