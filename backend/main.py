from pathlib import Path
import io
import sys
import time
import os
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.pdf_processor import extract_text, create_chunks
from src.embeddings import load_embedding_model
from src.retrieval import (
    build_bm25, semantic_search, semantic_search_filtered,
    keyword_search, keyword_search_filtered,
    reciprocal_rank_fusion, load_reranker, rerank,
)
from src.storage import (
    sha256, load_documents, save_documents,
    rebuild_vector_store, add_chunks_to_vector_store, load_vector_store,
)
from src.llm import chat
from src.chat_history import (
    init_db, ensure_conversation, create_conversation,
    list_conversations, get_conversation, add_message, delete_conversation,
)
from src.auth import (
    init_auth_db, create_user, authenticate_user, get_user,
    create_access_token, decode_access_token,
)
from src.user_storage import user_storage_dir, migrate_legacy_data

app = FastAPI(title="AI Document Intelligence API", version="1.3.0")

_default_origins = "http://localhost:3000,http://localhost:5173"
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

embedding_model = load_embedding_model()
reranker = load_reranker()
security = HTTPBearer(auto_error=False)
init_auth_db()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    document: str | None = None
    page: int | None = None
    conversation_id: str | None = None


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Missing user id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    migrate_legacy_data(user_id)
    return user


def workspace(user_id: str):
    path = user_storage_dir(user_id)
    init_db(path)
    return path


def load_user_state(user_id: str):
    path = workspace(user_id)
    documents = load_documents(path)
    index, _ = load_vector_store(path)
    chunks = []
    for meta in documents.values():
        chunks.extend(meta.get("chunks", []))
    bm25 = build_bm25(chunks) if chunks else None
    return path, documents, index, chunks, bm25


def retrieval_query(question: str, history: list[ChatMessage]) -> str:
    previous = [m.content.strip() for m in history if m.role == "user" and m.content.strip()][-3:]
    if len(previous) <= 1:
        return question
    return "Previous user questions: " + " | ".join(previous[:-1]) + " | Current question: " + question


@app.get("/health")
def health() -> dict[str, Any]:
    """Public process health endpoint for deployment probes."""
    return {"status": "ok", "service": "ai-document-intelligence-api"}


@app.get("/health/workspace")
def health_workspace(user=Depends(current_user)) -> dict[str, Any]:
    _, documents, index, chunks, _ = load_user_state(user["id"])
    return {"status": "ok", "user": user["email"], "documents": len(documents), "chunks": len(chunks), "indexed": index is not None}


@app.get("/auth/me")
def me(user=Depends(current_user)):
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


@app.post("/auth/register")
def register(request: RegisterRequest):
    if "@" not in request.email or "." not in request.email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    user = create_user(request.email, request.password)
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    token = create_access_token(user)
    migrate_legacy_data(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/auth/login")
def login(request: LoginRequest):
    user = authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_access_token(user)
    migrate_legacy_data(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": {
        "id": user["id"], "email": user["email"], "created_at": user["created_at"]
    }}


@app.get("/documents")
def list_documents(user=Depends(current_user)) -> dict[str, Any]:
    _, documents, _, _, _ = load_user_state(user["id"])
    return {"documents": [
        {"name": name, "pages": meta.get("pages", 0), "chunks": meta.get("chunks_count", 0)}
        for name, meta in documents.items()
    ]}


