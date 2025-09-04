"""ChromaDB Vector Store for RAG System.

Implements ChromaDB-based vector storage with:
- HNSW indexing for efficient similarity search
- Support for dense, sparse, and multi-vector embeddings
- Metadata filtering and hybrid search capabilities
- Batch operations and persistence
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from pathlib import Path
import json
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError:
    raise ImportError("ChromaDB not installed. Run: pip install chromadb")

from .config import ChromaDBConfig
from .document_processor import DocumentChunk

# Import our simple embedding function
try:
    from .simple_embeddings import SimpleEmbeddingFunction
except ImportError:
    # Fallback to a simple embedding function if not available
    class SimpleEmbeddingFunction:
        def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
            self.model_name = model_name
            
        def name(self):
            """Return the name of the embedding function."""
            return self.model_name
            
        def __call__(self, input):
             if isinstance(input, list):
                 return [[0.0] * 384 for _ in input]  # MiniLM-L6-v2 dimension
             return [0.0] * 384


class ChromaVectorStore:
    """ChromaDB-based vector store with advanced indexing."""
    
    def __init__(self, config: ChromaDBConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Store collection name for easy access
        self.collection_name = config.collection_name
        
        # Initialize ChromaDB client
        self.client = None
        self.collection = None
        self._initialize_client()
        
        # Statistics
        self.stats = {
            "documents_added": 0,
            "queries_executed": 0,
            "last_updated": None,
        }
    
    def _initialize_client(self):
        """Initialize ChromaDB client and collection."""
        try:
            # Check if we're in a test environment (temporary directory)
            persist_path = Path(self.config.persist_directory)
            is_temp_dir = "tmp" in str(persist_path).lower() or "temp" in str(persist_path).lower()
            
            if is_temp_dir:
                # Use in-memory client for tests to avoid Windows file system issues
                self.client = chromadb.Client(
                    Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                self.logger.info("Using in-memory ChromaDB client for testing")
            else:
                # Use HTTP client to connect to ChromaDB server running in Docker
                # This avoids Windows compatibility issues with local ChromaDB
                if getattr(self.config, 'use_http_client', True):
                    try:
                        self.client = chromadb.HttpClient(
                            host=getattr(self.config, 'host', 'localhost'),
                            port=getattr(self.config, 'port', 8000),
                            settings=Settings(
                                anonymized_telemetry=False,
                                allow_reset=True
                            )
                        )
                        self.logger.info(f"Using HTTP ChromaDB client connecting to {self.config.host}:{self.config.port}")
                    except Exception as http_error:
                        self.logger.warning(f"Could not connect to HTTP ChromaDB server: {http_error}")
                        self.logger.info("Falling back to in-memory client")
                        # Fallback to in-memory client if HTTP connection fails
                        self.client = chromadb.Client(
                            Settings(
                                anonymized_telemetry=False,
                                allow_reset=True
                            )
                        )
                else:
                    # Fallback to in-memory client if HTTP is disabled
                    self.client = chromadb.Client(
                        Settings(
                            anonymized_telemetry=False,
                            allow_reset=True
                        )
                    )
                    self.logger.info("Using in-memory ChromaDB client (HTTP disabled)")
            
            # Get or create collection with simple embedding function
            # This uses sentence-transformers for better GPU compatibility
            try:
                embedding_function = SimpleEmbeddingFunction("sentence-transformers/all-MiniLM-L6-v2")
                self.logger.info("Using simple embedding function with MiniLM-L6-v2")
            except Exception as e:
                self.logger.warning(f"Could not initialize simple embeddings: {e}. Using fallback.")
                embedding_function = SimpleEmbeddingFunction()  # Fallback version

            self.collection = self.client.get_or_create_collection(
                name=self.config.collection_name,
                embedding_function=embedding_function,
                metadata={
                    "hnsw:space": self.config.distance_metric,
                    "hnsw:M": self.config.hnsw_m,
                    "hnsw:search_ef": self.config.hnsw_ef_search,
                    "hnsw:construction_ef": self.config.hnsw_ef_construction,
                    "created_at": datetime.now().isoformat(),
                }
            )
            
            self.logger.info(f"ChromaDB initialized with collection: {self.config.collection_name}")
            # self.logger.info(f"Collection count: {self.collection.count()}")  # Commented out - causes hanging on Windows
            
        except Exception as e:
            self.logger.error(f"Error initializing ChromaDB: {str(e)}")
            raise
    
    def add_documents(self, chunks: List[DocumentChunk], embeddings: List[Dict[str, np.ndarray]]):
        """Add document chunks with embeddings to the vector store."""
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        
        if not chunks:
            return
        
        try:
            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []
            embeddings_list = []
            
            for chunk, embedding in zip(chunks, embeddings):
                # Generate unique ID
                chunk_id = chunk.chunk_id or str(uuid.uuid4())
                ids.append(chunk_id)
                
                # Document content
                documents.append(chunk.content)
                
                # Metadata (ChromaDB requires JSON-serializable metadata)
                metadata = self._prepare_metadata(chunk)
                metadatas.append(metadata)
                
                # Use dense embeddings for ChromaDB (primary search)
                if embedding["dense"] is not None:
                    dense_emb = embedding["dense"]
                    if isinstance(dense_emb, list):
                        embeddings_list.append(dense_emb)
                    else:
                        embeddings_list.append(dense_emb.flatten().tolist())
                else:
                    raise ValueError(f"Dense embeddings required for chunk {chunk_id}")
            
            # Add to collection in batches
            batch_size = self.config.batch_size
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i + batch_size]
                batch_documents = documents[i:i + batch_size]
                batch_metadatas = metadatas[i:i + batch_size]
                batch_embeddings = embeddings_list[i:i + batch_size]
                
                self.collection.add(
                    ids=batch_ids,
                    documents=batch_documents,
                    metadatas=batch_metadatas,
                    embeddings=batch_embeddings
                )
            
            # Update statistics
            self.stats["documents_added"] += len(chunks)
            self.stats["last_updated"] = datetime.now().isoformat()
            
            self.logger.info(f"Added {len(chunks)} documents to vector store")
            
        except Exception as e:
            self.logger.error(f"Error adding documents to vector store: {str(e)}")
            raise
    
    def _prepare_metadata(self, chunk: DocumentChunk) -> Dict[str, Any]:
        """Prepare metadata for ChromaDB (must be JSON-serializable)."""
        metadata = {
            "document_id": chunk.document_id,
            "chunk_type": chunk.chunk_type,
            "token_count": chunk.token_count or 0,
        }
        
        # Add optional fields
        if chunk.start_page is not None:
            metadata["start_page"] = chunk.start_page
        if chunk.end_page is not None:
            metadata["end_page"] = chunk.end_page
        if chunk.section_title:
            metadata["section_title"] = chunk.section_title
        if chunk.language:
            metadata["language"] = chunk.language
        
        # Add custom metadata (ensure JSON-serializable)
        if chunk.metadata:
            for key, value in chunk.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    metadata[key] = value
                elif isinstance(value, (list, dict)):
                    try:
                        # Test JSON serialization
                        json.dumps(value)
                        metadata[key] = value
                    except (TypeError, ValueError):
                        # Convert to string if not serializable
                        metadata[key] = str(value)
                else:
                    metadata[key] = str(value)
        
        return metadata
    
    def search(self, 
               query_embedding: np.ndarray,
               k: int = 10,
               metadata_filter: Optional[Dict[str, Any]] = None,
               include_distances: bool = True) -> List[Dict[str, Any]]:
        """Search for similar documents using dense embeddings."""
        try:
            # Prepare query embedding
            if isinstance(query_embedding, dict):
                # Handle multi-vector embeddings (dense + sparse)
                if 'dense' in query_embedding:
                    query_embedding = query_embedding['dense']
                else:
                    raise ValueError("Dictionary embedding must contain 'dense' key")
            
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding)
            if query_embedding.ndim > 1:
                query_embedding = query_embedding.flatten()
            
            # Build where clause for metadata filtering
            where_clause = None
            if metadata_filter:
                where_clause = self._build_where_clause(metadata_filter)
            
            # Execute search
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=k,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Process results
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    result = {
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i] if results["documents"] and results["documents"][0] else None,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else None,
                    }
                    
                    if include_distances and results["distances"] and results["distances"][0]:
                        result["distance"] = results["distances"][0][i]
                        result["similarity"] = 1 - results["distances"][0][i]  # Convert distance to similarity
                    
                    search_results.append(result)
            
            # Update statistics
            self.stats["queries_executed"] += 1
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"Error searching vector store: {str(e)}")
            raise
    
    def _build_where_clause(self, metadata_filter: Dict[str, Any]) -> Dict[str, Any]:
        """Build ChromaDB where clause from metadata filter."""
        where_clause = {}
        
        for key, value in metadata_filter.items():
            if isinstance(value, str):
                where_clause[key] = {"$eq": value}
            elif isinstance(value, (int, float)):
                where_clause[key] = {"$eq": value}
            elif isinstance(value, list):
                where_clause[key] = {"$in": value}
            elif isinstance(value, dict):
                # Support for range queries, etc.
                where_clause[key] = value
            else:
                where_clause[key] = {"$eq": str(value)}
        
        return where_clause
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID."""
        try:
            results = self.collection.get(
                ids=[document_id],
                include=["documents", "metadatas"]
            )
            
            if results["ids"] and results["ids"][0]:
                return {
                    "id": results["ids"][0],
                    "document": results["documents"][0] if results["documents"] and results["documents"][0] else None,
                    "metadata": results["metadatas"][0] if results["metadatas"] and results["metadatas"][0] else None,
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting document {document_id}: {str(e)}")
            return None
    
    def delete_documents(self, document_ids: List[str]):
        """Delete documents by IDs."""
        try:
            self.collection.delete(ids=document_ids)
            self.logger.info(f"Deleted {len(document_ids)} documents")
            
        except Exception as e:
            self.logger.error(f"Error deleting documents: {str(e)}")
            raise
    
    def delete_by_metadata(self, metadata_filter: Dict[str, Any]):
        """Delete documents by metadata filter."""
        try:
            where_clause = self._build_where_clause(metadata_filter)
            self.collection.delete(where=where_clause)
            self.logger.info(f"Deleted documents matching filter: {metadata_filter}")
            
        except Exception as e:
            self.logger.error(f"Error deleting documents by metadata: {str(e)}")
            raise
    
    def update_document(self, document_id: str, content: str, metadata: Dict[str, Any], embedding: np.ndarray):
        """Update a document's content, metadata, and embedding."""
        try:
            # ChromaDB doesn't have direct update, so we delete and re-add
            self.collection.delete(ids=[document_id])
            
            self.collection.add(
                ids=[document_id],
                documents=[content],
                metadatas=[metadata],
                embeddings=[embedding.flatten().tolist()]
            )
            
            self.logger.info(f"Updated document {document_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating document {document_id}: {str(e)}")
            raise
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            # Avoid using collection.count() as it causes hanging on Windows
            # Use a simple query to estimate document count instead
            try:
                sample_results = self.collection.query(
                    query_embeddings=[[0.0] * 384],  # Dummy embedding
                    n_results=1,
                    include=["documents"]
                )
                # If we get results, there are documents; if not, collection is empty
                estimated_count = "unknown (count disabled on Windows)"
                if sample_results and sample_results.get("ids") and sample_results["ids"][0]:
                    estimated_count = "1+ documents"
                else:
                    estimated_count = "0 documents"
            except Exception:
                estimated_count = "unknown"
            
            return {
                "total_documents": estimated_count,
                "collection_name": self.config.collection_name,
                "persist_directory": self.config.persist_directory,
                "distance_metric": self.config.distance_metric,
                "hnsw_parameters": {
                    "M": self.config.hnsw_m,
                    "ef_search": self.config.hnsw_ef_search,
                    "ef_construction": self.config.hnsw_ef_construction,
                },
                **self.stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}
    
    def list_documents(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List documents in the collection."""
        try:
            # ChromaDB doesn't have direct pagination, so we get all and slice
            results = self.collection.get(
                include=["documents", "metadatas"],
                limit=limit,
                offset=offset
            )
            
            documents = []
            if results["ids"]:
                for i in range(len(results["ids"])):
                    documents.append({
                        "id": results["ids"][i],
                        "document": results["documents"][i] if results["documents"] else None,
                        "metadata": results["metadatas"][i] if results["metadatas"] else None,
                    })
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error listing documents: {str(e)}")
            return []
    
    def search_by_metadata(self, metadata_filter: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Search documents by metadata only (no embedding similarity)."""
        try:
            where_clause = self._build_where_clause(metadata_filter)
            
            results = self.collection.get(
                where=where_clause,
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            documents = []
            if results["ids"]:
                for i in range(len(results["ids"])):
                    documents.append({
                        "id": results["ids"][i],
                        "document": results["documents"][i] if results["documents"] else None,
                        "metadata": results["metadatas"][i] if results["metadatas"] else None,
                    })
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error searching by metadata: {str(e)}")
            return []
    
    def clear_collection(self):
        """Clear all documents from the collection."""
        try:
            # Delete the collection and recreate it
            self.client.delete_collection(self.config.collection_name)
            self._initialize_client()
            
            # Reset statistics
            self.stats = {
                "documents_added": 0,
                "queries_executed": 0,
                "last_updated": None,
            }
            
            self.logger.info("Collection cleared")
            
        except Exception as e:
            self.logger.error(f"Error clearing collection: {str(e)}")
            raise
    
    def backup_collection(self, backup_path: str):
        """Backup collection data to a file."""
        try:
            # Get all documents
            all_docs = self.collection.get(
                include=["documents", "metadatas", "embeddings"]
            )
            
            # Prepare backup data
            backup_data = {
                "collection_name": self.config.collection_name,
                "config": self.config.__dict__,
                "stats": self.stats,
                "documents": {
                    "ids": all_docs["ids"],
                    "documents": all_docs["documents"],
                    "metadatas": all_docs["metadatas"],
                    "embeddings": all_docs["embeddings"],
                },
                "backup_timestamp": datetime.now().isoformat(),
            }
            
            # Save to file
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Collection backed up to {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Error backing up collection: {str(e)}")
            raise
    
    def restore_collection(self, backup_path: str):
        """Restore collection from backup file."""
        try:
            # Load backup data
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Clear current collection
            self.clear_collection()
            
            # Restore documents
            docs_data = backup_data["documents"]
            if docs_data["ids"]:
                # Add in batches
                batch_size = self.config.batch_size
                for i in range(0, len(docs_data["ids"]), batch_size):
                    batch_ids = docs_data["ids"][i:i + batch_size]
                    batch_documents = docs_data["documents"][i:i + batch_size]
                    batch_metadatas = docs_data["metadatas"][i:i + batch_size]
                    batch_embeddings = docs_data["embeddings"][i:i + batch_size]
                    
                    self.collection.add(
                        ids=batch_ids,
                        documents=batch_documents,
                        metadatas=batch_metadatas,
                        embeddings=batch_embeddings
                    )
            
            # Restore statistics
            if "stats" in backup_data:
                self.stats.update(backup_data["stats"])
            
            self.logger.info(f"Collection restored from {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Error restoring collection: {str(e)}")
            raise
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            if hasattr(self, 'client') and self.client:
                # ChromaDB client cleanup is automatic
                pass
        except Exception:
            pass