"""
RAG API - Document Ingestion and Retrieval

Provides REST API for:
- Document ingestion and processing (via CogneeRAGRetriever.register_chunks)
- Vector search and retrieval (via CogneeRAGRetriever.retrieve)
- Knowledge graph retrieval (via cognee_graph.GraphRetriever)
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.rag.cognee_rag import CogneeRAGRetriever, get_rag_retriever

# RAG is fully integrated inside heretek_swarm.rag

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])

# Global RAG retriever instance
_rag_retriever: CogneeRAGRetriever | None = None

# =============================================================================
# Lifecycle Management
# =============================================================================


async def get_or_create_rag_retriever() -> CogneeRAGRetriever:
    """Get or create the shared CogneeRAGRetriever instance.

    CogneeRAGRetriever is ready immediately after construction — there is
    no separate async initialize() step.
    """
    global _rag_retriever
    if _rag_retriever is None:
        _rag_retriever = get_rag_retriever()
    return _rag_retriever


# =============================================================================
# Document Ingestion Endpoints
# =============================================================================


@router.post("/ingest", status_code=201)
async def ingest_document(
    file: UploadFile,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Ingest a document into the RAG system.

    Args:
        file: Uploaded document file
        authenticated: Authentication token

    Returns:
        Processing result with chunk count
    """
    retriever = await get_or_create_rag_retriever()

    try:
        # Read file content
        content = (await file.read()).decode("utf-8")

        # Best-effort ingest via CogneeRAGRetriever.register_chunks
        # Cognee ingestion is async and goes through a separate cognee.add() path.
        # register_chunks is a stub that logs the chunks for future ingest.
        retriever.register_chunks([{"content": content, "filename": file.filename}])

        logger.info(
            "document_ingested",
            filename=file.filename,
        )

        return {
            "filename": file.filename,
            "status": "registered",
            "detail": "Content registered for ingestion; Cognee async ingest TBD",
        }

    except Exception as e:
        logger.error("ingest_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {e!s}") from e


