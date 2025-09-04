"""RAG (Retrieval-Augmented Generation) System for IXP Document Analysis.

This module provides a comprehensive RAG implementation with:
- Azure Document Intelligence integration
- Dense embeddings for semantic similarity
- ChromaDB vector storage with HNSW indexing
- Hybrid retrieval with RRF fusion
- Cross-encoder re-ranking
- Integration with CrewAI agents
- Comprehensive observability and evaluation
"""

__version__ = "1.0.0"
__author__ = "RAG System Team"

# Core components
from .config import RAGConfig
from .rag_pipeline import RAGPipeline

# Document processing
from .document_processor import (
    DocumentProcessor,
    ProcessedDocument,
    DocumentChunk,
    SemanticChunker,
    AzureDocumentProcessor
)

# Embeddings and vector storage
from .embeddings import EmbeddingManager
from .simple_embeddings import SimpleEmbeddings
from .vector_store import ChromaVectorStore

# Retrieval system
from .retriever import (
    HybridRetriever,

    CrossEncoderReranker,
    RetrievalResponse
)

# Observability and evaluation
from .observability import (
    RAGObservability,
    MetricsCollector,
    PerformanceTracker,
    QueryMetrics,
    IndexingMetrics,
    SystemMetrics
)

from .evaluation import (
    RAGEvaluator,
    RetrievalEvaluator,
    GenerationEvaluator,
    RetrievalEvaluation,
    GenerationEvaluation,
    EndToEndEvaluation
)

__all__ = [
    # Core
    "RAGConfig",
    "RAGPipeline",
    
    # Document processing
    "DocumentProcessor",
    "ProcessedDocument",
    "DocumentChunk",
    "SemanticChunker",
    "AzureDocumentProcessor",
    
    # Embeddings and storage
    "EmbeddingManager",
    "ChromaVectorStore",
    
    # Retrieval
    "HybridRetriever",

    "CrossEncoderReranker",
    "RetrievalResponse",
    
    # Observability
    "RAGObservability",
    "MetricsCollector",
    "PerformanceTracker",
    "QueryMetrics",
    "IndexingMetrics",
    "SystemMetrics",
    
    # Evaluation
    "RAGEvaluator",
    "RetrievalEvaluator",
    "GenerationEvaluator",
    "RetrievalEvaluation",
    "GenerationEvaluation",
    "EndToEndEvaluation",
]