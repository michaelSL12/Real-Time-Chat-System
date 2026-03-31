# Use a lightweight Node image for local frontend development.
FROM node:20-alpine

WORKDIR /app

# Install dependencies first to improve Docker layer caching.
COPY package*.json ./

RUN npm install

# Copy the rest of the frontend source code.
COPY . .

# Expose the Vite development server port.
EXPOSE 5173

# Run the Vite dev server and bind it to all interfaces
# so it is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]