@router.post("/ingest/batch", status_code=201)
async def ingest_batch(
    files: list[UploadFile],
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Ingest multiple documents in batch.

    Args:
        files: List of uploaded files
        authenticated: Authentication token

    Returns:
        Batch processing results
    """
    retriever = await get_or_create_rag_retriever()

    results = []
    for file in files:
        try:
            content = (await file.read()).decode("utf-8")
            retriever.register_chunks([{"content": content, "filename": file.filename}])
            results.append({"filename": file.filename, "status": "registered"})
        except Exception as e:
            logger.error("batch_ingest_failed", filename=file.filename, error=str(e))
            results.append({"filename": file.filename, "error": "Ingestion failed for this file"})

    logger.info(
        "batch_ingest_completed",
        total_files=len(files),
    )

    return {
        "results": results,
        "total_files": len(files),
    }


# =============================================================================
# Search and Retrieval Endpoints
# =============================================================================


@router.post("/query", status_code=200)
async def query_rag(
    query: str,
    top_k: int = 5,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Query the RAG system for relevant documents.

    Args:
        query: Search query text
        top_k: Number of results to return
        authenticated: Authentication token

    Returns:
        Search results with documents and context
    """
    retriever = await get_or_create_rag_retriever()

    try:
        results = await retriever.retrieve(query=query, top_k=top_k)

        logger.info(
            "rag_query_executed",
            query=query,
            documents_found=len(results),
        )

        return {
            "query": query,
            "results": [
                {
                    "content": r.content,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "count": len(results),
        }

    except Exception as e:
        logger.error("rag_query_failed", query=query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to execute RAG query: {e!s}") from e


@router.get("/documents", status_code=200)
async def list_documents(
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    List all ingested documents.

    Note: CogneeRAGRetriever has no document management, so this returns
    an empty list. Document management is handled at the Cognee level.

    Args:
        authenticated: Authentication token

    Returns:
        List of documents with metadata
    """
    logger.info("documents_listed", note="CogneeRAGRetriever does not expose document list")
    return {"documents": [], "count": 0}


@router.get("/documents/{document_id}", status_code=200)
async def get_document(
    document_id: str, authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """
    Get a specific document by ID.

    Note: CogneeRAGRetriever has no document management, so this
    returns 404 for all documents.

    Args:
        document_id: Document ID
        authenticated: Authentication token

    Returns:
        Document details
    """
    logger.info("document_retrieved", document_id=document_id, note="not supported")
    raise HTTPException(status_code=404, detail="Document not found")


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, authenticated: str = Depends(verify_auth)):
    """
    Delete a document and its associated vectors.

    Note: CogneeRAGRetriever has no document management, so this is a
    no-op that always returns 204.

    Args:
        document_id: Document ID
        authenticated: Authentication token
    """
    logger.info("document_delete_noop", document_id=document_id)
    return None


# =============================================================================
# RAG Configuration Endpoints
# =============================================================================


@router.get("/config", status_code=200)
async def get_rag_config(authenticated: str = Depends(verify_auth)) -> dict[str, Any]:
    """
    Get current RAG configuration.

    CogneeRAGRetriever has no separate Config object. Returns static
    metadata about the retriever.

    Args:
        authenticated: Authentication token

    Returns:
        RAG configuration overview
    """
    retriever = await get_or_create_rag_retriever()
    return {
        "backend": "cognee",
        "statistics": retriever.get_statistics(),
    }


@router.post("/config", status_code=200)
async def update_rag_config(
    config: dict[str, Any], authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """
    Update RAG configuration.

    CogneeRAGRetriever has no runtime-configurable Config object.
    Configuration is set at construction via env vars.

    Args:
        config: Configuration updates (accepted but ignored)
        authenticated: Authentication token

    Returns:
        Static acknowledgement
    """
    retriever = await get_or_create_rag_retriever()
    logger.info("rag_config_update_noop", received=config)
    return {
        "message": "CogneeRAGRetriever has no runtime config; configuration is env-driven",
        "backend": "cognee",
        "statistics": retriever.get_statistics(),
    }


# =============================================================================
# Knowledge Graph Retrieval Endpoints (RAGFlow pattern)
# =============================================================================

_knowledge_graph_retriever: Any = None


def get_knowledge_graph_retriever() -> Any:
    """Get or initialize the knowledge graph retriever.

    M-arch PR #3: delegates to the :func:`cognee_graph.get_graph_retriever`
    factory, which selects between the legacy in-memory
    :class:`KnowledgeGraphRetriever` (default) and the new
    :class:`CogneeGraphRetriever` (opt-in via
    ``HERETEK_USE_COGNEE_GRAPH=true``).
    """
    global _knowledge_graph_retriever
    if _knowledge_graph_retriever is None:
        from heretek_swarm.rag.cognee_graph import get_graph_retriever

        _knowledge_graph_retriever = get_graph_retriever()
    return _knowledge_graph_retriever


@router.post("/graph/query", status_code=200)
async def query_with_graph(
    query: str,
    top_k: int = 5,
    seed_chunk_ids: str | None = None,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Query using graph-based retrieval (RAGFlow pattern).

    Exploits document heading structure and chunk hierarchy
    for better context in complex queries.

    Args:
        query: Search query
        top_k: Number of results
        seed_chunk_ids: Optional comma-separated seed chunk IDs for graph expansion

    Returns:
        Graph retrieval results with traversal metadata
    """
    kg = get_knowledge_graph_retriever()

    seed_list = seed_chunk_ids.split(",") if seed_chunk_ids else None

    results = await kg.retrieve(
        query=query,
        top_k=top_k,
        seed_chunk_ids=seed_list,
    )

    return {
        "query": query,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "score": r.score,
                "heading_path": r.heading_path,
                "hop_depth": r.hop_depth,
                "traversal_path": r.traversal_path,
                "document_id": r.document_id,
            }
            for r in results
        ],
        "count": len(results),
    }


@router.post("/graph/chunks", status_code=201)
async def register_graph_chunks(
    chunks: list[dict[str, Any]],
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Register document chunks in the knowledge graph.

    Builds parent-child heading relationships automatically based on the
    heading_path hierarchy in each chunk.

    Expects chunk dicts with: chunk_id, document_id, content, heading_path,
    parent_chunk_id, level.
    """
    from heretek_swarm.rag.cognee_graph import GraphChunkNode

    kg = get_knowledge_graph_retriever()

    nodes = [
        GraphChunkNode(
            chunk_id=c["chunk_id"],
            document_id=c["document_id"],
            content=c.get("content", ""),
            heading_path=c.get("heading_path", []),
            parent_chunk_id=c.get("parent_chunk_id"),
            level=c.get("level", 0),
            metadata=c.get("metadata", {}),
        )
        for c in chunks
    ]

    count = kg.register_chunks(nodes)

    return {"registered": count, "graph_size": len(kg._chunk_graph)}


@router.get("/graph/statistics", status_code=200)
async def get_graph_statistics(
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Get knowledge graph statistics."""
    kg = get_knowledge_graph_retriever()
    return kg.get_statistics()


@router.get("/graph/document/{document_id}/headings", status_code=200)
async def get_document_headings(
    document_id: str,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Get the heading tree for a document."""
    kg = get_knowledge_graph_retriever()
    headings = kg.get_document_headings(document_id)
    return {"document_id": document_id, "headings": headings, "count": len(headings)}


@router.post("/graph/decompose", status_code=200)
async def decompose_query(
    query: str,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Decompose a complex query into simpler sub-questions.

    Supports sequential, comparative, causal, and hierarchical decomposition.
    """
    from heretek_swarm.rag.cognee_graph import SubQuestionDecomposer

    decomposer = SubQuestionDecomposer()
    sub_questions = decomposer.decompose(query)

    return {"original": query, "sub_questions": sub_questions, "count": len(sub_questions)}
