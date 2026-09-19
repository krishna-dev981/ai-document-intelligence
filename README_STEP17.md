# AI Document Intelligence — Step 17
## Deployment-ready full-stack package

This version keeps the working Step 16 RAG application and adds containerized deployment support.

### Added
- Backend Dockerfile
- Frontend Dockerfile + Nginx SPA configuration
- Docker Compose orchestration
- Environment variable template
- Configurable CORS origins
- Public `/health` endpoint for deployment health probes
- Persistent Docker volumes for user/auth/storage data

## Option A — Continue running locally

### Backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

### Ollama
```powershell
ollama serve
ollama pull qwen2.5:3b
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

## Option B — Run with Docker Compose

Prerequisite: Docker Desktop must be installed and running.

1. Copy the environment template:
```powershell
Copy-Item .env.example .env
```

2. Open `.env` and replace `JWT_SECRET` with a long random value.

3. Build and start:
```powershell
docker compose up --build
```

4. Open:
- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

5. Stop:
```powershell
docker compose down
```

Persistent application data is stored in Docker volumes `app_storage` and `app_data`.

## Ollama note

The Compose setup points the backend container at Ollama running on the host through:
`http://host.docker.internal:11434`

Start Ollama on the host and make sure the model exists:
```powershell
ollama serve
ollama pull qwen2.5:3b
```

For a cloud deployment, you must provide a reachable LLM service instead of assuming host-local Ollama. This package does not claim that Ollama is automatically available on every cloud provider.

## Production checklist

- Set a strong `JWT_SECRET`.
- Set `ALLOWED_ORIGINS` to the real frontend origin(s), not `*`.
- Put HTTPS in front of the services using your hosting provider/reverse proxy.
- Back up persistent volumes.
- Do not commit `.env` or secrets to Git.
