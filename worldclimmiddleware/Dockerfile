FROM node:13.11.0-stretch

WORKDIR /usr/src/app

COPY package*.json ./
ENV NODE_ENV=production
RUN npm ci --omit=dev

COPY . .

EXPOSE 8080
CMD ["npm", "start"]
