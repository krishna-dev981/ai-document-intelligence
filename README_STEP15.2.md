# AI Document Intelligence — Step 15.2

## What's new
- Local email/password registration and login
- JWT access tokens
- Protected API endpoints
- Logout
- Per-user document storage and FAISS index
- Per-user conversation database
- User-to-user data isolation
- Automatic one-time migration of Step 15.1 legacy storage to the first account
- React Markdown answers retained

## Backend
```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Ollama must be running and the model should exist:
```powershell
ollama run qwen2.5:3b
```

Optional stronger JWT secret:
```powershell
$env:JWT_SECRET="replace-with-a-long-random-secret"
```

## Frontend
```powershell
cd frontend
npm install
npm run dev
```

Open:
http://localhost:5173

## Test
1. Create an account.
2. Upload a PDF.
3. Ask a question.
4. Confirm conversation is saved.
5. Logout.
6. Create a second account.
7. The second account should start with its own empty workspace and cannot see the first account's documents or conversations.

### Important
The first account created after upgrading from Step 15.1 receives the old global Step 15.1 documents and conversations through a one-time migration. New accounts are isolated.
