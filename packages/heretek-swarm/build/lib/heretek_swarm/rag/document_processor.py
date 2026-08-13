"""Document processing and chunking for RAG pipeline."""

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class DocumentType(Enum):
    """Document type enumeration."""

    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    HTML = "html"
    CODE = "code"
    JSON = "json"
    UNKNOWN = "unknown"

class ChunkStrategy(Enum):
    """Chunking strategy enumeration."""

    FIXED = "fixed"
    FIXED_SIZE = "fixed_size"
    RECURSIVE = "recursive"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"

@dataclass
class ProcessingConfig:
    """Configuration for document processing."""

    chunk_size: int = 512
    chunk_overlap: int = 50
    min_chunk_size: int = 50
    strategy: ChunkStrategy = ChunkStrategy.FIXED
    enable_heuristics: bool = True
    max_metadata_length: int = 500

@dataclass
class ProcessedDocument:
    """Processed document with chunks and metadata."""

    id: str
    content: str
    chunks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    document_type: DocumentType = DocumentType.TEXT

class DocumentProcessor:
    """Document processing and chunking."""

    def __init__(self, config: ProcessingConfig | None = None):
        self.config = config or ProcessingConfig()

    def detect_type(self, filename: str) -> DocumentType:
        """Detect document type from filename."""
        if filename.endswith((".md", ".markdown")):
            return DocumentType.MARKDOWN
        if filename.endswith(".pdf"):
            return DocumentType.PDF
        if filename.endswith((".html", ".htm")):
            return DocumentType.HTML
        if filename.endswith(".json"):
            return DocumentType.JSON
        if filename.endswith((".py", ".js", ".ts", ".rs", ".java", ".cpp", ".c", ".go")):
            return DocumentType.CODE
        if filename.endswith((".txt", ".text")):
            return DocumentType.TEXT
        return DocumentType.UNKNOWN

    def generate_id(self, content: str, source: str) -> str:
        """Generate document ID from content and source."""
        hash_obj = hashlib.sha256((content + source).encode())
        return f"doc_{hash_obj.hexdigest()[:16]}"

    def _extract_metadata(self, content: str, doc_type: DocumentType) -> dict[str, Any]:
        """Extract metadata from content."""
        metadata = {
            "type": doc_type.value,
            "length": len(content),
        }
        if doc_type == DocumentType.MARKDOWN:
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("#"):
                    metadata["title"] = line.lstrip("#").strip()
                    break
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
        if urls:
            metadata["url_count"] = len(urls)
        code_blocks = re.findall(r"```[\s\S]*?```|`[^`]+`", content)
        if code_blocks:
            metadata["code_snippets"] = len(code_blocks)
        return metadata

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content."""
        words = re.findall(r"\b[a-z]{4,}\b", content.lower())
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "they",
            "will",
            "been",
            "were",
            "when",
        }
        keywords = [w for w in words if w not in stop_words]
        return list(set(keywords))[:10]

    def _clean_content(self, content: str, doc_type: DocumentType) -> str:
        """Clean content based on document type."""
        if doc_type == DocumentType.HTML:
            content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"https?://\S+", "", content)
        return re.sub(r"\s+", " ", content).strip()

    def _chunk_fixed_size(
        self,
        text: str,
        doc_id: str,
        filename: str,
        doc_type: DocumentType,
    ) -> list[ProcessedDocument]:
        """Fixed-size chunking with proper overlap."""
        chunks = []
        content = self._clean_content(text, doc_type)
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        start = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_text = content[start:end]
            chunk_id = f"{doc_id}_chunk_{len(chunks)}"
            chunk_doc = ProcessedDocument(
                id=chunk_id,
                content=chunk_text,
                chunks=[chunk_text],
                metadata={
                    "source": filename,
                    "chunk_index": len(chunks),
                },
                document_type=doc_type,
            )
            chunks.append(chunk_doc)
            if end >= len(content):
                break
            start = end - overlap

        return chunks

    def _chunk_recursive(
        self,
        text: str,
        doc_id: str,
        filename: str,
        doc_type: DocumentType,
    ) -> list[ProcessedDocument]:
        """Recursive chunking by sentences/paragraphs."""
        chunks = []
        # Split by sentence-ending punctuation first, then group
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # Add period if missing
            if sentence[-1] not in ".!?":
                sentence += "."
            if len(current_chunk) + len(sentence) <= self.config.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    chunk_id = f"{doc_id}_chunk_{chunk_index}"
                    chunks.append(
                        ProcessedDocument(
                            id=chunk_id,
                            content=current_chunk.strip(),
                            chunks=[current_chunk.strip()],
                            metadata={"source": filename, "chunk_index": chunk_index},
                            document_type=doc_type,
                        )
                    )
                    chunk_index += 1
                current_chunk = sentence + " "

        # Don't forget the last chunk
        if current_chunk.strip():
            chunk_id = f"{doc_id}_chunk_{chunk_index}"
            chunks.append(
                ProcessedDocument(
                    id=chunk_id,
                    content=current_chunk.strip(),
                    chunks=[current_chunk.strip()],
                    metadata={"source": filename, "chunk_index": chunk_index},
                    document_type=doc_type,
                )
            )

        # Ensure at least one chunk
        if not chunks:
            chunk_id = f"{doc_id}_chunk_0"
            chunks.append(
                ProcessedDocument(
                    id=chunk_id,
                    content=text,
                    chunks=[text],
                    metadata={"source": filename, "chunk_index": 0},
                    document_type=doc_type,
                )
            )

        return chunks

    def _chunk(self, content: str) -> list[str]:
        """Split content into chunks."""
        if self.config.strategy in (ChunkStrategy.FIXED, ChunkStrategy.FIXED_SIZE):
            return self._fixed_chunk(content)
        if self.config.strategy == ChunkStrategy.RECURSIVE:
            return self._recursive_chunk(content)
        return [content]

    def _fixed_chunk(self, content: str) -> list[str]:
        """Fixed-size chunking."""
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        for i in range(0, len(content), chunk_size - overlap):
            chunk = content[i : i + chunk_size]
            if chunk:
                chunks.append(chunk)
        return chunks if chunks else [content]

    def _recursive_chunk(self, content: str) -> list[str]:
        """Recursive chunking."""
        sentences = re.split(r"(?<=[.!?])\s+", content)
        chunks = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) <= self.config.chunk_size:
                current += sentence + " "
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = sentence + " "
        if current.strip():
            chunks.append(current.strip())
        return chunks if chunks else [content]

    async def process_content(
        self,
        content: str,
        source_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProcessedDocument:
        """Process content for RAG pipeline."""
        doc_type = self.detect_type(source_path or "unknown.txt")
        doc_id = self.generate_id(content, source_path or "unknown")

        extracted_metadata = self._extract_metadata(content, doc_type)
        if metadata:
            extracted_metadata.update(metadata)

        chunks = []
        if self.config.strategy == ChunkStrategy.RECURSIVE:
            chunk_docs = self._chunk_recursive(content, doc_id, source_path or "unknown", doc_type)
            chunks = [c.content for c in chunk_docs]
        else:
            chunk_docs = self._chunk_fixed_size(content, doc_id, source_path or "unknown", doc_type)
            chunks = [c.content for c in chunk_docs]

        return ProcessedDocument(
            id=doc_id,
            content=content,
            chunks=chunks,
            metadata=extracted_metadata,
            document_type=doc_type,
        )

    def process(
        self,
        content: str,
        doc_type: DocumentType = DocumentType.TEXT,
    ) -> ProcessedDocument:
        """Process document into chunks."""
        doc_id = self.generate_id(content, "process")
        metadata = self._extract_metadata(content, doc_type)
        cleaned = self._clean_content(content, doc_type)
        chunks = self._chunk(cleaned)

        return ProcessedDocument(
            id=doc_id,
            content=content,
            chunks=chunks,
            metadata=metadata,
            document_type=doc_type,
        )
