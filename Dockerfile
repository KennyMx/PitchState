FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY index.html tsconfig*.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.10-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r server/requirements.txt
COPY server ./server
COPY docs/TACTICAL_REFERENCE.md ./docs/TACTICAL_REFERENCE.md
COPY --from=frontend /app/dist ./dist
RUN useradd --uid 10001 --create-home pitchstate && mkdir models data .local && chown -R pitchstate:pitchstate /app
USER pitchstate
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server.pitchstate.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
