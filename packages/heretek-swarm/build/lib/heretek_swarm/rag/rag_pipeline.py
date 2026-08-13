"""
RAG Pipeline for Retrieval-Augmented Generation.

Orchestrates document ingestion, hybrid retrieval, and LLM-based generation
using LiteLLM for embeddings and chat completions.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

import structlog

from heretek_swarm.rag.document_processor import (
    ChunkStrategy,
    DocumentProcessor,
    DocumentType,
    ProcessedDocument,
)
from heretek_swarm.rag.hybrid_retriever import (
    FusionMethod,
    HybridRetriever,
    HybridRetrieverConfig,
    RetrievalResult,
)

logger = structlog.get_logger(__name__)


@dataclass
class RAGPipelineConfig:
    """Configuration for the RAG pipeline."""

    # Embedding settings
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embeddingDimensions: int | None = None

    # LLM settings
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    max_tokens: int = 1000
    temperature: float = 0.7

    # Retrieval settings
    top_k: int = 5
    rerank_top_k: int = 10
    score_threshold: float = 0.0
    fusion_method: str = "reciprocal_rank"

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: int = 50
    chunk_strategy: str = "recursive"

    # Context settings
    max_context_chunks: int = 5
    context_window_chars: int = 8000

    # Rate limiting
    rate_limit_rpm: int = 60

    # Cache settings
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600


@dataclass
class IngestedDocument:
    """Result of document ingestion."""

    document_id: str
    chunks_ingested: int
    processing_time_ms: float


@dataclass
class RAGResponse:
    """Response from a RAG query."""

    answer: str
    sources: list[dict[str, Any]]
    context_used: str
    retrieval_results: list[RetrievalResult]
    latency_ms: float
    model_used: str


class RAGPipeline:
    """
    RAG Pipeline orchestrating retrieval and generation.

    Provides a unified interface for:
    - Document ingestion with chunking and embedding
    - Hybrid retrieval using vector + sparse search
    - LLM-based generation with retrieved context
    """

    def __init__(
        self,
        config: RAGPipelineConfig | None = None,
        hybrid_retriever: HybridRetriever | None = None,
        document_processor: DocumentProcessor | None = None,
    ):
        """
        Initialize the RAG pipeline.

        Args:
            config: Pipeline configuration
            hybrid_retriever: Optional pre-configured retriever
            document_processor: Optional pre-configured processor
        """
        self.config = config or RAGPipelineConfig()
        self.document_processor = document_processor or DocumentProcessor()
        self._hybrid_retriever = hybrid_retriever
        self._initialized = False
        self._litellm_available = self._check_litellm()

    def _check_litellm(self) -> bool:
        """Check if LiteLLM is available."""
        try:
            import importlib.util

            return importlib.util.find_spec("litellm") is not None
        except ImportError:
            logger.warning("litellm_not_installed_rag")
            return False

    async def initialize(self) -> None:
        """
        Initialize the pipeline components.

        Sets up the hybrid retriever and any required services.
        """
        if self._initialized:
            return

        # Configure embedding provider
        from heretek_swarm.embeddings.providers.factory import create_embedding_provider

        api_key = os.environ.get("OPENAI_API_KEY")

        embedding_config = {
            "api_key": api_key,
            "default_model": self.config.embedding_model,
        }

        embedding_provider = create_embedding_provider(
            self.config.embedding_provider,
            embedding_config,
        )

        # Create hybrid retriever if not provided
        if self._hybrid_retriever is None:
            retriever_config = HybridRetrieverConfig(
                fusion_method=FusionMethod(self.config.fusion_method),
                dense_weight=0.5,
                sparse_weight=0.3,
                rerank_top_k=self.config.rerank_top_k,
                enable_reranking=True,
                cache_enabled=self.config.cache_enabled,
                cache_ttl_seconds=self.config.cache_ttl_seconds,
                rate_limit_queries_per_minute=self.config.rate_limit_rpm,
            )

            self._hybrid_retriever = HybridRetriever(
                config=retriever_config,
                embedding_provider=embedding_provider,
            )

        await self._hybrid_retriever.initialize()
        self._initialized = True

        logger.info("rag_pipeline_initialized", config=self.config)

    async def ingest(
        self,
        documents: list[str] | str,
        metadata: dict[str, Any] | None = None,
        document_type: DocumentType = DocumentType.TEXT,  # noqa: ARG002
        chunk_strategy: ChunkStrategy | None = None,
    ) -> list[IngestedDocument]:
        """
        Ingest documents into the RAG pipeline.

        Processes documents through chunking, embedding, and indexing.

        Args:
            documents: Single document or list of documents to ingest
            metadata: Optional metadata to attach to documents
            document_type: Type of document (TEXT, MARKDOWN, etc.)
            chunk_strategy: Override default chunking strategy

        Returns:
            List of ingestion results with document IDs and chunk counts

        Raises:
            RuntimeError: If pipeline is not initialized
        """
        if not self._initialized:
            await self.initialize()

        metadata = metadata or {}
        chunk_strategy or ChunkStrategy(self.config.chunk_strategy)

        if isinstance(documents, str):
            documents = [documents]

        results = []

        for doc_idx, document in enumerate(documents):
            start_time = time.time()

            # Process document (chunk)
            processed: ProcessedDocument = await self.document_processor.process_content(
                content=document,
                source_path=metadata.get("source", f"doc_{doc_idx}"),
                metadata=metadata,
            )

            # Merge document-level metadata with per-chunk metadata
            doc_metadata = {**metadata, "document_id": processed.id}

            # Index each chunk through the retriever
            chunks_indexed = 0
            for chunk_idx, chunk in enumerate(processed.chunks):
                chunk_metadata = {
                    **doc_metadata,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(processed.chunks),
                }

                # The retriever's vector store handles embedding + indexing
                # We pass the chunk with metadata for storage
                vs = getattr(self._hybrid_retriever, "vector_store", None)
                if vs is not None:
                    await self._index_chunk(
                        chunk_id=f"{processed.id}_chunk_{chunk_idx}",
                        chunk_content=chunk,
                        metadata=chunk_metadata,
                    )
                    chunks_indexed += 1

            processing_time_ms = (time.time() - start_time) * 1000

            results.append(
                IngestedDocument(
                    document_id=processed.id,
                    chunks_ingested=chunks_indexed or len(processed.chunks),
                    processing_time_ms=processing_time_ms,
                )
            )

            # Register in lightweight document registry for list_documents()
            self._register_document(
                doc_id=processed.id,
                metadata={
                    "filename": metadata.get("filename", f"doc_{doc_idx}"),
                    "chunks": chunks_indexed or len(processed.chunks),
                    "ingested_at": datetime.now(UTC).isoformat(),
                },
            )

            logger.debug(
                "document_ingested",
                document_id=processed.id,
                chunks=chunks_indexed or len(processed.chunks),
                processing_time_ms=processing_time_ms,
            )

        return results

    async def _index_chunk(
        self,
        chunk_id: str,
        chunk_content: str,
        metadata: dict[str, Any],
    ) -> None:
        """
        Index a single chunk into the vector store.

        Args:
            chunk_id: Unique identifier for this chunk
            chunk_content: Text content of the chunk
            metadata: Associated metadata
        """
        # Get embedding for the chunk

        embedding_response = await self._hybrid_retriever.embedding_provider.embed(
            texts=chunk_content,
            model=self.config.embedding_model,
            dimensions=self.config.embeddingDimensions,
        )

        embedding = embedding_response.embeddings[0]

        # Store in vector store if available
        if self._hybrid_retriever.vector_store:
            await self._hybrid_retriever.vector_store.upsert(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk_content],
                metadatas=[metadata],
            )

    async def query(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        conversation_id: str | None = None,  # noqa: ARG002
    ) -> RAGResponse:
        """
        Query the RAG pipeline.

        Retrieves relevant context and generates a response using LiteLLM.

        Args:
            question: The question to answer
            top_k: Number of context chunks to retrieve (default from config)
            filters: Optional metadata filters for retrieval
            conversation_id: Optional conversation ID for context

        Returns:
            RAGResponse with answer, sources, and metadata

        Raises:
            RuntimeError: If pipeline is not initialized
            RuntimeError: If LiteLLM is not available
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        top_k = top_k or self.config.top_k

        # Step 1: Retrieve relevant context
        retrieval_results = await self._hybrid_retriever.retrieve(
            query=question,
            top_k=top_k,
            filters=filters,
        )

        # Step 2: Format context from retrieval results
        context_parts = []
        sources = []

        for i, result in enumerate(retrieval_results[: self.config.max_context_chunks]):
            context_parts.append(f"[{i + 1}] {result.content}")
            sources.append(
                {
                    "content": result.content,
                    "score": result.score,
                    "source": result.source,
                    "metadata": result.metadata,
                }
            )

        # Truncate context if too long
        context_str = "\n\n".join(context_parts)
        if len(context_str) > self.config.context_window_chars:
            context_str = context_str[: self.config.context_window_chars] + "..."

        # Step 3: Generate response using LiteLLM
        answer = await self._generate_response(question, context_str)

        latency_ms = (time.time() - start_time) * 1000

        return RAGResponse(
            answer=answer,
            sources=sources,
            context_used=context_str,
            retrieval_results=retrieval_results,
            latency_ms=latency_ms,
            model_used=f"{self.config.llm_provider}/{self.config.llm_model}",
        )

    async def _generate_response(self, question: str, context: str) -> str:
        """
        Generate a response using LiteLLM.

        Args:
            question: The user's question
            context: Retrieved context to use in generation

        Returns:
            Generated answer string
        """
        if not self._litellm_available:
            return self._simulated_response(question, context)

        try:
            import litellm

            litellm.api_key = os.environ.get("OPENAI_API_KEY")

            prompt = self._build_prompt(question, context)

            response = await litellm.acompletion(
                model=f"{self.config.llm_provider}/{self.config.llm_model}",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI assistant that answers questions "
                            "based on the provided context. "
                            "If the context doesn't contain relevant information, say so."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            return f"[Error generating response: {e!s}]"

    def _build_prompt(self, question: str, context: str) -> str:
        """
        Build the prompt for the LLM.

        Args:
            question: The user's question
            context: Retrieved context

        Returns:
            Formatted prompt string
        """
        return f"""Context:
{context}

Question: {question}

Answer based on the context provided above."""

    def _simulated_response(self, question: str, context: str) -> str:
        """
        Return a simulated response when LiteLLM is unavailable.

        Args:
            question: The user's question
            context: Retrieved context

        Returns:
            Simulated response string
        """
        return (
            f"[Simulated response - LiteLLM not available]\n\n"
            f"Question: {question}\n\n"
            f"Relevant context found: {len(context)} characters"
        )

    async def retrieve_context(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> tuple[str, list[RetrievalResult]]:
        """
        Retrieve context without generating a response.

        Useful for debugging or when you want to retrieve without generation.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            Tuple of (formatted context string, raw retrieval results)
        """
        if not self._initialized:
            await self.initialize()

        return await self._hybrid_retriever.retrieve_with_context(
            query=query,
            context=None,
            top_k=top_k or self.config.top_k,
        )

    def get_retriever(self) -> HybridRetriever:
        """
        Get the underlying hybrid retriever.

        Returns:
            The HybridRetriever instance
        """
        return self._hybrid_retriever

    async def close(self) -> None:
        """Close the pipeline and release resources."""
        if self._hybrid_retriever:
            await self._hybrid_retriever.close()
        self._initialized = False
        logger.info("rag_pipeline_closed")

    async def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List documents tracked by the pipeline.

        This provides a lightweight document registry by tracking what
        the pipeline has ingested. Full document/chunk retrieval requires
        the vector store's query capability.

        Args:
            limit: Maximum documents to return
            offset: Pagination offset

        Returns:
            List of document metadata dicts
        """
        # Maintain a lightweight in-memory document registry.
        # Each ingest() call registers its document_id in _ingested_docs.
        all_docs = list(self._ingested_docs.values())
        return all_docs[offset : offset + limit]

    @property
    def _ingested_docs(self) -> dict[str, dict[str, Any]]:
        """Lazy document registry keyed by document_id."""
        if not hasattr(self, "_document_registry"):
            self._document_registry: dict[str, dict[str, Any]] = {}
        return self._document_registry

    def _register_document(self, doc_id: str, metadata: dict[str, Any]) -> None:
        """Register a document in the in-memory registry."""
        self._ingested_docs[doc_id] = {
            "document_id": doc_id,
            "filename": metadata.get("filename", "unknown"),
            "chunks_ingested": metadata.get("chunks", 0),
            "ingested_at": metadata.get("ingested_at"),
        }

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
