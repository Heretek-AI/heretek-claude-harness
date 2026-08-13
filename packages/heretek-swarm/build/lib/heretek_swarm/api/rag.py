"""
RAG API - Document Ingestion and Retrieval

Provides REST API for:
- Document ingestion and processing
- Vector search and retrieval
- RAG query execution
- Document management
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile

if TYPE_CHECKING:
    from heretek_swarm.rag.cognee_graph import GraphRetriever
    from heretek_swarm.rag.knowledge_graph import KnowledgeGraphRetriever
    from heretek_swarm.rag.rag_pipeline import RAGPipeline

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.rag.document_processor import DocumentType

# RAG is fully integrated inside heretek_swarm.rag

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])

# Global RAG pipeline instance
_rag_pipeline: RAGPipeline | None = None  # type: ignore

# =============================================================================
# Lifecycle Management
# =============================================================================


async def get_rag_pipeline() -> RAGPipeline:
    """Get or initialize RAG pipeline instance."""
    global _rag_pipeline
    if _rag_pipeline is None:
        from heretek_swarm.rag.rag_pipeline import RAGPipeline

        _rag_pipeline = RAGPipeline()
        await _rag_pipeline.initialize()
    return _rag_pipeline


# =============================================================================
# Document Ingestion Endpoints
# =============================================================================


@router.post("/ingest", status_code=201)
async def ingest_document(
    file: UploadFile,
    metadata: dict[str, Any] | None = None,
    chunk_strategy: str = "recursive",
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Ingest a document into the RAG system.

    Args:
        file: Uploaded document file
        metadata: Optional metadata to attach
        chunk_strategy: Chunking strategy (recursive, fixed_size, semantic, sentence)
        authenticated: Authentication token

    Returns:
        Processing result with chunk count and vector storage status
    """
    pipeline = await get_rag_pipeline()

    try:
        # Read file content
        content = (await file.read()).decode("utf-8")

        # Ingest document content via the pipeline's ingest method.
        # Note: ingest() takes list[str] | str, not a file path + content pattern.
        results = await pipeline.ingest(
            documents=content,
            metadata={"filename": file.filename, **(metadata or {})},
            document_type=DocumentType.TEXT,
        )

        # Return the first result's fields (pipeline.ingest returns list[IngestedDocument])
        result = results[0] if results else None

        logger.info(
            "document_ingested",
            filename=file.filename,
            chunks_processed=result.chunks_ingested if result else 0,
            vectors_stored=result.chunks_ingested if result else 0,  # approximate
        )

        return {
            "filename": file.filename,
            "chunks_processed": result.chunks_ingested if result else 0,
            "vectors_stored": result.chunks_ingested if result else 0,
            "processing_time_ms": result.processing_time_ms if result else 0,
            "document_id": result.document_id if result else file.filename,
        }

    except Exception as e:
        logger.error("ingest_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {e!s}") from e


