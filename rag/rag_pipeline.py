"""Main RAG Pipeline for Document Analysis.

Orchestrates all RAG components:
- Document processing with Azure Document Intelligence
- Dense embeddings for semantic similarity
- ChromaDB vector storage with HNSW indexing
- Hybrid retrieval with RRF fusion and re-ranking
- Integration with CrewAI agents
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime

from .config import RAGConfig
from .document_processor import DocumentProcessor, ProcessedDocument, DocumentChunk
from .embeddings import EmbeddingManager
from .vector_store import ChromaVectorStore
from .retriever import HybridRetriever, RetrievalResponse


class RAGPipeline:
    """Main RAG pipeline orchestrating all components."""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.document_processor = None
        self.embedding_manager = None
        self.vector_store = None
        self.retriever = None
        
        # Pipeline state
        self.is_initialized = False
        self.indexed_documents = set()
        
        # Statistics
        self.stats = {
            "documents_processed": 0,
            "chunks_indexed": 0,
            "queries_processed": 0,
            "initialization_time": None,
            "last_indexing_time": None,
            "last_query_time": None,
        }
        
        # Initialize pipeline
        self._initialize_pipeline()
    
    def _initialize_pipeline(self):
        """Initialize all RAG components."""
        try:
            start_time = time.time()
            self.logger.info("Initializing RAG pipeline...")
            
            # Initialize document processor
            self.logger.info("Initializing document processor...")
            self.document_processor = DocumentProcessor(self.config)
            
            # Initialize embedding manager
            self.logger.info("Initializing embedding manager...")
            self.embedding_manager = EmbeddingManager(self.config.embeddings)
            
            # Initialize vector store
            self.logger.info("Initializing vector store...")
            self.vector_store = ChromaVectorStore(self.config.chromadb)
            
            # Initialize retriever
            self.logger.info("Initializing hybrid retriever...")
            self.retriever = HybridRetriever(
                config=self.config.retrieval,
                reranking_config=self.config.reranking,
                vector_store=self.vector_store,
                embedding_manager=self.embedding_manager
            )
            
            initialization_time = time.time() - start_time
            self.stats["initialization_time"] = initialization_time
            
            self.is_initialized = True
            self.logger.info(f"RAG pipeline initialized successfully in {initialization_time:.2f} seconds")
            
        except Exception as e:
            self.logger.error(f"Error initializing RAG pipeline: {str(e)}")
            raise
    
    def index_documents(self, 
                       file_paths: List[str], 
                       force_reprocess: bool = False,
                       batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Index documents into the RAG system."""
        if not self.is_initialized:
            raise RuntimeError("RAG pipeline not initialized")
        
        start_time = time.time()
        batch_size = batch_size or 10
        
        try:
            self.logger.info(f"Starting document indexing for {len(file_paths)} files")
            
            # Process documents in batches
            all_processed_docs = []
            processing_errors = []
            
            for i in range(0, len(file_paths), batch_size):
                batch_files = file_paths[i:i + batch_size]
                self.logger.info(f"Processing batch {i//batch_size + 1}/{(len(file_paths)-1)//batch_size + 1}")
                
                try:
                    # Process documents
                    batch_processed = self.document_processor.process_multiple_documents(
                        batch_files, force_reprocess
                    )
                    all_processed_docs.extend(batch_processed)
                    
                except Exception as e:
                    self.logger.error(f"Error processing batch {i//batch_size + 1}: {str(e)}")
                    processing_errors.append({
                        "batch": i//batch_size + 1,
                        "files": batch_files,
                        "error": str(e)
                    })
                    continue
            
            if not all_processed_docs:
                raise RuntimeError("No documents were successfully processed")
            
            # Extract all chunks
            all_chunks = []
            for processed_doc in all_processed_docs:
                all_chunks.extend(processed_doc.chunks)
            
            self.logger.info(f"Extracted {len(all_chunks)} chunks from {len(all_processed_docs)} documents")
            
            # Generate embeddings for chunks
            self.logger.info("Generating embeddings...")
            chunk_contents = [chunk.content for chunk in all_chunks]
            embeddings_list = self.embedding_manager.embed_documents(chunk_contents, use_cache=True)
            
            # Index chunks in vector store
            self.logger.info("Indexing chunks in vector store...")
            self.vector_store.add_documents(all_chunks, embeddings_list)
            
            # Add to sparse retrieval index
            self.logger.info("Building sparse retrieval index...")
            chunk_ids = [chunk.chunk_id for chunk in all_chunks]
            self.retriever.add_documents_to_sparse_index(chunk_ids, chunk_contents)
            
            # Update indexed documents tracking
            for processed_doc in all_processed_docs:
                self.indexed_documents.add(processed_doc.file_path)
            
            # Update statistics
            indexing_time = time.time() - start_time
            self.stats["documents_processed"] += len(all_processed_docs)
            self.stats["chunks_indexed"] += len(all_chunks)
            self.stats["last_indexing_time"] = indexing_time
            
            indexing_results = {
                "success": True,
                "documents_processed": len(all_processed_docs),
                "chunks_indexed": len(all_chunks),
                "indexing_time": indexing_time,
                "processing_errors": processing_errors,
                "processed_documents": [
                    {
                        "file_path": doc.file_path,
                        "document_id": doc.document_id,
                        "chunks_count": len(doc.chunks),
                        "total_tokens": doc.processing_stats.get("total_tokens", 0)
                    }
                    for doc in all_processed_docs
                ]
            }
            
            self.logger.info(
                f"Document indexing completed: {len(all_processed_docs)} documents, "
                f"{len(all_chunks)} chunks in {indexing_time:.2f} seconds"
            )
            
            return indexing_results
            
        except Exception as e:
            self.logger.error(f"Error during document indexing: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "indexing_time": time.time() - start_time
            }
    
    def process_single_document(self, file_path: str, force_reprocess: bool = False) -> Optional[ProcessedDocument]:
        """Process a single document without indexing it.
        
        Args:
            file_path: Path to the document to process
            force_reprocess: Whether to force reprocessing even if cached
            
        Returns:
            ProcessedDocument if successful, None if failed
        """
        if not self.is_initialized:
            raise RuntimeError("RAG pipeline not initialized")
        
        try:
            self.logger.info(f"Processing single document: {Path(file_path).name}")
            
            # Process the document
            processed_doc = self.document_processor.process_document(file_path, force_reprocess)
            
            self.logger.info(
                f"Document processed successfully: {len(processed_doc.chunks)} chunks, "
                f"{processed_doc.processing_stats.get('total_tokens', 0)} tokens"
            )
            
            return processed_doc
            
        except Exception as e:
            self.logger.error(f"Error processing document {file_path}: {str(e)}")
            return None
    
    def query(self, 
             query_text: str,
             k: Optional[int] = None,
             metadata_filter: Optional[Dict[str, Any]] = None,
             enable_reranking: bool = True,
             return_context: bool = True) -> Dict[str, Any]:
        """Query the RAG system for relevant documents."""
        if not self.is_initialized:
            raise RuntimeError("RAG pipeline not initialized")
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Processing query: {query_text[:100]}...")
            
            # Retrieve relevant documents
            retrieval_response = self.retriever.retrieve(
                query=query_text,
                k=k,
                metadata_filter=metadata_filter,
                enable_reranking=enable_reranking
            )
            
            # Prepare context if requested
            context = None
            if return_context and retrieval_response.results:
                context = self._build_context(retrieval_response.results)
            
            # Update statistics
            query_time = time.time() - start_time
            self.stats["queries_processed"] += 1
            self.stats["last_query_time"] = query_time
            
            query_results = {
                "success": True,
                "query": query_text,
                "results": [
                    {
                        "id": result.id,
                        "content": result.content,
                        "metadata": result.metadata,
                        "score": result.score,
                        "rank": result.rank,
                        "retrieval_method": result.retrieval_method
                    }
                    for result in retrieval_response.results
                ],
                "context": context,
                "total_candidates": retrieval_response.total_candidates,
                "retrieval_time": retrieval_response.retrieval_time,
                "reranking_time": retrieval_response.reranking_time,
                "total_query_time": query_time,
                "fusion_method": retrieval_response.fusion_method,
                "k": k or self.config.retrieval.k_final
            }
            
            self.logger.info(
                f"Query processed: {len(retrieval_response.results)} results in {query_time:.2f} seconds"
            )
            
            return query_results
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return {
                "success": False,
                "query": query_text,
                "error": str(e),
                "total_query_time": time.time() - start_time
            }
    
    def _build_context(self, results: List[Any]) -> str:
        """Build context string from retrieval results."""
        context_parts = []
        
        for i, result in enumerate(results):
            # Add document metadata for context
            doc_info = ""
            if result.metadata.get("document_id"):
                doc_info = f"[Documento: {result.metadata['document_id']}]"
            
            if result.metadata.get("section_title"):
                doc_info += f" [Sección: {result.metadata['section_title']}]"
            
            # Format context entry
            context_entry = f"--- Fragmento {i+1} {doc_info} ---\n{result.content}\n"
            context_parts.append(context_entry)
        
        return "\n".join(context_parts)
    
    def get_indexed_documents(self) -> List[str]:
        """Get list of indexed document paths."""
        return list(self.indexed_documents)
    
    def remove_document(self, document_id: str) -> bool:
        """Remove a document and its chunks from the index."""
        try:
            # Remove from vector store
            self.vector_store.delete_by_metadata({"document_id": document_id})
            
            # Remove from indexed documents tracking
            # Note: We'd need to track document_id -> file_path mapping for this
            # For now, we'll just log the removal
            self.logger.info(f"Removed document {document_id} from index")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing document {document_id}: {str(e)}")
            return False
    
    def clear_index(self) -> bool:
        """Clear all indexed documents."""
        try:
            self.vector_store.clear_collection()
            self.indexed_documents.clear()
            
            # Reset statistics
            self.stats["documents_processed"] = 0
            self.stats["chunks_indexed"] = 0
            self.stats["queries_processed"] = 0
            
            self.logger.info("Index cleared successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing index: {str(e)}")
            return False
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        vector_store_stats = self.vector_store.get_collection_stats()
        retrieval_stats = self.retriever.get_retrieval_stats()
        embedding_stats = self.embedding_manager.get_cache_stats()
        
        return {
            "pipeline_stats": self.stats,
            "vector_store_stats": vector_store_stats,
            "retrieval_stats": retrieval_stats,
            "embedding_stats": embedding_stats,
            "config_summary": {
                "embeddings_model": self.config.embeddings.model_name,
                "reranking_model": self.config.reranking.model_name,
                "fusion_method": self.config.retrieval.fusion_method,
                "k_final": self.config.retrieval.k_final,
            },
            "is_initialized": self.is_initialized,
            "indexed_documents_count": len(self.indexed_documents)
        }
    
    def save_pipeline_state(self, file_path: str):
        """Save pipeline state to file."""
        try:
            state_data = {
                "config": self.config.to_dict(),
                "stats": self.stats,
                "indexed_documents": list(self.indexed_documents),
                "is_initialized": self.is_initialized,
                "timestamp": datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Pipeline state saved to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving pipeline state: {str(e)}")
            raise
    
    def load_pipeline_state(self, file_path: str):
        """Load pipeline state from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Update statistics
            if "stats" in state_data:
                self.stats.update(state_data["stats"])
            
            # Update indexed documents
            if "indexed_documents" in state_data:
                self.indexed_documents = set(state_data["indexed_documents"])
            
            self.logger.info(f"Pipeline state loaded from {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error loading pipeline state: {str(e)}")
            raise
    
    def backup_system(self, backup_dir: str):
        """Create a complete backup of the RAG system."""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup vector store
            vector_backup_path = backup_path / f"vector_store_{timestamp}.json"
            self.vector_store.backup_collection(str(vector_backup_path))
            
            # Backup pipeline state
            state_backup_path = backup_path / f"pipeline_state_{timestamp}.json"
            self.save_pipeline_state(str(state_backup_path))
            
            # Create backup manifest
            manifest = {
                "timestamp": timestamp,
                "vector_store_backup": str(vector_backup_path),
                "pipeline_state_backup": str(state_backup_path),
                "config": self.config.to_dict(),
                "stats": self.get_pipeline_stats()
            }
            
            manifest_path = backup_path / f"backup_manifest_{timestamp}.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"System backup created in {backup_dir}")
            return str(manifest_path)
            
        except Exception as e:
            self.logger.error(f"Error creating system backup: {str(e)}")
            raise
    
    def restore_system(self, manifest_path: str):
        """Restore RAG system from backup."""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # Restore vector store
            if "vector_store_backup" in manifest:
                self.vector_store.restore_collection(manifest["vector_store_backup"])
            
            # Restore pipeline state
            if "pipeline_state_backup" in manifest:
                self.load_pipeline_state(manifest["pipeline_state_backup"])
            
            self.logger.info(f"System restored from backup: {manifest_path}")
            
        except Exception as e:
            self.logger.error(f"Error restoring system: {str(e)}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Perform system health check."""
        health_status = {
            "overall_status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Check initialization
            health_status["components"]["initialization"] = {
                "status": "healthy" if self.is_initialized else "unhealthy",
                "details": "Pipeline initialized" if self.is_initialized else "Pipeline not initialized"
            }
            
            # Check vector store
            try:
                vector_stats = self.vector_store.get_collection_stats()
                health_status["components"]["vector_store"] = {
                    "status": "healthy",
                    "details": f"Collection active with {vector_stats.get('total_documents', 0)} documents"
                }
            except Exception as e:
                health_status["components"]["vector_store"] = {
                    "status": "unhealthy",
                    "details": f"Vector store error: {str(e)}"
                }
                health_status["overall_status"] = "degraded"
            
            # Check embedding manager
            try:
                embedding_info = self.embedding_manager.get_model_info()
                health_status["components"]["embeddings"] = {
                    "status": "healthy",
                    "details": f"Model {embedding_info['model_name']} on {embedding_info['device']}"
                }
            except Exception as e:
                health_status["components"]["embeddings"] = {
                    "status": "unhealthy",
                    "details": f"Embeddings error: {str(e)}"
                }
                health_status["overall_status"] = "degraded"
            
            # Check retriever
            try:
                retrieval_stats = self.retriever.get_retrieval_stats()
                health_status["components"]["retriever"] = {
                    "status": "healthy",
                    "details": f"Processed {retrieval_stats['total_queries']} queries"
                }
            except Exception as e:
                health_status["components"]["retriever"] = {
                    "status": "unhealthy",
                    "details": f"Retriever error: {str(e)}"
                }
                health_status["overall_status"] = "degraded"
            
        except Exception as e:
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    def __del__(self):
        """Cleanup when pipeline is destroyed."""
        try:
            if hasattr(self, 'logger'):
                self.logger.info("RAG pipeline cleanup")
        except Exception:
            pass