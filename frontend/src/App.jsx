import React, { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "adi_access_token";

async function apiFetch(path, options = {}, token = localStorage.getItem(TOKEN_KEY)) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(`${API}${path}`, { ...options, headers });
}

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Authentication failed.");
      localStorage.setItem(TOKEN_KEY, data.access_token);
      onAuth(data.user);
    } catch (err) {
      setError(err.message);
    } finally { setBusy(false); }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">📚</div>
        <h1>AI Document Intelligence</h1>
        <p>{mode === "login" ? "Sign in to your private workspace" : "Create your private workspace"}</p>
        <form onSubmit={submit}>
          <label>Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="you@example.com" />
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} placeholder="Minimum 8 characters" />
          {error && <div className="error">{error}</div>}
          <button className="primary auth-submit" disabled={busy}>
            {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button className="auth-switch" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "New user? Create an account" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [files, setFiles] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState("");
  const [selectedPage, setSelectedPage] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    apiFetch("/auth/me", {}, token).then(async res => {
      if (!res.ok) { localStorage.removeItem(TOKEN_KEY); return; }
      setUser(await res.json());
    }).catch(() => localStorage.removeItem(TOKEN_KEY));
  }, []);

  async function loadState() {
    try {
      const [docsRes, healthRes, conversationsRes] = await Promise.all([
        apiFetch("/documents"), apiFetch("/health"), apiFetch("/conversations")
      ]);
      if ([docsRes, healthRes, conversationsRes].some(r => r.status === 401)) {
        logout(); return;
      }
      if (!docsRes.ok || !healthRes.ok || !conversationsRes.ok) throw new Error("Backend is not reachable.");
      const [docs, h, c] = await Promise.all([docsRes.json(), healthRes.json(), conversationsRes.json()]);
      setDocuments(docs.documents || []); setHealth(h); setConversations(c.conversations || []); setError("");
    } catch (e) {
      setError("Cannot connect to FastAPI. Start the backend with: uvicorn main:app --reload");
    }
  }

  useEffect(() => { if (user) loadState(); }, [user]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null); setMessages([]); setDocuments([]); setConversations([]); setConversationId(null);
  }

  async function uploadFiles() {
    if (!files.length) return;
    setUploading(true); setError("");
    try {
      const form = new FormData(); files.forEach(file => form.append("files", file));
      const res = await apiFetch("/documents/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed.");
      setFiles([]); document.getElementById("pdfInput").value = ""; await loadState();
    } catch (e) { setError(e.message); } finally { setUploading(false); }
  }

  function startNewChat() { setMessages([]); setQuestion(""); setError(""); setConversationId(null); }

  async function loadConversation(id) {
    if (loading || historyLoading) return;
    setHistoryLoading(true); setError("");
    try {
      const res = await apiFetch(`/conversations/${id}`); const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load conversation.");
      setConversationId(data.id); setMessages(data.messages || []);
    } catch (e) { setError(e.message); } finally { setHistoryLoading(false); }
  }

  async function deleteConversation(id) {
    if (!window.confirm("Delete this conversation?")) return;
    try {
      const res = await apiFetch(`/conversations/${id}`, { method: "DELETE" }); const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not delete conversation.");
      if (conversationId === id) startNewChat(); await loadState();
    } catch (e) { setError(e.message); }
  }

  async function askQuestion(e) {
    e?.preventDefault(); const q = question.trim();
    if (!q || loading) return;
    const userMessage = { role: "user", content: q }; const history = [...messages];
    setMessages(prev => [...prev, userMessage]); setQuestion(""); setLoading(true); setError("");
    try {
      const body = { question: q, history, document: selectedDocument || null,
        page: selectedPage ? Number(selectedPage) : null, conversation_id: conversationId };
      const res = await apiFetch("/chat", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Question failed.");
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, { role: "assistant", content: data.answer, sources: data.sources, retrieval: data.retrieval }]);
      await loadState();
    } catch (e) { setMessages(prev => prev.slice(0, -1)); setError(e.message); }
    finally { setLoading(false); }
  }

  const selectedMeta = useMemo(() => documents.find(d => d.name === selectedDocument), [documents, selectedDocument]);
  const pages = selectedMeta?.pages ? Array.from({ length: selectedMeta.pages }, (_, i) => i + 1) : [];

  if (!user) return <AuthScreen onAuth={setUser} />;

  return (
    <div className="app">
      <header className="topbar">
        <div><h1>📚 AI Document Intelligence</h1><p>Full-stack RAG • Private User Workspace</p></div>
        <div className="top-actions">
          <span className="user-email">👤 {user.email}</span>
          <button className="logout" onClick={logout}>Logout</button>
          <div className={`status ${health?.status === "ok" ? "online" : "offline"}`}><span /> {health?.status === "ok" ? "API Online" : "API Offline"}</div>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <section><h2>💬 Conversations</h2><button className="primary" onClick={startNewChat}>＋ New Chat</button>
            <div className="conversation-list">{conversations.length === 0 && <small>No saved conversations yet.</small>}
              {conversations.map(c => <div className={`conversation-item ${conversationId === c.id ? "active" : ""}`} key={c.id}>
                <button className="conversation-open" onClick={() => loadConversation(c.id)} title={c.title}>{c.title}</button>
                <button className="conversation-delete" onClick={() => deleteConversation(c.id)} title="Delete">×</button>
              </div>)}
            </div>
          </section>

          <section><h2>📄 Documents</h2><input id="pdfInput" type="file" accept=".pdf" multiple onChange={e => setFiles(Array.from(e.target.files || []))} />
            <button className="primary" onClick={uploadFiles} disabled={!files.length || uploading}>{uploading ? "Indexing..." : "Upload & Index"}</button>
            {files.length > 0 && <small>{files.length} file(s) selected</small>}
          </section>

          <section><h2>🎯 Retrieval Scope</h2><label>Document</label>
            <select value={selectedDocument} onChange={e => { setSelectedDocument(e.target.value); setSelectedPage(""); }}>
              <option value="">All Documents</option>{documents.map(d => <option key={d.name} value={d.name}>{d.name}</option>)}
            </select>
            <label>Page</label><select value={selectedPage} onChange={e => setSelectedPage(e.target.value)} disabled={!selectedDocument}>
              <option value="">All Pages</option>{pages.map(p => <option key={p} value={p}>Page {p}</option>)}
            </select>
          </section>

          <section><h2>📊 My Workspace</h2><div className="stats">
            <div><b>{health?.documents ?? documents.length}</b><span>Documents</span></div>
            <div><b>{health?.chunks ?? "—"}</b><span>Chunks</span></div>
          </div></section>
        </aside>

        <main className="chat">
          {messages.length === 0 && <div className="welcome"><div className="hero-icon">📚</div><h2>Ask questions about your documents</h2><p>Your documents and conversations are isolated to your account.</p></div>}
          <div className="messages">
            {messages.map((m, i) => <div className={`message ${m.role}`} key={i}><div className="avatar">{m.role === "user" ? "👤" : "🤖"}</div>
              <div className="bubble"><div className="content">{m.role === "assistant" ? <ReactMarkdown>{m.content}</ReactMarkdown> : m.content}</div>
                {m.sources?.length > 0 && <details className="sources"><summary>📚 Sources ({m.sources.length})</summary>
                  {m.sources.map(s => <div className="source" key={`${s.rank}-${s.document}-${s.page}`}><b>Source {s.rank}</b> · {s.document} · Page {s.page}<div>{s.text}</div></div>)}
                  {m.retrieval && <div className="retrieval">Query: {m.retrieval.query} · FAISS: {m.retrieval.faiss_results} · BM25: {m.retrieval.bm25_results} · Reranked: {m.retrieval.reranked} · {m.retrieval.latency_seconds}s</div>}
                </details>}
              </div></div>)}
            {loading && <div className="message assistant"><div className="avatar">🤖</div><div className="bubble typing">Searching documents and generating answer…</div></div>}
          </div>
          {error && <div className="error">⚠️ {error}</div>}
          <form className="composer" onSubmit={askQuestion}><input value={question} onChange={e => setQuestion(e.target.value)} placeholder={documents.length ? "Ask something about your documents..." : "Upload a PDF first..."} disabled={!documents.length || loading || historyLoading} /><button className="send" disabled={!question.trim() || loading || !documents.length}>➤</button></form>
          <div className="hint">Authentication enabled • Each account has isolated documents, indexes and conversations.</div>
        </main>
      </div>
    </div>
  );
}
export default App;
