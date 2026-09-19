from pathlib import Path
import hashlib
import json
import numpy as np
import faiss

DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
DEFAULT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _dir(storage_dir=None):
    path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _paths(storage_dir=None):
    d = _dir(storage_dir)
    return d / "documents.json", d / "embeddings.npy", d / "faiss.index"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_documents(storage_dir=None):
    docs_file, _, _ = _paths(storage_dir)
    if not docs_file.exists():
        return {}
    try:
        return json.loads(docs_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_documents(documents, storage_dir=None):
    docs_file, _, _ = _paths(storage_dir)
    docs_file.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")


def load_vector_store(storage_dir=None):
    _, embeddings_file, index_file = _paths(storage_dir)
    if not (index_file.exists() and embeddings_file.exists()):
        return None, None
    try:
        index = faiss.read_index(str(index_file))
        embeddings = np.load(embeddings_file)
        return index, embeddings
    except Exception:
        return None, None


def save_vector_store(embeddings, storage_dir=None):
    _, embeddings_file, index_file = _paths(storage_dir)
    embeddings = np.asarray(embeddings, dtype="float32")
    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        raise ValueError("No embeddings available to save.")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(index_file))
    np.save(embeddings_file, embeddings)
    return index


def rebuild_vector_store(all_chunks, embedding_model, storage_dir=None):
    texts = [c["text"] for c in all_chunks]
    if not texts:
        raise ValueError("No chunks available to index.")
    embeddings = embedding_model.encode(
        texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
    )
    index = save_vector_store(embeddings, storage_dir)
    return index, embeddings


def add_chunks_to_vector_store(new_chunks, embedding_model, storage_dir=None):
    texts = [c["text"] for c in new_chunks]
    if not texts:
        raise ValueError("No new chunks available to index.")
    new_embeddings = embedding_model.encode(
        texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
    )
    new_embeddings = np.asarray(new_embeddings, dtype="float32")
    old_index, old_embeddings = load_vector_store(storage_dir)
    if old_index is None or old_embeddings is None:
        index = faiss.IndexFlatIP(new_embeddings.shape[1])
        index.add(new_embeddings)
        all_embeddings = new_embeddings
    else:
        old_embeddings = np.asarray(old_embeddings, dtype="float32")
        if old_embeddings.ndim != 2 or old_embeddings.shape[1] != new_embeddings.shape[1]:
            raise ValueError("Embedding dimension mismatch. Rebuild the user index.")
        index = old_index
        index.add(new_embeddings)
        all_embeddings = np.vstack([old_embeddings, new_embeddings])
    _, embeddings_file, index_file = _paths(storage_dir)
    faiss.write_index(index, str(index_file))
    np.save(embeddings_file, all_embeddings)
    return index, all_embeddings, len(new_chunks)


def rebuild_from_documents(documents, embedding_model, storage_dir=None):
    all_chunks = []
    for meta in documents.values():
        all_chunks.extend(meta.get("chunks", []))
    return rebuild_vector_store(all_chunks, embedding_model, storage_dir)


def clear_storage(storage_dir=None):
    docs_file, embeddings_file, index_file = _paths(storage_dir)
    for path in [docs_file, embeddings_file, index_file]:
        if path.exists():
            path.unlink()
