FROM node:24.22.1-alpine3.23

WORKDIR /usr/src/app

COPY package*.json ./
ENV NODE_ENV=production
RUN npm ci --omit=dev

COPY . .

EXPOSE 8080
CMD ["npm", "start"]
