"""Dense Embeddings Module for RAG System.

Implements dense embedding models for:
- Dense embeddings (semantic similarity)
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
import torch
from transformers import AutoTokenizer, AutoModel
import json
from pathlib import Path

from .config import EmbeddingsConfig
from .simple_embeddings import SimpleEmbeddings


class BGE_M3_Embeddings:
    """Dense embeddings with support for various embedding models."""
    
    def __init__(self, config: EmbeddingsConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Device setup
        self.device = self._setup_device()
        
        # Load model and tokenizer
        self.tokenizer = None
        self.model = None
        self._load_model()
        
        # Embedding cache
        self.embedding_cache = {}
        
    def _setup_device(self) -> str:
        """Setup computation device."""
        if self.config.device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
                self.logger.info(f"Using CUDA device: {torch.cuda.get_device_name()}")
            else:
                device = "cpu"
                self.logger.info("Using CPU device")
        else:
            device = self.config.device
            
        return device
    
    def _load_model(self):
        """Load embedding model and tokenizer."""
        try:
            self.logger.info(f"Loading embedding model: {self.config.model_name}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            # Load model
            self.model = AutoModel.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            # Move to device
            self.model.to(self.device)
            self.model.eval()
            
            self.logger.info("Embedding model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading embedding model: {str(e)}")
            raise
    
    def _prepare_texts(self, texts: List[str]) -> List[str]:
        """Prepare texts for embedding (truncation, cleaning)."""
        prepared_texts = []
        
        for text in texts:
            # Clean text
            cleaned_text = text.strip()
            
            # Truncate if necessary (rough estimation)
            if len(cleaned_text) > self.config.max_length * 4:  # 4 chars per token estimate
                cleaned_text = cleaned_text[:self.config.max_length * 4]
                self.logger.warning(f"Text truncated to {self.config.max_length * 4} characters")
            
            prepared_texts.append(cleaned_text)
        
        return prepared_texts
    
    def _encode_batch(self, texts: List[str]) -> Dict[str, torch.Tensor]:
        """Encode a batch of texts with dense embeddings only."""
        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.config.max_length,
            return_tensors="pt"
        ).to(self.device)
        
        # Generate embeddings
        with torch.no_grad():
            outputs = self.model(**inputs, return_dict=True)
            
            # Extract dense embeddings only
            embeddings = {
                "dense": outputs.last_hidden_state.mean(dim=1),  # Mean pooling for dense
            }
            
            # Normalize dense embeddings if configured
            if self.config.normalize:
                embeddings["dense"] = torch.nn.functional.normalize(
                    embeddings["dense"], p=2, dim=1
                )
        
        return embeddings
    

    
    def encode_texts(self, texts: List[str]) -> Dict[str, np.ndarray]:
        """Encode texts to embeddings."""
        if not texts:
            return {
                "dense": np.array([]),
                "sparse": np.array([]) if self.config.use_sparse else None,
                "multi_vector": np.array([]) if self.config.use_multivector != "false" else None,
            }
        
        # Prepare texts
        prepared_texts = self._prepare_texts(texts)
        
        # Process in batches
        all_dense = []
        
        for i in range(0, len(prepared_texts), self.config.batch_size):
            batch_texts = prepared_texts[i:i + self.config.batch_size]
            
            # Encode batch
            batch_embeddings = self._encode_batch(batch_texts)
            
            # Check if batch_embeddings is valid
            if batch_embeddings is None or batch_embeddings.get("dense") is None:
                self.logger.error(f"Invalid batch embeddings returned for batch {i//self.config.batch_size}: {batch_embeddings}")
                continue
            
            # Collect results
            all_dense.append(batch_embeddings["dense"].cpu().numpy())
        
        # Concatenate results
        result = {
            "dense": np.vstack(all_dense) if all_dense else np.array([]),
        }
        
        return result
    
    def encode_single_text(self, text: str) -> Dict[str, np.ndarray]:
        """Encode a single text to embeddings."""
        return self.encode_texts([text])
    
    def compute_similarity(self, 
                          embeddings1: Dict[str, np.ndarray], 
                          embeddings2: Dict[str, np.ndarray]) -> float:
        """Compute cosine similarity between two dense embeddings."""
        if embeddings1["dense"] is None or embeddings2["dense"] is None:
            return 0.0
            
        # Cosine similarity for dense embeddings
        vec1 = embeddings1["dense"].flatten()
        vec2 = embeddings2["dense"].flatten()
        
        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_embedding_dimensions(self) -> Dict[str, int]:
        """Get embedding dimensions for dense embeddings only."""
        return {
            "dense": self.config.dense_dim,
        }
    
    def save_embeddings(self, embeddings: Dict[str, np.ndarray], file_path: str):
        """Save embeddings to file."""
        save_data = {}
        
        for key, value in embeddings.items():
            if value is not None:
                save_data[key] = value.tolist()
            else:
                save_data[key] = None
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f)
    
    def load_embeddings(self, file_path: str) -> Dict[str, np.ndarray]:
        """Load embeddings from file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            save_data = json.load(f)
        
        embeddings = {}
        for key, value in save_data.items():
            if value is not None:
                embeddings[key] = np.array(value)
            else:
                embeddings[key] = None
        
        return embeddings
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            "model_name": self.config.model_name,
            "device": self.device,
            "max_length": self.config.max_length,
            "normalize": self.config.normalize,
            "embedding_dimensions": self.get_embedding_dimensions(),
        }