@router.post("/ingest/batch", status_code=201)
async def ingest_batch(
    files: list[UploadFile],
    metadata: dict[str, Any] | None = None,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Ingest multiple documents in batch.

    Args:
        files: List of uploaded files
        metadata: Optional metadata to attach
        authenticated: Authentication token

    Returns:
        Batch processing results
    """
    pipeline = await get_rag_pipeline()

    results = []
    total_chunks = 0
    total_vectors = 0

    for file in files:
        try:
            content = await file.read()
            result = await pipeline.ingest_file(
                file_path=file.filename,
                content=content.decode("utf-8"),
                metadata=metadata,
            )

            results.append(
                {
                    "filename": file.filename,
                    "chunks_processed": result.chunks_processed,
                    "vectors_stored": result.vectors_stored,
                    "document_id": result.id,
                }
            )

            total_chunks += result.chunks_processed
            total_vectors += result.vectors_stored

        except Exception as e:
            logger.error("batch_ingest_failed", filename=file.filename, error=str(e))
            results.append(
                {
                    "filename": file.filename,
                    "error": "Ingestion failed for this file",
                }
            )

    logger.info(
        "batch_ingest_completed",
        total_files=len(files),
        total_chunks=total_chunks,
        total_vectors=total_vectors,
    )

    return {
        "results": results,
        "total_files": len(files),
        "total_chunks": total_chunks,
        "total_vectors": total_vectors,
    }


# =============================================================================
# Search and Retrieval Endpoints
# =============================================================================


@router.post("/query", status_code=200)
async def query_rag(
    query: str,
    top_k: int = 5,
    search_mode: str = "hybrid",
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Query the RAG system for relevant documents.

    Args:
        query: Search query text
        top_k: Number of results to return
        search_mode: Search mode (vector_only, keyword_only, hybrid)
        authenticated: Authentication token

    Returns:
        Search results with documents and context
    """
    pipeline = await get_rag_pipeline()

    try:
        result = await pipeline.query(
            query_text=query,
            top_k=top_k,
            search_mode=search_mode,
        )

        logger.info(
            "rag_query_executed",
            query=query,
            documents_found=len(result.documents),
            retrieval_time_ms=result.retrieval_time_ms,
        )

        return {
            "query": query,
            "documents": [d.to_dict() for d in result.documents],
            "context": result.context,
            "total_tokens": result.total_tokens,
            "retrieval_time_ms": result.retrieval_time_ms,
            "embedding_time_ms": result.embedding_time_ms,
            "total_time_ms": result.total_time_ms,
        }

    except Exception as e:
        logger.error("rag_query_failed", query=query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to execute RAG query: {e!s}") from e


@router.get("/documents", status_code=200)
async def list_documents(
    limit: int = 100, offset: int = 0, authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """
    List all ingested documents.

    Args:
        limit: Maximum number of documents to return
        offset: Offset for pagination
        authenticated: Authentication token

    Returns:
        List of documents with metadata
    """
    pipeline = await get_rag_pipeline()

    try:
        # Get all documents from vector store
        documents = await pipeline.list_documents(
            limit=limit,
            offset=offset,
        )

        logger.info("documents_listed", count=len(documents))

        return {
            "documents": documents,
            "count": len(documents),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error("list_documents_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {e!s}") from e


@router.get("/documents/{document_id}", status_code=200)
async def get_document(
    document_id: str, authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """
    Get a specific document by ID.

    Args:
        document_id: Document ID
        authenticated: Authentication token

    Returns:
        Document details with chunks
    """
    pipeline = await get_rag_pipeline()

    try:
        document = await pipeline.get_document(document_id)

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        logger.info("document_retrieved", document_id=document_id)

        return {
            "id": document.id,
            "source_path": document.source_path,
            "source_type": document.source_type.value,
            "title": document.title,
            "author": document.author,
            "total_characters": document.total_characters,
            "total_lines": document.total_lines,
            "total_chunks": document.total_chunks,
            "created_at": document.created_at,
            "processing_time_ms": document.processing_time_ms,
            "chunk_strategy": document.chunk_strategy.value,
        }

    except Exception as e:
        logger.error("get_document_failed", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get document: {e!s}") from e


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, authenticated: str = Depends(verify_auth)):
    """
    Delete a document and its associated vectors.

    Args:
        document_id: Document ID
        authenticated: Authentication token

    Returns:
        Success message
    """
    pipeline = await get_rag_pipeline()

    try:
        success = await pipeline.delete_document(document_id)

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        logger.info("document_deleted", document_id=document_id)

        return {"message": f"Document {document_id} deleted successfully"}

    except Exception as e:
        logger.error("delete_document_failed", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e!s}") from e


# =============================================================================
# RAG Configuration Endpoints
# =============================================================================


@router.get("/config", status_code=200)
async def get_rag_config(authenticated: str = Depends(verify_auth)) -> dict[str, Any]:
    """
    Get current RAG configuration.

    Args:
        authenticated: Authentication token

    Returns:
        RAG pipeline configuration
    """
    pipeline = await get_rag_pipeline()

    return {
        "chunking": {
            "strategy": pipeline.config.processing.chunk_strategy.value,
            "chunk_size": pipeline.config.processing.chunk_size,
            "chunk_overlap": pipeline.config.processing.chunk_overlap,
            "min_chunk_size": pipeline.config.processing.min_chunk_size,
        },
        "embedding": {
            "provider": pipeline.config.embedding.provider.value,
            "model": pipeline.config.embedding.model,
            "dimension": pipeline.config.embedding.dimension,
        },
        "retrieval": {
            "mode": pipeline.config.retrieval.mode.value,
            "top_k": pipeline.config.retrieval.top_k,
            "similarity_threshold": pipeline.config.retrieval.similarity_threshold,
        },
        "storage": {
            "collection_name": pipeline.config.collection_name,
            "persist_processed": pipeline.config.persist_processed,
        },
    }


@router.post("/config", status_code=200)
async def update_rag_config(
    config: dict[str, Any], authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """
    Update RAG configuration.

    Args:
        config: Configuration updates
        authenticated: Authentication token

    Returns:
        Updated configuration
    """
    pipeline = await get_rag_pipeline()

    try:
        _update_chunking_config(pipeline, config.get("chunking"))
        _update_embedding_config(pipeline, config.get("embedding"))
        _update_retrieval_config(pipeline, config.get("retrieval"))
        _update_storage_config(pipeline, config.get("storage"))

        logger.info("rag_config_updated", config=config)

        return {
            "message": "RAG configuration updated successfully",
            "config": {
                "chunking": {
                    "strategy": pipeline.config.processing.chunk_strategy.value,
                    "chunk_size": pipeline.config.processing.chunk_size,
                    "chunk_overlap": pipeline.config.processing.chunk_overlap,
                },
                "embedding": {
                    "provider": pipeline.config.embedding.provider.value,
                    "model": pipeline.config.embedding.model,
                    "dimension": pipeline.config.embedding.dimension,
                },
                "retrieval": {
                    "mode": pipeline.config.retrieval.mode.value,
                    "top_k": pipeline.config.retrieval.top_k,
                    "similarity_threshold": pipeline.config.retrieval.similarity_threshold,
                },
                "storage": {
                    "collection_name": pipeline.config.collection_name,
                    "persist_processed": pipeline.config.persist_processed,
                },
            },
        }

    except Exception as e:
        logger.error("update_rag_config_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update RAG config: {e!s}") from e


def _update_chunking_config(pipeline: RAGPipeline, chunking: dict[str, Any] | None) -> None:
    """Update chunking configuration."""
    if not chunking:
        return
    if "strategy" in chunking:
        pipeline.config.processing.chunk_strategy = chunking["strategy"]
    if "chunk_size" in chunking:
        pipeline.config.processing.chunk_size = chunking["chunk_size"]
    if "chunk_overlap" in chunking:
        pipeline.config.processing.chunk_overlap = chunking["chunk_overlap"]


def _update_embedding_config(pipeline: RAGPipeline, embedding: dict[str, Any] | None) -> None:
    """Update embedding configuration."""
    if not embedding:
        return
    if "provider" in embedding:
        pipeline.config.embedding.provider = embedding["provider"]
    if "model" in embedding:
        pipeline.config.embedding.model = embedding["model"]


def _update_retrieval_config(pipeline: RAGPipeline, retrieval: dict[str, Any] | None) -> None:
    """Update retrieval configuration."""
    if not retrieval:
        return
    if "mode" in retrieval:
        pipeline.config.retrieval.mode = retrieval["mode"]
    if "top_k" in retrieval:
        pipeline.config.retrieval.top_k = retrieval["top_k"]
    if "similarity_threshold" in retrieval:
        pipeline.config.retrieval.similarity_threshold = retrieval["similarity_threshold"]


def _update_storage_config(pipeline: RAGPipeline, storage: dict[str, Any] | None) -> None:
    """Update storage configuration."""
    if not storage:
        return
    if "collection_name" in storage:
        pipeline.config.collection_name = storage["collection_name"]
    if "persist_processed" in storage:
        pipeline.config.persist_processed = storage["persist_processed"]


# =============================================================================
# Knowledge Graph Retrieval Endpoints (RAGFlow pattern)
# =============================================================================

_knowledge_graph_retriever: GraphRetriever | None = None


def get_knowledge_graph_retriever() -> GraphRetriever:
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
    from heretek_swarm.rag.knowledge_graph import GraphChunkNode

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

    return {"registered": count, "graph_size": len(kg._chunk_graph)}  # noqa: SLF001


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
    from heretek_swarm.rag.knowledge_graph import SubQuestionDecomposer

    decomposer = SubQuestionDecomposer()
    sub_questions = decomposer.decompose(query)

    return {"original": query, "sub_questions": sub_questions, "count": len(sub_questions)}
