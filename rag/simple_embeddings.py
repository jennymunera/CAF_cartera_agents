"""Simple Embeddings Module for RAG System using sentence-transformers.

Implements a lightweight embedding model using sentence-transformers library
for dense embeddings only, optimized for speed and efficiency.
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
import torch
from sentence_transformers import SentenceTransformer
import json
from pathlib import Path

from .config import EmbeddingsConfig


class SimpleEmbeddings:
    """Simple embeddings using sentence-transformers for dense embeddings only."""
    
    def __init__(self, config: EmbeddingsConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Device setup
        self.device = self._setup_device()
        
        # Load model
        self.model = None
        self._load_model()
        
        # Embedding cache
        self.embedding_cache = {}
        
    def _setup_device(self) -> str:
        """Setup computation device with automatic GPU detection."""
        if self.config.device == "auto":
            # Check for CUDA availability first
            if torch.cuda.is_available():
                device = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                self.logger.info(f"✓ GPU detectada: {gpu_name} ({gpu_memory:.1f}GB) - Usando CUDA")
            # Check for MPS (Apple Silicon) if CUDA not available
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
                self.logger.info("✓ GPU Apple Silicon detectada - Usando MPS")
            else:
                device = "cpu"
                self.logger.info("⚠️ No se detectó GPU compatible - Usando CPU")
        else:
            device = self.config.device
            if device == "cuda" and not torch.cuda.is_available():
                self.logger.warning("CUDA solicitado pero no disponible, cambiando a CPU")
                device = "cpu"
            elif device == "mps" and not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
                self.logger.warning("MPS solicitado pero no disponible, cambiando a CPU")
                device = "cpu"
            
        return device
    
    def _load_model(self):
        """Load the sentence transformer model."""
        try:
            self.logger.info(f"Loading model: {self.config.model_name}")
            
            # Load model with device specification
            self.model = SentenceTransformer(
                self.config.model_name,
                device=self.device
            )
            
            # Set model to evaluation mode
            self.model.eval()
            
            self.logger.info(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            self.logger.error(f"Failed to load model {self.config.model_name}: {e}")
            raise
    
    def encode_texts(self, texts: List[str]) -> Dict[str, np.ndarray]:
        """Encode texts to embeddings."""
        if not texts:
            return {
                "dense": np.array([]),
                "sparse": None,
                "multi_vector": None
            }
        
        # Filter out None texts
        prepared_texts = [text for text in texts if text is not None]
        
        if not prepared_texts:
            return {
                "dense": np.array([]),
                "sparse": None,
                "multi_vector": None
            }
        
        try:
            # Encode using sentence-transformers
            embeddings = self.model.encode(
                prepared_texts,
                batch_size=self.config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=self.config.normalize
            )
            
            return {
                "dense": embeddings,
                "sparse": None,
                "multi_vector": None
            }
            
        except Exception as e:
            self.logger.error(f"Error encoding texts: {e}")
            raise
    
    def encode_single_text(self, text: str) -> Dict[str, np.ndarray]:
        """Encode a single text to embeddings."""
        batch_result = self.encode_texts([text])
        
        # Extract single result from batch
        return {
            "dense": batch_result["dense"][0:1] if batch_result["dense"].size > 0 else batch_result["dense"],
            "sparse": batch_result["sparse"],
            "multi_vector": batch_result["multi_vector"]
        }
    
    def compute_similarity(self, 
                          embeddings1: Dict[str, np.ndarray], 
                          embeddings2: Dict[str, np.ndarray],
                          similarity_type: str = "cosine") -> float:
        """Compute similarity between two embeddings."""
        if embeddings1["dense"] is None or embeddings2["dense"] is None:
            return 0.0
        
        emb1 = embeddings1["dense"]
        emb2 = embeddings2["dense"]
        
        if similarity_type == "cosine":
            # Normalize if not already normalized
            if not self.config.normalize:
                emb1 = emb1 / np.linalg.norm(emb1, axis=-1, keepdims=True)
                emb2 = emb2 / np.linalg.norm(emb2, axis=-1, keepdims=True)
            
            return float(np.dot(emb1.flatten(), emb2.flatten()))
        
        elif similarity_type == "euclidean":
            return float(-np.linalg.norm(emb1 - emb2))
        
        else:
            raise ValueError(f"Unsupported similarity type: {similarity_type}")
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of dense embeddings."""
        return self.config.dense_dim
    
    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self, 'model') and self.model is not None:
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            self.logger.info("Embeddings model cleanup completed")


class EmbeddingManager:
    """Manager for embedding operations with caching."""
    
    def __init__(self, config: EmbeddingsConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize embeddings model
        self.embeddings_model = SimpleEmbeddings(config)
        
        # Cache for embeddings
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def embed_documents(self, texts: List[str], use_cache: bool = True) -> List[Dict[str, np.ndarray]]:
        """Embed a list of documents with optional caching."""
        if not texts:
            return []
        
        results = []
        texts_to_embed = []
        text_indices = []
        
        # Check cache for existing embeddings
        for i, text in enumerate(texts):
            if text is None:
                results.append(None)
                continue
            
            cache_key = hash(text) if use_cache else None
            
            if use_cache and cache_key in self.cache:
                results.append(self.cache[cache_key])
                self.cache_hits += 1
            else:
                results.append(None)  # Placeholder
                texts_to_embed.append(text)
                text_indices.append(i)
                if use_cache:
                    self.cache_misses += 1
        
        # Embed non-cached texts
        if texts_to_embed:
            batch_embeddings = self.embeddings_model.encode_texts(texts_to_embed)
            
            # Split batch embeddings back to individual documents
            for idx, text_idx in enumerate(text_indices):
                doc_embeddings = {
                    "dense": batch_embeddings["dense"][idx:idx+1],
                    "sparse": None,
                    "multi_vector": None
                }
                
                results[text_idx] = doc_embeddings
                
                # Cache the result
                if use_cache:
                    cache_key = hash(texts_to_embed[idx])
                    self.cache[cache_key] = doc_embeddings
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self.cache)
        }
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.logger.info("Embedding cache cleared")
    
    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self, 'embeddings_model'):
            self.embeddings_model.cleanup()
        self.clear_cache()
        self.logger.info("EmbeddingManager cleanup completed")