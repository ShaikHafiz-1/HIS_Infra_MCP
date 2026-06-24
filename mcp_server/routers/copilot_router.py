"""
AI Copilot REST endpoint.

POST /api/v1/copilot/query
{
  "question":       "Why is Bed 12 alarming?",
  "patient_id":     "PT-001",          // optional
  "care_unit_id":   "ICU",             // optional
  "clinician_id":   "CLN-001",
  "clinician_role": "physician"
}

Returns CopilotResponse JSON with answer, tool_traces, rag_sources, audit_id.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/copilot", tags=["AI Copilot"])


class CopilotQuery(BaseModel):
    question:       str
    patient_id:     Optional[str]  = None
    care_unit_id:   Optional[str]  = "ICU"
    alarm_id:       Optional[str]  = None
    clinician_id:   str            = "demo"
    clinician_role: str            = "physician"
    anthropic_api_key: Optional[str] = None   # passed per-session from UI


@router.post("/query")
async def copilot_query(body: CopilotQuery):
    from mcp_server.copilot.workflow import get_copilot

    copilot = get_copilot(
        mcp_server        = None,   # will use mock/simulator
        anthropic_api_key = body.anthropic_api_key,
        force_new         = bool(body.anthropic_api_key),
    )

    context = {
        "patient_id":       body.patient_id,
        "care_unit_id":     body.care_unit_id,
        "alarm_id":         body.alarm_id,
        "elapsed_seconds":  0,
    }
    try:
        from simulator.patient_monitor import get_simulator
        context["elapsed_seconds"] = get_simulator().elapsed_seconds()
    except Exception:
        pass

    try:
        response = await copilot.answer(
            question       = body.question,
            context        = context,
            clinician_id   = body.clinician_id,
            clinician_role = body.clinician_role,
        )
        return {
            "answer":          response.answer,
            "confidence":      response.confidence,
            "confidence_tier": response.confidence_tier,
            "safety_flags":    response.safety_flags,
            "escalation_note": response.escalation_note,
            "audit_id":        response.audit_id,
            "total_ms":        response.total_ms,
            "model_used":      response.model_used,
            "tool_traces": [
                {
                    "tool_name":  t.tool_name,
                    "arguments":  t.arguments,
                    "success":    t.success,
                    "latency_ms": t.latency_ms,
                    "error":      t.error,
                }
                for t in response.tool_traces
            ],
            "rag_sources": [
                {
                    "title":      r.title,
                    "section":    r.section,
                    "snippet":    r.snippet,
                    "score":      r.score,
                    "confidence": r.confidence,
                    "source":     r.source_file,
                }
                for r in response.rag_sources
            ],
        }
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/rag/documents")
async def list_rag_documents():
    """List all documents in the RAG knowledge base."""
    from mcp_server.rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    return {
        "backend":     pipeline.backend,
        "chunk_count": pipeline.chunk_count,
        "documents":   pipeline.list_documents(),
    }


@router.post("/rag/search")
async def rag_search(body: dict):
    """Raw RAG search for a query (debugging / admin)."""
    query  = body.get("query", "")
    top_k  = body.get("top_k", 3)
    from mcp_server.rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    result   = pipeline.retrieve(query, top_k=top_k)
    return {
        "query":         result.query,
        "retrieval_ms":  result.retrieval_ms,
        "total_chunks":  result.total_chunks,
        "results": [
            {
                "chunk_id":   r.chunk.chunk_id,
                "title":      r.chunk.title,
                "section":    r.chunk.section,
                "snippet":    r.snippet,
                "score":      r.score,
                "confidence": r.confidence,
            }
            for r in result.retrieved
        ],
    }
