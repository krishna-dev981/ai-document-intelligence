import re
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

RERANKER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def tokenize(text):
    # More robust tokenization for punctuation, code-like terms, and PDFs.
    return re.findall(r"[a-zA-Z0-9_+#.:-]+", text.lower())


def build_faiss(embeddings):
    embeddings = np.asarray(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index


def build_bm25(chunks):
    return BM25Okapi([tokenize(c["text"]) for c in chunks])


def semantic_search(index, model, question, k):
    query = model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    k = min(k, index.ntotal)
    if k == 0:
        return np.array([]), np.array([], dtype=int)

    scores, indices = index.search(
        np.asarray(query, dtype="float32"), k
    )
    return scores[0], indices[0]


def semantic_search_filtered(index, model, question, chunks, k, filename=None, page=None):
    """Semantic search restricted to a document and/or page.

    FAISS IndexFlatIP does not need to be rebuilt for filtering. We reconstruct
    the stored normalized vectors, score only matching chunk IDs, and return
    the original global chunk IDs so BM25/hybrid/reranking stay aligned.
    """
    allowed = [
        i for i, chunk in enumerate(chunks)
        if (filename is None or chunk.get("filename") == filename)
        and (page is None or int(chunk.get("page", -1)) == int(page))
    ]

    if not allowed:
        return np.array([]), np.array([], dtype=int)

    query = model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].astype("float32")

    vectors = np.asarray(index.reconstruct_n(0, index.ntotal), dtype="float32")
    candidate_vectors = vectors[allowed]
    scores = candidate_vectors @ query

    order = np.argsort(scores)[::-1][: min(k, len(allowed))]
    return scores[order], np.asarray([allowed[i] for i in order], dtype=int)


def keyword_search(bm25, question, k):
    scores = bm25.get_scores(tokenize(question))
    k = min(k, len(scores))
    indices = np.argsort(scores)[::-1][:k]
    return scores[indices], indices


def keyword_search_filtered(bm25, question, chunks, k, filename=None, page=None):
    allowed = [
        i for i, chunk in enumerate(chunks)
        if (filename is None or chunk.get("filename") == filename)
        and (page is None or int(chunk.get("page", -1)) == int(page))
    ]

    if not allowed:
        return np.array([]), np.array([], dtype=int)

    scores = bm25.get_scores(tokenize(question))
    allowed_scores = np.asarray([scores[i] for i in allowed])
    order = np.argsort(allowed_scores)[::-1][: min(k, len(allowed))]

    return allowed_scores[order], np.asarray([allowed[i] for i in order], dtype=int)


def reciprocal_rank_fusion(faiss_indices, bm25_indices, k=60):
    """Fuse semantic and keyword rankings using Reciprocal Rank Fusion.

    RRF rewards chunks that rank well in either retriever and gives an
    additional advantage to chunks that appear strongly in both lists.
    """
    scores = {}

    for rank, idx in enumerate(faiss_indices, start=1):
        idx = int(idx)
        if idx >= 0:
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)

    for rank, idx in enumerate(bm25_indices, start=1):
        idx = int(idx)
        if idx >= 0:
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)

    return [idx for idx, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


def hybrid_ids(faiss_indices, bm25_indices):
    # Backward-compatible alias. V8.4 uses RRF ordering instead of arbitrary
    # sorted union ordering.
    return reciprocal_rank_fusion(faiss_indices, bm25_indices)


def load_reranker():
    return CrossEncoder(RERANKER_NAME)


def rerank(reranker, question, chunks, top_k=5):
    if not chunks:
        return []

    pairs = [[question, c["text"]] for c in chunks]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(chunks, scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )

    return ranked[:top_k]


def expand_context_chunks(ranked, chunks, window=1, max_chunks=10):
    """Expand high-ranked chunks with nearby chunks from the same page.

    Retrieval selects the most relevant chunk, but answers often need the
    sentence or code block immediately before/after it. This function adds
    neighboring chunks without changing retrieval scores.
    """
    if not ranked or not chunks:
        return []

    selected = []
    seen = set()

    for chunk, _score in ranked:
        try:
            center = chunks.index(chunk)
        except ValueError:
            continue

        filename = chunk.get("filename")
        page = chunk.get("page")

        for idx in range(max(0, center - window), min(len(chunks), center + window + 1)):
            neighbor = chunks[idx]
            if neighbor.get("filename") != filename or neighbor.get("page") != page:
                continue
            if idx not in seen:
                seen.add(idx)
                selected.append((idx, neighbor))
            if len(selected) >= max_chunks:
                break
        if len(selected) >= max_chunks:
            break

    selected.sort(key=lambda item: item[0])
    return [chunk for _, chunk in selected]
