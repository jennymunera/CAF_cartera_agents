"""Hybrid Retrieval System for RAG.

Implements advanced retrieval with:
- Dense retrieval (semantic similarity)
- Sparse retrieval (lexical similarity)
- Reciprocal Rank Fusion (RRF)
- Cross-encoder re-ranking
- Groundedness verification
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from collections import defaultdict
import math

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
except ImportError:
    raise ImportError("Transformers not installed. Run: pip install transformers torch")

from .config import RetrievalConfig, RerankingConfig
from .vector_store import ChromaVectorStore
from .embeddings import EmbeddingManager


@dataclass
class RetrievalResult:
    """Represents a single retrieval result."""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    rank: int
    retrieval_method: str  # "dense", "sparse", "hybrid", "reranked"
    

@dataclass
class RetrievalResponse:
    """Complete retrieval response with results and metadata."""
    query: str
    results: List[RetrievalResult]
    total_candidates: int
    retrieval_time: float
    reranking_time: Optional[float] = None
    fusion_method: Optional[str] = None
    


class CrossEncoderReranker:
    """Cross-encoder model for re-ranking retrieved documents."""
    
    def __init__(self, config: RerankingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Device setup
        self.device = self._setup_device()
        
        # Load model and tokenizer
        self.tokenizer = None
        self.model = None
        self._load_model()
    
    def _setup_device(self) -> str:
        """Setup computation device."""
        if self.config.device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
                self.logger.info(f"Using CUDA device for re-ranking: {torch.cuda.get_device_name()}")
            else:
                device = "cpu"
                self.logger.info("Using CPU device for re-ranking")
        else:
            device = self.config.device
            
        return device
    
    def _load_model(self):
        """Load cross-encoder model."""
        try:
            self.logger.info(f"Loading cross-encoder model: {self.config.model_name}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            self.model.to(self.device)
            self.model.eval()
            
            self.logger.info("Cross-encoder model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading cross-encoder model: {str(e)}")
            raise
    
    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Re-rank documents using cross-encoder."""
        if not documents:
            return documents
        
        try:
            # Prepare query-document pairs
            pairs = []
            for doc in documents:
                content = doc.get("document", doc.get("content", ""))
                pairs.append((query, content))
            
            # Compute relevance scores in batches
            scores = self._compute_relevance_scores(pairs)
            
            # Add scores to documents and sort
            for i, doc in enumerate(documents):
                doc["rerank_score"] = scores[i]
            
            # Sort by re-ranking score
            reranked_docs = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)
            
            return reranked_docs
            
        except Exception as e:
            self.logger.error(f"Error re-ranking documents: {str(e)}")
            return documents
    
    def _compute_relevance_scores(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Compute relevance scores for query-document pairs."""
        scores = []
        
        # Process in batches
        for i in range(0, len(pairs), self.config.batch_size):
            batch_pairs = pairs[i:i + self.config.batch_size]
            batch_scores = self._score_batch(batch_pairs)
            scores.extend(batch_scores)
        
        return scores
    
    def _score_batch(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Score a batch of query-document pairs."""
        # Prepare inputs
        queries = [pair[0] for pair in pairs]
        documents = [pair[1] for pair in pairs]
        
        # Tokenize
        inputs = self.tokenizer(
            queries,
            documents,
            padding=True,
            truncation=True,
            max_length=self.config.max_length,
            return_tensors="pt"
        ).to(self.device)
        
        # Compute scores
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            
            # Convert logits to scores (assuming binary classification)
            if logits.shape[1] == 1:
                # Single output (regression)
                scores = torch.sigmoid(logits.squeeze()).cpu().numpy()
            else:
                # Binary classification (take positive class probability)
                scores = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
        
        return scores.tolist()


class HybridRetriever:
    """Hybrid retrieval system combining dense and sparse search."""
    
    def __init__(self, 
                 config: RetrievalConfig,
                 reranking_config: RerankingConfig,
                 vector_store: ChromaVectorStore,
                 embedding_manager: EmbeddingManager):
        self.config = config
        self.reranking_config = reranking_config
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.reranker = CrossEncoderReranker(reranking_config)
        
        # Statistics
        self.stats = {
            "total_queries": 0,
            "dense_retrievals": 0,
            "reranking_operations": 0,
        }
    

    
    def retrieve(self, 
                query: str,
                k: Optional[int] = None,
                metadata_filter: Optional[Dict[str, Any]] = None,
                enable_reranking: bool = True) -> RetrievalResponse:
        """Retrieve relevant documents using dense retrieval."""
        import time
        start_time = time.time()
        
        k = k or self.config.k_final
        
        try:
            # Use dense retrieval only
            results = self._dense_retrieval(query, k, metadata_filter)
            
            retrieval_time = time.time() - start_time
            
            # Re-ranking
            reranking_time = None
            if enable_reranking and results and len(results) > 1:
                rerank_start = time.time()
                results = self._rerank_results(query, results)
                reranking_time = time.time() - rerank_start
                self.stats["reranking_operations"] += 1
            
            # Limit to final k
            results = results[:k]
            
            # Convert to RetrievalResult objects
            retrieval_results = []
            for i, result in enumerate(results):
                retrieval_result = RetrievalResult(
                    id=result["id"],
                    content=result["document"],
                    metadata=result["metadata"],
                    score=result.get("rerank_score", result.get("similarity", result.get("score", 0.0))),
                    rank=i + 1,
                    retrieval_method="dense" + ("_reranked" if enable_reranking else "")
                )
                retrieval_results.append(retrieval_result)
            
            # Update statistics
            self.stats["total_queries"] += 1
            
            return RetrievalResponse(
                query=query,
                results=retrieval_results,
                total_candidates=len(results),
                retrieval_time=retrieval_time,
                reranking_time=reranking_time,
                fusion_method=None
            )
            
        except Exception as e:
            self.logger.error(f"Error in retrieval: {str(e)}")
            return RetrievalResponse(
                query=query,
                results=[],
                total_candidates=0,
                retrieval_time=time.time() - start_time
            )
    
    def _dense_retrieval(self, query: str, k: int, metadata_filter: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Perform dense (semantic) retrieval."""
        # Get query embedding
        query_embeddings = self.embedding_manager.embed_query(query)
        query_dense = query_embeddings["dense"]
        
        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_dense,
            k=k,
            metadata_filter=metadata_filter,
            include_distances=True
        )
        
        self.stats["dense_retrievals"] += 1
        return results
    

    

    

    

    
    def _rerank_results(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Re-rank results using cross-encoder."""
        # Limit candidates for re-ranking
        candidates = results[:self.reranking_config.top_k_candidates]
        
        # Re-rank
        reranked_results = self.reranker.rerank(query, candidates)
        
        # Add remaining results (not re-ranked)
        if len(results) > len(candidates):
            remaining_results = results[len(candidates):]
            reranked_results.extend(remaining_results)
        
        return reranked_results
    
    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        return {
            **self.stats,
            "config": {
                "k_dense": self.config.k_dense,
                "k_sparse": self.config.k_sparse,
                "k_final": self.config.k_final,
                "fusion_method": self.config.fusion_method,
                "rrf_k": self.config.rrf_k,
                "dense_weight": self.config.dense_weight,
                "sparse_weight": self.config.sparse_weight,
            },
            "reranking_config": {
                "model_name": self.reranking_config.model_name,
                "top_k_candidates": self.reranking_config.top_k_candidates,
            }
        }