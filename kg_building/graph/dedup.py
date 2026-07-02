from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def find_duplicate(new_name: str, existing: list[dict], threshold: float = 0.88) -> dict | None:
    """Returns the best-matching existing entity dict if cosine similarity >= threshold, else None."""
    if not existing:
        return None
    try:
        import numpy as np
        model = _get_model()
        names = [e["name"] for e in existing]
        emb_existing = model.encode(names, normalize_embeddings=True)
        emb_new = model.encode([new_name], normalize_embeddings=True)[0]
        sims = emb_existing @ emb_new
        best_idx = int(sims.argmax())
        if sims[best_idx] >= threshold:
            log.debug("Dedup match: '%s' ~ '%s' (sim=%.3f)", new_name, names[best_idx], sims[best_idx])
            return existing[best_idx]
    except Exception as exc:
        log.warning("Embedding dedup unavailable (%s) — falling back to exact/substring match", exc)
        low = new_name.strip().lower()
        for e in existing:
            if e["name"].strip().lower() == low:
                return e
    return None


def find_similar_entities(query: str, existing: list[dict], threshold: float = 0.75) -> list[tuple[float, dict]]:
    """Returns all existing entity dicts with cosine similarity >= threshold to `query`,
    sorted descending, as (similarity, entity) pairs. One-vs-many — used by search_entities
    to surface near-misses that plain lexical matching wouldn't catch."""
    if not existing or not query.strip():
        return []
    try:
        model = _get_model()
        names = [e["name"] for e in existing]
        emb_existing = model.encode(names, normalize_embeddings=True)
        emb_query = model.encode([query], normalize_embeddings=True)[0]
        sims = emb_existing @ emb_query
        matches = [(float(sims[i]), existing[i]) for i in range(len(existing)) if sims[i] >= threshold]
        matches.sort(key=lambda x: -x[0])
        return matches
    except Exception as exc:
        log.warning("Embedding search unavailable (%s)", exc)
        return []


def find_all_duplicate_pairs(entities: list[dict], threshold: float = 0.75, limit: int = 20) -> list[dict]:
    """Pairwise cosine similarity across every entity name. Returns
    [{"a": id, "a_name": ..., "b": id, "b_name": ..., "similarity": float}],
    sorted descending, capped at `limit`. Used by the critic to surface duplicate
    candidates that fell below the 0.88 auto-merge threshold at creation time."""
    if len(entities) < 2:
        return []
    try:
        import numpy as np
        model = _get_model()
        names = [e["name"] for e in entities]
        emb = model.encode(names, normalize_embeddings=True)
        sim_matrix = emb @ emb.T
        pairs = []
        n = len(entities)
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim >= threshold:
                    pairs.append({
                        "a": entities[i]["id"], "a_name": entities[i]["name"],
                        "b": entities[j]["id"], "b_name": entities[j]["name"],
                        "similarity": round(sim, 3),
                    })
        pairs.sort(key=lambda p: -p["similarity"])
        return pairs[:limit]
    except Exception as exc:
        log.warning("Embedding pairwise dedup unavailable (%s)", exc)
        return []
