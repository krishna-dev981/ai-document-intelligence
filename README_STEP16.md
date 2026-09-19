# AI Document Intelligence — Step 16

This package contains the complete FastAPI backend and React/Vite frontend.

## Features
- User registration and login with JWT
- Private per-user document storage
- Multi-PDF upload and indexing
- FAISS semantic retrieval
- BM25 keyword retrieval
- Reciprocal Rank Fusion
- Cross-encoder reranking
- Document/page retrieval scope
- Conversation history
- Source citations and retrieval statistics
- Ollama-powered grounded answers
- Configurable frontend API URL

## 1. Start the backend

Open Terminal 1:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend: http://127.0.0.1:8000  
Swagger: http://127.0.0.1:8000/docs

Make sure Ollama is installed and the model is available:

```bash
ollama pull qwen2.5:3b
```

## 2. Start the frontend

Open Terminal 2:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open the Vite URL shown in the terminal, normally:

http://localhost:5173

## Important
- Start the backend first.
- Keep the backend terminal running.
- Use a PDF with selectable text. Scanned image-only PDFs may not extract text.
- If the frontend cannot connect, check `frontend/.env` and confirm the backend is running.
