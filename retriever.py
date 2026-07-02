"""
retriever.py
Hybrid retrieval over the SHL catalog: BM25 (keyword) + embeddings (semantic).
"""

from typing import List, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from catalog import load_catalog

# Model choice — MiniLM is fast (~80MB), good quality for short texts
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for BM25."""
    return text.lower().replace("/", " ").replace("-", " ").split()


class Retriever:
    """Hybrid retriever: BM25 keyword + sentence embedding similarity."""

    def __init__(self):
        print("[Retriever] Loading catalog...")
        self.items: List[Dict[str, Any]] = load_catalog()
        self.n = len(self.items)
        print(f"[Retriever] {self.n} items loaded.")

        # ---- BM25 ----
        print("[Retriever] Building BM25 index...")
        tokenized_corpus = [_tokenize(item["search_text"]) for item in self.items]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # ---- Embeddings ----
        print(f"[Retriever] Loading embedding model: {EMBED_MODEL_NAME}")
        self.model = SentenceTransformer(EMBED_MODEL_NAME)
        print("[Retriever] Encoding catalog...")
        # Use a shorter, focused text for embeddings (name + description)
        embed_texts = [
            f"{item['name']}. {item['description']}" for item in self.items
        ]
        self.embeddings = self.model.encode(
            embed_texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )  # shape: (n, dim)
        print(f"[Retriever] Embeddings shape: {self.embeddings.shape}")
        print("[Retriever] Ready.")

    def search(
        self,
        query: str,
        k: int = 15,
        bm25_weight: float = 0.4,
        emb_weight: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Hybrid search. Returns top-k catalog items with scores."""
        if not query.strip():
            return []

        # ---- BM25 scores ----
        bm25_scores = np.array(self.bm25.get_scores(_tokenize(query)))
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / bm25_scores.max()  # normalize 0-1

        # ---- Embedding scores ----
        q_emb = self.model.encode([query], normalize_embeddings=True)[0]
        emb_scores = self.embeddings @ q_emb  # cosine sim (both normalized)

        # ---- Combined ----
        combined = bm25_weight * bm25_scores + emb_weight * emb_scores

        # Top-k indices
        top_idx = np.argsort(-combined)[:k]

        results = []
        for i in top_idx:
            item = self.items[int(i)].copy()
            item["_score"] = float(combined[i])
            item["_bm25"] = float(bm25_scores[i])
            item["_emb"] = float(emb_scores[i])
            results.append(item)
        return results

    def search_multi(self, queries: List[str], k: int = 15) -> List[Dict[str, Any]]:
        """Search using multiple query strings, merge by max score."""
        if not queries:
            return []
        all_scores = np.zeros(self.n)
        for q in queries:
            if not q.strip():
                continue
            bm25 = np.array(self.bm25.get_scores(_tokenize(q)))
            if bm25.max() > 0:
                bm25 = bm25 / bm25.max()
            q_emb = self.model.encode([q], normalize_embeddings=True)[0]
            emb = self.embeddings @ q_emb
            combined = 0.4 * bm25 + 0.6 * emb
            all_scores = np.maximum(all_scores, combined)

        top_idx = np.argsort(-all_scores)[:k]
        results = []
        for i in top_idx:
            item = self.items[int(i)].copy()
            item["_score"] = float(all_scores[i])
            results.append(item)
        return results


# ---- Standalone test ----
if __name__ == "__main__":
    r = Retriever()

    print("\n" + "=" * 60)
    print("TEST 1: Java developer")
    print("=" * 60)
    for hit in r.search("hiring a Java developer for backend microservices", k=5):
        print(f"  [{hit['_score']:.3f}] {hit['name']}  ({hit['test_type']})")

    print("\n" + "=" * 60)
    print("TEST 2: senior leadership CXO personality")
    print("=" * 60)
    for hit in r.search("senior leadership CXO personality assessment", k=5):
        print(f"  [{hit['_score']:.3f}] {hit['name']}  ({hit['test_type']})")

    print("\n" + "=" * 60)
    print("TEST 3: contact centre spoken english screening")
    print("=" * 60)
    for hit in r.search("contact centre agent spoken english call screening", k=5):
        print(f"  [{hit['_score']:.3f}] {hit['name']}  ({hit['test_type']})")

    print("\n" + "=" * 60)
    print("TEST 4: safety dependability manufacturing")
    print("=" * 60)
    for hit in r.search("safety dependability plant operator manufacturing", k=5):
        print(f"  [{hit['_score']:.3f}] {hit['name']}  ({hit['test_type']})")