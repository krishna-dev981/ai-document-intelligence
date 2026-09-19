# Step 13.2 — React Frontend

## 1. Start FastAPI

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

FastAPI:
`http://127.0.0.1:8000`

Swagger:
`http://127.0.0.1:8000/docs`

## 2. Start React

Requirements: Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`).

## What this frontend supports

- PDF upload and indexing
- Multi-PDF document list
- Document/page retrieval scope
- ChatGPT-style chat UI
- Conversation history sent to the backend
- Conversation-aware retrieval
- Source citations
- Retrieval statistics
- Backend health indicator
- Clear chat
