# === STAGE 1: BACKEND ENVIRONMENT ===
FROM python:3.9-slim AS backend
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

# === STAGE 2: FRONTEND BUILD ===
FROM node:18-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json .
RUN npm install
COPY frontend/ .
RUN npm run build

# === STAGE 3: FINAL PRODUCTION RUNNER ===
FROM python:3.9-slim
WORKDIR /app
COPY --from=backend /app/backend /app/backend
COPY --from=frontend /app/frontend/dist /app/frontend/dist
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
