FROM node:18-alpine

WORKDIR /app

COPY web_v2/package.json .
RUN npm install

COPY web_v2/ .

EXPOSE 3000

CMD ["node", "server.js"]