import numpy as np


def record(question, latency, faiss_count, bm25_count,
           candidate_count, top_chunks, reranker_scores, context_chunks=None):
    avg_score = (
        float(np.mean(reranker_scores))
        if reranker_scores else 0.0
    )

    return {
        "question": question,
        "latency": float(latency),
        "faiss_count": int(faiss_count),
        "bm25_count": int(bm25_count),
        "candidate_count": int(candidate_count),
        "top_chunks": int(top_chunks),
        "context_chunks": int(context_chunks if context_chunks is not None else top_chunks),
        "avg_reranker_score": avg_score,
    }


def metrics(history):
    if not history:
        return 0, 0.0, 0.0

    return (
        len(history),
        float(np.mean([x["latency"] for x in history])),
        float(np.mean([x["avg_reranker_score"] for x in history])),
    )


def evaluate_retrieval(question, ranked_chunks, expected_keywords=None,
                       expected_document=None, expected_page=None):
    """Evaluate whether retrieved chunks contain expected evidence.

    This is a retrieval-oriented test, not an LLM correctness judge.
    """
    expected_keywords = [k.strip().lower() for k in (expected_keywords or []) if k.strip()]
    hits = []
    for rank, chunk in enumerate(ranked_chunks, start=1):
        text = str(chunk.get("text", "")).lower()
        keyword_hit = bool(expected_keywords) and all(k in text for k in expected_keywords)
        location_hit = (
            (expected_document is None or chunk.get("filename") == expected_document)
            and (expected_page is None or int(chunk.get("page", -1)) == int(expected_page))
        )
        hits.append(keyword_hit and location_hit)

    first_hit = next((i + 1 for i, hit in enumerate(hits) if hit), None)
    return {
        "question": question,
        "hit_at_1": bool(hits[:1] and hits[0]),
        "hit_at_3": any(hits[:3]),
        "hit_at_5": any(hits[:5]),
        "mrr": 1.0 / first_hit if first_hit else 0.0,
        "first_hit_rank": first_hit or "—",
        "retrieved": len(ranked_chunks),
    }


def benchmark_metrics(results):
    if not results:
        return {"tests": 0, "hit1": 0.0, "hit3": 0.0, "hit5": 0.0, "mrr": 0.0}
    return {
        "tests": len(results),
        "hit1": float(np.mean([r["hit_at_1"] for r in results])),
        "hit3": float(np.mean([r["hit_at_3"] for r in results])),
        "hit5": float(np.mean([r["hit_at_5"] for r in results])),
        "mrr": float(np.mean([r["mrr"] for r in results])),
    }