class EmbeddingManager:
    """Manager for handling embeddings operations."""
    
    def __init__(self, config: EmbeddingsConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize Simple embeddings (sentence-transformers)
        self.embeddings_model = SimpleEmbeddings(config)
        
        # Embedding cache for frequently used texts
        self.cache = {}
        self.cache_size_limit = 1000
    
    def embed_documents(self, documents: List[str], use_cache: bool = True) -> List[Dict[str, np.ndarray]]:
        """Embed multiple documents."""
        if not documents:
            return []
        
        embeddings_list = []
        texts_to_embed = []
        cache_keys = []
        
        # Check cache
        for doc in documents:
            cache_key = hash(doc) if use_cache else None
            cache_keys.append(cache_key)
            
            if use_cache and cache_key in self.cache:
                embeddings_list.append(self.cache[cache_key])
                texts_to_embed.append(None)  # Placeholder
            else:
                embeddings_list.append(None)  # Placeholder
                texts_to_embed.append(doc)
        
        # Embed non-cached documents
        non_cached_docs = [doc for doc in texts_to_embed if doc is not None]
        if non_cached_docs:
            batch_embeddings = self.embeddings_model.encode_texts(non_cached_docs)
            
            # Split batch embeddings back to individual documents
            batch_idx = 0
            for i, doc in enumerate(texts_to_embed):
                if doc is not None:
                    # Check if batch_embeddings and dense embeddings are valid
                    if batch_embeddings is None or batch_embeddings.get("dense") is None:
                        self.logger.error(f"Invalid batch embeddings for document {i}: {batch_embeddings}")
                        continue
                    
                    # Extract embeddings for this document
                    doc_embeddings = {
                        "dense": batch_embeddings["dense"][batch_idx:batch_idx+1],
                    }
                    
                    embeddings_list[i] = doc_embeddings
                    
                    # Cache if enabled
                    if use_cache and cache_keys[i] is not None:
                        self._add_to_cache(cache_keys[i], doc_embeddings)
                    
                    batch_idx += 1
        
        return embeddings_list
    
    def embed_query(self, query: str) -> Dict[str, np.ndarray]:
        """Embed a single query."""
        return self.embeddings_model.encode_single_text(query)
    
    def _add_to_cache(self, key: int, embeddings: Dict[str, np.ndarray]):
        """Add embeddings to cache with size limit."""
        if len(self.cache) >= self.cache_size_limit:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = embeddings
    
    def clear_cache(self):
        """Clear embedding cache."""
        self.cache.clear()
        self.logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self.cache),
            "cache_limit": self.cache_size_limit,
            "cache_usage": len(self.cache) / self.cache_size_limit,
        }
    
    def compute_similarities(self, 
                           query_embeddings: Dict[str, np.ndarray],
                           document_embeddings: List[Dict[str, np.ndarray]]) -> List[float]:
        """Compute similarities between query and multiple documents."""
        similarities = []
        
        for doc_embeddings in document_embeddings:
            similarity = self.embeddings_model.compute_similarity(
                query_embeddings, doc_embeddings
            )
            similarities.append(similarity)
        
        return similarities
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get embedding model information."""
        return self.embeddings_model.get_model_info()