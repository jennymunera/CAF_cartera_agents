"""RAG System Configuration.

Centralized configuration for all RAG components including:
- Dense embeddings settings
- ChromaDB vector store configuration
- Azure Document Intelligence parameters
- Chunking and retrieval settings
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path


@dataclass
class EmbeddingsConfig:
    """Configuration for sentence-transformers embeddings."""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    normalize: bool = True
    use_sparse: bool = False  # Desactivar sparse embeddings para evitar errores
    use_multivector: str = "false"  # Usar solo embeddings densos
    max_length: int = 512  # MiniLM max sequence length
    batch_size: int = 32
    device: str = "cpu"  # auto, cpu, cuda
    
    # Embedding dimensions
    dense_dim: int = 384  # MiniLM dense embedding dimension
    sparse_dim: int = 0  # No sparse embeddings


@dataclass
class ChromaDBConfig:
    """Configuration for ChromaDB vector store."""
    persist_directory: str = "./rag_vectorstore"
    collection_name: str = "rag_documents"
    
    # HTTP Client settings for Docker ChromaDB
    use_http_client: bool = True  # Use HTTP client by default
    host: str = "localhost"
    port: int = 8000
    
    # HNSW index parameters
    hnsw_m: int = 64  # Number of bi-directional links for each node
    hnsw_ef_search: int = 128  # Size of dynamic candidate list
    hnsw_ef_construction: int = 200  # Size of dynamic candidate list during construction
    
    # Distance metric
    distance_metric: str = "cosine"  # cosine, l2, ip
    
    # Batch settings
    batch_size: int = 1000
    

@dataclass
class ChunkingConfig:
    """Configuration for semantic chunking."""
    target_tokens: int = 1000  # Target chunk size in tokens
    min_tokens: int = 800  # Minimum chunk size
    max_tokens: int = 1200  # Maximum chunk size
    overlap_tokens: int = 100  # Overlap between chunks
    
    # Semantic chunking parameters
    respect_sections: bool = True  # Respect document sections
    respect_paragraphs: bool = True  # Respect paragraph boundaries
    respect_sentences: bool = True  # Respect sentence boundaries
    
    # Language detection
    detect_language: bool = True
    default_language: str = "es"  # Default language for documents
    

@dataclass
class RetrievalConfig:
    """Configuration for hybrid retrieval."""
    # Retrieval parameters
    k_dense: int = 50  # Number of dense retrieval candidates
    k_sparse: int = 50  # Number of sparse retrieval candidates
    k_final: int = 8  # Final number of results after re-ranking
    
    # Fusion method
    fusion_method: str = "rrf"  # rrf, weighted_sum
    rrf_k: int = 60  # RRF parameter
    
    # Weighted sum parameters (if fusion_method = "weighted_sum")
    dense_weight: float = 0.6
    sparse_weight: float = 0.4
    
    # Pre-filtering
    enable_metadata_filters: bool = True
    

@dataclass
class RerankingConfig:
    """Configuration for cross-encoder re-ranking."""
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Modelo más simple y estable
    batch_size: int = 16
    max_length: int = 512
    device: str = "auto"  # auto, cpu, cuda
    
    # Re-ranking parameters
    top_k_candidates: int = 100  # Number of candidates to re-rank
    

@dataclass
class AzureDocumentIntelligenceConfig:
    """Configuration for Azure Document Intelligence."""
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model_id: str = "prebuilt-layout"
    
    # Processing parameters
    extract_tables: bool = True
    extract_key_value_pairs: bool = True
    extract_paragraphs: bool = True
    extract_sections: bool = True
    
    # Language detection
    detect_language: bool = True
    
    def __post_init__(self):
        """Load Azure credentials from environment if not provided."""
        if self.endpoint is None:
            self.endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        if self.api_key is None:
            self.api_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
            
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure Document Intelligence credentials not found. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY "
                "environment variables or pass them explicitly."
            )


@dataclass
class EvaluationConfig:
    """Configuration for RAG evaluation and observability."""
    # Groundedness checking
    enable_groundedness_check: bool = True
    groundedness_threshold: float = 0.7
    
    # Metrics collection
    enable_metrics: bool = True
    metrics_log_file: str = "rag_metrics.jsonl"
    
    # Evaluation datasets
    eval_dataset_path: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "rag_system.log"
    

@dataclass
class RAGConfig:
    """Main RAG system configuration."""
    # Component configurations
    embeddings: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    reranking: RerankingConfig = field(default_factory=RerankingConfig)
    azure_di: AzureDocumentIntelligenceConfig = field(default_factory=AzureDocumentIntelligenceConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    
    # General settings
    project_name: str = "CrewAI_RAG_System"
    version: str = "1.0.0"
    
    # Paths
    base_dir: str = "./"
    input_dir: str = "input_docs"
    output_dir: str = "output_docs"
    
    def __post_init__(self):
        """Validate configuration and create directories."""
        self._validate_config()
        self._create_directories()
    
    def _validate_config(self):
        """Validate configuration parameters."""
        # Validate chunking parameters
        if self.chunking.min_tokens >= self.chunking.max_tokens:
            raise ValueError("min_tokens must be less than max_tokens")
        
        if self.chunking.target_tokens < self.chunking.min_tokens or \
           self.chunking.target_tokens > self.chunking.max_tokens:
            raise ValueError("target_tokens must be between min_tokens and max_tokens")
        
        # Validate retrieval parameters
        if self.retrieval.k_final > min(self.retrieval.k_dense, self.retrieval.k_sparse):
            raise ValueError("k_final cannot be greater than k_dense or k_sparse")
        
        # Validate fusion weights
        if self.retrieval.fusion_method == "weighted_sum":
            total_weight = self.retrieval.dense_weight + self.retrieval.sparse_weight
            if abs(total_weight - 1.0) > 1e-6:
                raise ValueError("Dense and sparse weights must sum to 1.0")
    
    def _create_directories(self):
        """Create necessary directories."""
        directories = [
            self.input_dir,
            self.output_dir,
            self.chromadb.persist_directory,
            os.path.dirname(self.evaluation.metrics_log_file),
            os.path.dirname(self.evaluation.log_file),
        ]
        
        for directory in directories:
            if directory and directory != ".":
                Path(directory).mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "embeddings": self.embeddings.__dict__,
            "chromadb": self.chromadb.__dict__,
            "chunking": self.chunking.__dict__,
            "retrieval": self.retrieval.__dict__,
            "reranking": self.reranking.__dict__,
            "azure_di": {
                k: v for k, v in self.azure_di.__dict__.items() 
                if k not in ["api_key"]  # Don't expose API key
            },
            "evaluation": self.evaluation.__dict__,
            "project_name": self.project_name,
            "version": self.version,
            "base_dir": self.base_dir,
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "RAGConfig":
        """Create configuration from dictionary."""
        # Extract component configs
        embeddings_config = EmbeddingsConfig(**config_dict.get("embeddings", {}))
        chromadb_config = ChromaDBConfig(**config_dict.get("chromadb", {}))
        chunking_config = ChunkingConfig(**config_dict.get("chunking", {}))
        retrieval_config = RetrievalConfig(**config_dict.get("retrieval", {}))
        reranking_config = RerankingConfig(**config_dict.get("reranking", {}))
        azure_di_config = AzureDocumentIntelligenceConfig(**config_dict.get("azure_di", {}))
        evaluation_config = EvaluationConfig(**config_dict.get("evaluation", {}))
        
        return cls(
            embeddings=embeddings_config,
            chromadb=chromadb_config,
            chunking=chunking_config,
            retrieval=retrieval_config,
            reranking=reranking_config,
            azure_di=azure_di_config,
            evaluation=evaluation_config,
            project_name=config_dict.get("project_name", "CrewAI_RAG_System"),
            version=config_dict.get("version", "1.0.0"),
            base_dir=config_dict.get("base_dir", "./"),
            input_dir=config_dict.get("input_dir", "input_docs"),
            output_dir=config_dict.get("output_dir", "output_docs"),
        )
    
    def save_to_file(self, file_path: str):
        """Save configuration to JSON file."""
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> "RAGConfig":
        """Load configuration from JSON file."""
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)


# Default configuration instance
default_config = RAGConfig()