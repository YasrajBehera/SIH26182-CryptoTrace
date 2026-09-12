FROM node:20-alpine

WORKDIR /srv/cryptotrace-frontend

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_PROXY_TARGET=http://127.0.0.1:8000
ENV VITE_API_PROXY_TARGET=${VITE_API_PROXY_TARGET}

RUN npm run build

EXPOSE 4173

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]