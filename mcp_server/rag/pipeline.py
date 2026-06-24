"""
RAG Pipeline — Clinical Knowledge Retrieval.

Zero-dependency retrieval using TF-IDF cosine similarity.
Falls back to scikit-learn TfidfVectorizer when available (better recall).

Documents are loaded from knowledge/ directory at module import.
Each document is chunked into ~200-word paragraphs with overlapping context.
Retrieval returns top-k chunks with source citation and confidence score.
"""

from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeChunk:
    chunk_id:    str
    doc_id:      str
    source_file: str
    title:       str
    section:     str
    content:     str
    word_count:  int
    char_offset: int          # byte offset in source document


@dataclass
class RetrievedChunk:
    chunk:      KnowledgeChunk
    score:      float          # cosine similarity 0..1
    confidence: str            # "high" / "medium" / "low"
    snippet:    str            # highlighted excerpt ≤300 chars


@dataclass
class RAGResult:
    query:          str
    retrieved:      List[RetrievedChunk]
    retrieval_ms:   float
    total_chunks:   int


# ---------------------------------------------------------------------------
# Document loader & chunker
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

_CHUNK_WORDS    = 200    # target words per chunk
_CHUNK_OVERLAP  = 40     # overlap words between adjacent chunks


def _split_into_chunks(text: str, doc_id: str, source_file: str,
                       title: str) -> List[KnowledgeChunk]:
    """Split document into overlapping word-window chunks."""
    words  = text.split()
    chunks: List[KnowledgeChunk] = []
    start  = 0
    idx    = 0

    # Detect section headings (## heading)
    section_map: Dict[int, str] = {}
    current_section = "Introduction"
    char_pos = 0
    word_pos = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("# "):
            heading = stripped.lstrip("#").strip()
            word_pos_in_line = len(section_map)
            section_map[char_pos] = heading
        char_pos += len(line) + 1

    while start < len(words):
        end   = min(start + _CHUNK_WORDS, len(words))
        chunk = words[start:end]
        content = " ".join(chunk)

        # Find the closest section heading before this chunk
        chunk_char = len(" ".join(words[:start]))
        sec = "General"
        for pos, heading in sorted(section_map.items()):
            if pos <= chunk_char:
                sec = heading

        chunks.append(KnowledgeChunk(
            chunk_id    = f"{doc_id}-chunk-{idx:03d}",
            doc_id      = doc_id,
            source_file = source_file,
            title       = title,
            section     = sec,
            content     = content,
            word_count  = len(chunk),
            char_offset = chunk_char,
        ))
        idx  += 1
        start = end - _CHUNK_OVERLAP if end < len(words) else end

    return chunks


def _extract_title(text: str) -> str:
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "Untitled Document"


def load_knowledge_base() -> List[KnowledgeChunk]:
    """Load all .md files from knowledge/ directory into chunks."""
    if not KNOWLEDGE_DIR.exists():
        return []

    all_chunks: List[KnowledgeChunk] = []
    for md_file in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text  = md_file.read_text(encoding="utf-8")
        title = _extract_title(text)
        doc_id = md_file.stem
        chunks = _split_into_chunks(text, doc_id, md_file.name, title)
        all_chunks.extend(chunks)

    return all_chunks