@app.post("/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...), user=Depends(current_user)) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files uploaded.")
    path, documents, _, _, _ = load_user_state(user["id"])
    new_chunks, replaced, added, reused = [], False, 0, 0

    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{upload.filename or 'File'} is not a PDF.")
        data = await upload.read()
        digest = sha256(data)
        existing = documents.get(upload.filename)
        if existing and existing.get("hash") == digest:
            reused += 1
            continue
        pages = extract_text(io.BytesIO(data))
        if not pages:
            raise HTTPException(status_code=422, detail=f"{upload.filename} has no extractable text.")
        made = create_chunks(pages, upload.filename)
        if not made:
            raise HTTPException(status_code=422, detail=f"No chunks created for {upload.filename}.")
        documents[upload.filename] = {
            "hash": digest, "pages": len(pages), "chunks_count": len(made), "chunks": made,
        }
        if existing:
            replaced = True
        else:
            added += 1
            new_chunks.extend(made)

    if replaced:
        all_chunks = []
        for meta in documents.values():
            all_chunks.extend(meta.get("chunks", []))
        rebuild_vector_store(all_chunks, embedding_model, path)
    elif new_chunks:
        add_chunks_to_vector_store(new_chunks, embedding_model, path)

    save_documents(documents, path)
    _, documents, index, chunks, _ = load_user_state(user["id"])
    return {"added": added, "reused": reused, "updated": int(replaced),
            "documents": len(documents), "chunks": len(chunks), "indexed": index is not None}


@app.post("/conversations")
def new_conversation(user=Depends(current_user)):
    path = workspace(user["id"])
    return {"conversation_id": create_conversation(storage_dir=path)}


@app.get("/conversations")
def conversations(user=Depends(current_user)):
    path = workspace(user["id"])
    return {"conversations": list_conversations(path)}


@app.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str, user=Depends(current_user)):
    path = workspace(user["id"])
    conversation = get_conversation(conversation_id, path)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@app.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: str, user=Depends(current_user)):
    path = workspace(user["id"])
    if not delete_conversation(conversation_id, path):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"deleted": True}


@app.post("/chat")
def chat_endpoint(request: ChatRequest, user=Depends(current_user)) -> dict[str, Any]:
    path, documents, index, chunks, bm25 = load_user_state(user["id"])
    if index is None or not chunks or bm25 is None:
        raise HTTPException(status_code=400, detail="Upload and index at least one PDF first.")

    start = time.perf_counter()
    strict = request.document is not None
    query = retrieval_query(request.question, request.history)

    if strict:
        faiss_scores, faiss_indices = semantic_search_filtered(
            index, embedding_model, query, chunks, 20, request.document, request.page)
        bm25_scores, bm25_indices = keyword_search_filtered(
            bm25, query, chunks, 20, request.document, request.page)
    else:
        faiss_scores, faiss_indices = semantic_search(index, embedding_model, query, 20)
        bm25_scores, bm25_indices = keyword_search(bm25, query, 20)

    candidate_ids = reciprocal_rank_fusion(faiss_indices, bm25_indices, k=60)[:20]
    candidates = [chunks[i] for i in candidate_ids]
    ranked = rerank(reranker, query, candidates, top_k=5)
    if strict:
        ranked = [(c, s) for c, s in ranked if c.get("filename") == request.document and
                  (request.page is None or int(c.get("page", -1)) == request.page)]

    context = "\n\n".join(
        f"[Source {i}]\n[Document: {c['filename']}]\n[Page: {c['page']}]\n{c['text']}"
        for i, (c, _) in enumerate(ranked, 1)
    ) or "No relevant document context was retrieved."

    history = [m.model_dump() for m in request.history]
    answer = chat(request.question, context, history, strict_scope=strict)
    sources = [
        {"rank": i, "document": c["filename"], "page": c["page"],
         "score": float(score), "text": c["text"]}
        for i, (c, score) in enumerate(ranked, 1)
    ]
    retrieval = {
        "query": query, "faiss_results": len(faiss_indices),
        "bm25_results": len(bm25_indices), "candidates": len(candidates),
        "reranked": len(ranked),
        "latency_seconds": round(time.perf_counter() - start, 3),
    }

    conversation_id = ensure_conversation(
        request.conversation_id, request.question[:80] or "New conversation", path
    )
    add_message(conversation_id, "user", request.question, storage_dir=path)
    add_message(conversation_id, "assistant", answer, sources=sources, retrieval=retrieval, storage_dir=path)

    return {"conversation_id": conversation_id, "answer": answer,
            "sources": sources, "retrieval": retrieval}
