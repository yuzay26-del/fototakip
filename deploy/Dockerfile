# Bağlam: repo kökü  →  docker build -f deploy/Dockerfile .
FROM node:22-alpine AS web
WORKDIR /src
COPY api/ api/
COPY web/package*.json web/
RUN cd web && (if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi)
COPY web/ web/
RUN cd web && npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WEB_DIST=/app/web-dist
WORKDIR /app/backend
COPY backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /src/web/dist /app/web-dist
EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
