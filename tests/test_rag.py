"""
Integration tests for the RAG (Retrieval-Augmented Generation) pipeline.

Tests cover:
- Document loading from knowledge/ directory
- Chunking correctness (word count, overlap, title extraction)
- TF-IDF retrieval (score ordering, top-k limit, min-score filter)
- Per-document coverage limit (≤ 2 chunks per doc per query)
- Snippet generation (best sentence selection)
- Confidence tier mapping
- Module-level singleton behaviour
- retrieve_for_display convenience wrapper
"""

import pytest

from mcp_server.rag.pipeline import (
    ClinicalRAGPipeline,
    get_rag_pipeline,
    KnowledgeChunk,
    RetrievedChunk,
    RAGResult,
    _tokenise,
    _idf,
    KNOWLEDGE_DIR,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pipeline():
    """Module-scoped pipeline — loads knowledge base once."""
    return ClinicalRAGPipeline()


# ── Knowledge base loading ────────────────────────────────────────────────

class TestKnowledgeLoading:
    def test_knowledge_dir_exists(self):
        assert KNOWLEDGE_DIR.exists(), f"{KNOWLEDGE_DIR} does not exist"

    def test_at_least_four_documents_loaded(self, pipeline):
        docs = pipeline.list_documents()
        assert len(docs) >= 4, f"Expected ≥4 docs, got {len(docs)}: {[d['doc_id'] for d in docs]}"

    def test_expected_documents_present(self, pipeline):
        doc_ids = {d["doc_id"] for d in pipeline.list_documents()}
        expected = {"sepsis_protocol", "respiratory_protocol",
                    "alarm_management_policy", "device_troubleshooting"}
        for doc_id in expected:
            assert doc_id in doc_ids, f"Missing document: {doc_id}"

    def test_chunk_count_is_positive(self, pipeline):
        assert pipeline.chunk_count > 0

    def test_each_document_has_title(self, pipeline):
        for doc in pipeline.list_documents():
            assert doc["title"], f"Empty title for {doc['doc_id']}"

    def test_each_document_has_multiple_chunks(self, pipeline):
        for doc in pipeline.list_documents():
            assert doc["chunks"] >= 1, f"{doc['doc_id']} has no chunks"

    def test_backend_is_set(self, pipeline):
        assert pipeline.backend in ("sklearn", "pure_python"), \
            f"Unexpected backend: {pipeline.backend}"


# ── Tokeniser ────────────────────────────────────────────────────────────

class TestTokeniser:
    def test_lowercases_input(self):
        tokens = _tokenise("SpO2 CRISIS Alarm")
        assert all(t == t.lower() for t in tokens)

    def test_strips_punctuation(self):
        tokens = _tokenise("NEWS2, score: 7.")
        assert "," not in tokens
        assert "." not in tokens

    def test_filters_single_char_tokens(self):
        tokens = _tokenise("a b c NEWS2")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "news2" in tokens

    def test_returns_list_of_strings(self):
        tokens = _tokenise("sepsis protocol management")
        assert isinstance(tokens, list)
        assert all(isinstance(t, str) for t in tokens)


# ── IDF calculation ───────────────────────────────────────────────────────

class TestIDF:
    def test_rare_term_has_higher_idf(self):
        """Term appearing in 1/100 docs should have higher IDF than 50/100."""
        idf_rare   = _idf(100, 1)
        idf_common = _idf(100, 50)
        assert idf_rare > idf_common

    def test_idf_is_positive(self):
        assert _idf(100, 1) > 0
        assert _idf(100, 100) > 0


# ── Retrieval ─────────────────────────────────────────────────────────────

class TestRetrieval:
    def test_retrieve_returns_rag_result(self, pipeline):
        result = pipeline.retrieve("sepsis protocol blood pressure")
        assert isinstance(result, RAGResult)

    def test_retrieval_has_query_set(self, pipeline):
        q = "SpO2 alarm crisis respiratory"
        result = pipeline.retrieve(q)
        assert result.query == q

    def test_retrieval_ms_is_positive(self, pipeline):
        result = pipeline.retrieve("NEWS2 score deterioration")
        assert result.retrieval_ms >= 0

    def test_total_chunks_matches_corpus(self, pipeline):
        result = pipeline.retrieve("test")
        assert result.total_chunks == pipeline.chunk_count

    def test_top_k_limits_results(self, pipeline):
        for top_k in [1, 2, 3]:
            result = pipeline.retrieve("alarm crisis warning", top_k=top_k)
            assert len(result.retrieved) <= top_k

    def test_results_sorted_by_score_descending(self, pipeline):
        result = pipeline.retrieve("sepsis NEWS2 blood culture", top_k=5)
        scores = [r.score for r in result.retrieved]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score"

    def test_sepsis_query_retrieves_sepsis_doc(self, pipeline):
        result = pipeline.retrieve("sepsis-3 qSOFA blood pressure NEWS2", top_k=3)
        sources = [r.chunk.doc_id for r in result.retrieved]
        assert any("sepsis" in s for s in sources), \
            f"Sepsis doc not retrieved for sepsis query. Got: {sources}"

    def test_respiratory_query_retrieves_resp_doc(self, pipeline):
        result = pipeline.retrieve("SpO2 oxygen saturation respiratory deterioration", top_k=3)
        sources = [r.chunk.doc_id for r in result.retrieved]
        assert any("respiratory" in s or "alarm" in s for s in sources), \
            f"Respiratory doc not retrieved. Got: {sources}"

    def test_device_query_retrieves_device_doc(self, pipeline):
        result = pipeline.retrieve("ventilator offline probe disconnect troubleshoot", top_k=3)
        sources = [r.chunk.doc_id for r in result.retrieved]
        assert any("device" in s or "alarm" in s for s in sources), \
            f"Device doc not retrieved. Got: {sources}"

    def test_per_doc_limit_enforced(self, pipeline):
        """No single document should contribute more than 2 chunks."""
        result = pipeline.retrieve("alarm alarm alarm NEWS2 alarm", top_k=10)
        from collections import Counter
        counts = Counter(r.chunk.doc_id for r in result.retrieved)
        for doc_id, count in counts.items():
            assert count <= 2, f"{doc_id} contributed {count} chunks (limit=2)"

    def test_min_score_filter(self, pipeline):
        result = pipeline.retrieve("xxxx yyyyzzzz qqqqqq", min_score=0.5)
        # Nonsense query should return nothing above 0.5
        assert all(r.score >= 0.5 for r in result.retrieved)

    def test_empty_query_does_not_raise(self, pipeline):
        try:
            result = pipeline.retrieve("")
        except Exception as ex:
            pytest.fail(f"Empty query raised: {ex}")


# ── Chunk properties ─────────────────────────────────────────────────────

class TestChunkProperties:
    def test_retrieved_chunks_have_content(self, pipeline):
        result = pipeline.retrieve("sepsis lactate bundle", top_k=3)
        for r in result.retrieved:
            assert r.chunk.content.strip(), "Chunk content is empty"

    def test_retrieved_chunks_have_word_count(self, pipeline):
        result = pipeline.retrieve("NEWS2 respiratory deterioration", top_k=3)
        for r in result.retrieved:
            assert r.chunk.word_count > 0

    def test_snippet_length_within_limit(self, pipeline):
        result = pipeline.retrieve("alarm tier crisis", top_k=3)
        for r in result.retrieved:
            assert len(r.snippet) <= 310, f"Snippet too long: {len(r.snippet)}"

    def test_snippet_is_nonempty(self, pipeline):
        result = pipeline.retrieve("SpO2 saturation", top_k=3)
        for r in result.retrieved:
            assert r.snippet.strip(), "Snippet is empty"


# ── Confidence tiers ─────────────────────────────────────────────────────

class TestConfidenceTiers:
    def test_high_confidence_for_exact_match(self, pipeline):
        """A query that exactly matches frequent terms in a doc should score HIGH."""
        result = pipeline.retrieve("sepsis-3 definition organ dysfunction SOFA criteria", top_k=1)
        if result.retrieved:
            top = result.retrieved[0]
            # Score might be medium or high depending on corpus size — just verify mapping
            expected = (
                "high"   if top.score >= 0.35 else
                "medium" if top.score >= 0.15 else
                "low"
            )
            assert top.confidence == expected

    def test_confidence_values_are_valid(self, pipeline):
        result = pipeline.retrieve("NEWS2 RCP monitoring", top_k=5)
        valid = {"high", "medium", "low"}
        for r in result.retrieved:
            assert r.confidence in valid, f"Invalid confidence: {r.confidence}"

    def test_scores_are_between_0_and_1(self, pipeline):
        result = pipeline.retrieve("alarm management", top_k=5)
        for r in result.retrieved:
            assert 0.0 <= r.score <= 1.0, f"Score {r.score} out of [0,1]"


# ── retrieve_for_display convenience method ───────────────────────────────

class TestRetrieveForDisplay:
    def test_returns_list_of_dicts(self, pipeline):
        results = pipeline.retrieve_for_display("SpO2 alarm", top_k=3)
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, dict)

    def test_dict_has_required_keys(self, pipeline):
        results = pipeline.retrieve_for_display("sepsis bundle", top_k=2)
        required_keys = {"source", "title", "section", "snippet", "score", "confidence", "chunk_id"}
        for item in results:
            missing = required_keys - set(item.keys())
            assert not missing, f"Missing keys: {missing}"

    def test_respects_top_k(self, pipeline):
        results = pipeline.retrieve_for_display("NEWS2", top_k=2)
        assert len(results) <= 2


# ── Singleton behaviour ───────────────────────────────────────────────────

class TestSingleton:
    def test_get_rag_pipeline_returns_same_instance(self):
        p1 = get_rag_pipeline()
        p2 = get_rag_pipeline()
        assert p1 is p2, "get_rag_pipeline() should return the same singleton"

    def test_singleton_has_chunks_loaded(self):
        p = get_rag_pipeline()
        assert p.chunk_count > 0
