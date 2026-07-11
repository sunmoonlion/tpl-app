ARG NODE_IMAGE=node:22.22.0-alpine
ARG NGINX_IMAGE=harbor.sunmoonai.com:30443/k8s-images/nginx:stable-alpine
ARG NPM_CONFIG_REGISTRY=https://registry.npmmirror.com

FROM ${NODE_IMAGE} AS build
ARG NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
ARG VITE_API_URL
ARG VITE_APP_NAME="Template Admin"
ARG VITE_DEFAULT_LOCALE=zh-CN
ARG BASE_PATH=/
ENV npm_config_registry=${NPM_CONFIG_REGISTRY} \
    COREPACK_NPM_REGISTRY=${NPM_CONFIG_REGISTRY} \
    COREPACK_INTEGRITY_KEYS=0 \
    npm_config_fetch_retries=5 \
    npm_config_fetch_retry_maxtimeout=120000 \
    npm_config_fetch_timeout=600000 \
    VITE_API_URL=${VITE_API_URL} \
    VITE_APP_NAME=${VITE_APP_NAME} \
    VITE_DEFAULT_LOCALE=${VITE_DEFAULT_LOCALE} \
    BASE_PATH=${BASE_PATH} \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

RUN npm install -g pnpm@9.15.4 \
    --registry="${NPM_CONFIG_REGISTRY}" \
    --fetch-retries=5 \
    --fetch-retry-maxtimeout=120000 \
    --fetch-timeout=600000
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store pnpm config set store-dir /pnpm/store && pnpm install --frozen-lockfile
COPY . .
RUN pnpm typecheck && pnpm test && pnpm build

FROM ${NGINX_IMAGE} AS run
COPY --from=build /app/build/client /usr/share/nginx/html
COPY mybuild/nginx.conf /etc/nginx/conf.d/default.conf
COPY mybuild/security-headers.inc /etc/nginx/conf.d/security-headers.inc
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