# ---------------------------------------------------------------------------
# TF-IDF vectoriser (pure Python fallback + sklearn preferred)
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> List[str]:
    """Lower-case, remove punctuation, split on whitespace."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in text.split() if len(t) > 1]


def _idf(doc_count: int, df: int) -> float:
    return math.log((doc_count + 1) / (df + 1)) + 1.0


class PurePythonTFIDF:
    """Minimal TF-IDF implementation — no external dependencies."""

    def __init__(self):
        self._vocab:  Dict[str, int]   = {}
        self._idf:    Dict[int, float]  = {}
        self._matrix: List[Dict[int, float]] = []   # sparse: {term_idx: tfidf}
        self._doc_count = 0

    def fit(self, documents: List[str]):
        self._doc_count = len(documents)
        df: Dict[str, int] = {}
        tokenised = [_tokenise(d) for d in documents]

        for tokens in tokenised:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

        self._vocab = {t: i for i, t in enumerate(sorted(df.keys()))}
        self._idf   = {
            i: _idf(self._doc_count, df[t])
            for t, i in self._vocab.items()
        }

        self._matrix = []
        for tokens in tokenised:
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            total = max(len(tokens), 1)
            vec: Dict[int, float] = {
                self._vocab[t]: (cnt / total) * self._idf[self._vocab[t]]
                for t, cnt in tf.items() if t in self._vocab
            }
            self._matrix.append(vec)

    def transform_query(self, query: str) -> Dict[int, float]:
        tokens = _tokenise(query)
        tf: Dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = max(len(tokens), 1)
        return {
            self._vocab[t]: (cnt / total) * self._idf.get(self._vocab[t], 1.0)
            for t, cnt in tf.items() if t in self._vocab
        }

    def cosine_scores(self, query_vec: Dict[int, float]) -> List[float]:
        scores = []
        q_norm = math.sqrt(sum(v * v for v in query_vec.values())) or 1e-9
        for doc_vec in self._matrix:
            dot = sum(query_vec.get(k, 0) * v for k, v in doc_vec.items())
            d_norm = math.sqrt(sum(v * v for v in doc_vec.values())) or 1e-9
            scores.append(dot / (q_norm * d_norm))
        return scores


# ---------------------------------------------------------------------------
# RAG Pipeline
# ---------------------------------------------------------------------------

class ClinicalRAGPipeline:
    """
    Retrieve relevant clinical knowledge chunks for a natural-language query.

    Uses scikit-learn TF-IDF if available; falls back to pure-Python implementation.
    Chunked documents are indexed at construction time (~50ms for 4 docs).
    """

    def __init__(self):
        self._chunks: List[KnowledgeChunk] = load_knowledge_base()
        self._corpus  = [c.content for c in self._chunks]
        self._backend = "none"
        self._sklearn_vectoriser = None
        self._sklearn_matrix     = None
        self._pure_tfidf         = None

        if not self._corpus:
            return   # empty knowledge base

        # Prefer sklearn for better BM25-like weighting
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            vectoriser = TfidfVectorizer(
                lowercase   = True,
                stop_words  = "english",
                ngram_range = (1, 2),
                max_df      = 0.85,
                sublinear_tf = True,
            )
            matrix = vectoriser.fit_transform(self._corpus)
            self._sklearn_vectoriser = vectoriser
            self._sklearn_matrix     = matrix
            self._cosine_fn = cosine_similarity
            self._np = np
            self._backend = "sklearn"
        except ImportError:
            pure = PurePythonTFIDF()
            pure.fit(self._corpus)
            self._pure_tfidf = pure
            self._backend = "pure_python"

    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 4,
                 min_score: float = 0.05) -> RAGResult:
        """
        Retrieve top-k relevant chunks for query.
        Returns RAGResult with scored, cited chunks.
        """
        t0 = time.time()

        if not self._corpus:
            return RAGResult(query=query, retrieved=[],
                             retrieval_ms=0, total_chunks=0)

        # Score all chunks
        if self._backend == "sklearn":
            q_vec  = self._sklearn_vectoriser.transform([query])
            scores = self._cosine_fn(q_vec, self._sklearn_matrix).flatten().tolist()
        elif self._backend == "pure_python":
            q_vec  = self._pure_tfidf.transform_query(query)
            scores = self._pure_tfidf.cosine_scores(q_vec)
        else:
            return RAGResult(query=query, retrieved=[],
                             retrieval_ms=0, total_chunks=0)

        # Rank and filter
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        retrieved: List[RetrievedChunk] = []

        seen_docs: Dict[str, int] = {}   # doc_id → count, limit 2 per doc
        for idx, score in ranked:
            if score < min_score:
                break
            if len(retrieved) >= top_k:
                break
            chunk = self._chunks[idx]
            # Limit chunks per document to avoid one doc dominating
            if seen_docs.get(chunk.doc_id, 0) >= 2:
                continue
            seen_docs[chunk.doc_id] = seen_docs.get(chunk.doc_id, 0) + 1

            confidence = (
                "high"   if score >= 0.35 else
                "medium" if score >= 0.15 else
                "low"
            )
            snippet = self._make_snippet(chunk.content, query)
            retrieved.append(RetrievedChunk(
                chunk      = chunk,
                score      = round(score, 4),
                confidence = confidence,
                snippet    = snippet,
            ))

        retrieval_ms = (time.time() - t0) * 1000
        return RAGResult(
            query        = query,
            retrieved    = retrieved,
            retrieval_ms = round(retrieval_ms, 2),
            total_chunks = len(self._corpus),
        )

    # ------------------------------------------------------------------
    def retrieve_for_display(self, query: str, top_k: int = 3) -> List[dict]:
        """Convenience method returning list of dicts for UI rendering."""
        result = self.retrieve(query, top_k=top_k)
        return [
            {
                "source":     r.chunk.source_file,
                "title":      r.chunk.title,
                "section":    r.chunk.section,
                "snippet":    r.snippet,
                "score":      r.score,
                "confidence": r.confidence,
                "chunk_id":   r.chunk.chunk_id,
            }
            for r in result.retrieved
        ]

    # ------------------------------------------------------------------
    @staticmethod
    def _make_snippet(content: str, query: str, max_len: int = 300) -> str:
        """Extract the most relevant sentence from the chunk for display."""
        query_words = set(_tokenise(query))
        sentences   = re.split(r"(?<=[.!?])\s+", content)

        best_sent  = content[:max_len]
        best_score = -1
        for sent in sentences:
            sent_words = set(_tokenise(sent))
            overlap    = len(query_words & sent_words)
            if overlap > best_score:
                best_score = overlap
                best_sent  = sent

        if len(best_sent) > max_len:
            best_sent = best_sent[:max_len].rsplit(" ", 1)[0] + "…"
        return best_sent

    # ------------------------------------------------------------------
    @property
    def backend(self) -> str:
        return self._backend

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def list_documents(self) -> List[dict]:
        seen = {}
        for c in self._chunks:
            if c.doc_id not in seen:
                seen[c.doc_id] = {
                    "doc_id": c.doc_id,
                    "title":  c.title,
                    "file":   c.source_file,
                    "chunks": 0,
                }
            seen[c.doc_id]["chunks"] += 1
        return list(seen.values())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

import threading as _threading

_pipeline: Optional[ClinicalRAGPipeline] = None
_pipeline_lock = _threading.Lock()


def get_rag_pipeline() -> ClinicalRAGPipeline:
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                _pipeline = ClinicalRAGPipeline()
    return _pipeline
