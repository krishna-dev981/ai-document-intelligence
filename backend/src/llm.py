import ollama

MODEL_NAME = "qwen2.5:3b"




def understand_query(question, strict_scope=False):
    """Classify a user question and extract retrieval signals.

    The model is used only to understand the query; it does not answer it.
    A conservative fallback keeps retrieval working if Ollama is unavailable.
    """
    scope_rule = (
        "The search is restricted to the selected document/page."
        if strict_scope else
        "The search can use the full document collection."
    )
    prompt = f"""
Analyze the user's document question for retrieval. Do NOT answer it.
Return exactly four lines in this format:
INTENT: <one of factual, procedural, definition, list, comparison, summary, troubleshooting, other>
KEYWORDS: <comma-separated important terms>
ENTITIES: <comma-separated names, products, technologies, identifiers, or concepts>
RETRIEVAL_QUERY: <one concise query preserving the user's exact intent>
{scope_rule}
Do not invent terms that are not supported by the question.

User question:
{question}
"""
    fallback = {
        "intent": "other",
        "keywords": [],
        "entities": [],
        "retrieval_query": question.strip(),
    }
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        result = dict(fallback)
        for raw in response["message"]["content"].splitlines():
            line = raw.strip()
            upper = line.upper()
            if upper.startswith("INTENT:"):
                value = line.split(":", 1)[1].strip().lower()
                allowed = {"factual", "procedural", "definition", "list", "comparison", "summary", "troubleshooting", "other"}
                if value in allowed:
                    result["intent"] = value
            elif upper.startswith("KEYWORDS:"):
                result["keywords"] = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
            elif upper.startswith("ENTITIES:"):
                result["entities"] = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
            elif upper.startswith("RETRIEVAL_QUERY:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    result["retrieval_query"] = value
        return result
    except Exception:
        return fallback

def generate_search_queries(question, strict_scope=False, max_queries=3):
    """Generate a small set of retrieval-oriented rewrites for multi-query RAG.

    The rewrites preserve the user's intent and do not answer the question.
    If generation fails, the original question is returned as a safe fallback.
    """
    max_queries = max(1, min(int(max_queries), 4))
    scope_rule = (
        "The search is restricted to the selected document/page, so do not broaden the topic."
        if strict_scope else
        "The search may use all indexed documents."
    )
    prompt = f"""
Create {max_queries} concise search-query rewrites for the user's question below.
These are ONLY for retrieving relevant passages from a document collection.
Do not answer the question. Do not add facts that are not present in the question.
Preserve important names, technical terms, numbers, and code identifiers.
Use different wording when useful: one direct rewrite, one keyword-focused query,
and one concept-focused query.
{scope_rule}
Return ONLY one query per line, with no numbering or bullets.

User question:
{question}
"""
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = [
            line.strip(" -•\t")
            for line in response["message"]["content"].splitlines()
            if line.strip()
        ]
        queries = []
        seen = set()
        for line in lines:
            key = line.lower()
            if key and key not in seen:
                seen.add(key)
                queries.append(line)
            if len(queries) >= max_queries:
                break
        if question.lower() not in seen:
            queries.insert(0, question)
        return queries[:max_queries]
    except Exception:
        return [question]

def chat(question, context, history=None, strict_scope=False):
    history = history or []

    # In strict document/page scope, previous conversation can leak facts
    # from an earlier question that was asked with a different scope.
    # Disable it completely so the answer is grounded only in current context.
    if strict_scope:
        history_text = "(Previous conversation disabled in strict scope mode.)"
    else:
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in history[-8:]
        )


    prompt = f"""
You are an AI document assistant.

Use ONLY the retrieved document context to answer.
Do not use outside knowledge.
Do not invent facts.

If the answer is not supported by the context, say exactly:
"I could not find the answer in the documents."

Previous conversation:
----------------------
{history_text}
----------------------

IMPORTANT GROUNDING RULES:
- Answer ONLY from the Retrieved context shown below.
- Every factual claim must be supported by the retrieved context.
- Cite supporting evidence using the source markers exactly as provided, such as [Source 1] or [Source 2].
- Do not invent, infer unsupported details, or use outside knowledge.
- If the requested information is not present in the retrieved context, say exactly:
  "I could not find the answer in the documents."
- If only part of the question is supported, answer only that supported part and clearly say what is not available.

IMPORTANT SCOPE RULE:
- In strict scope mode, use ONLY the selected document/page context.
- Never use facts from previous conversation or other documents.

Retrieved context:
----------------------
{context}
----------------------

Current question:
----------------------
{question}
----------------------

Answer clearly and concisely. Put citations immediately after the relevant sentence.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"]


def summarize(filename, chunks):
    text = "\n\n".join(
        c["text"] for c in chunks if c["filename"] == filename
    )

    # Prevent accidentally sending an enormous PDF to the local model.
    text = text[:14000]

    prompt = f"""
Summarize the following document using ONLY its content.

Document: {filename}

Content:
----------------------
{text}
----------------------

Use:
## Main Topic
## Key Points
## Important Details
## Conclusion

Do not use outside knowledge or invent information.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"]


def compare(document_a, document_b, chunks):
    text_a = "\n\n".join(
        c["text"] for c in chunks if c["filename"] == document_a
    )[:10000]

    text_b = "\n\n".join(
        c["text"] for c in chunks if c["filename"] == document_b
    )[:10000]

    prompt = f"""
Compare these documents using ONLY their content.

DOCUMENT A: {document_a}
----------------------
{text_a}
----------------------

DOCUMENT B: {document_b}
----------------------
{text_b}
----------------------

Use:
## Similarities
## Differences
## Key Takeaway

Clearly distinguish information belonging to each document.
Do not use outside knowledge or invent information.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"]
