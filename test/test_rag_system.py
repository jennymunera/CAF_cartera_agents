"""Comprehensive tests for RAG System.

Tests all RAG components:
- Configuration
- Document processing
- Embeddings
- Vector storage
- Retrieval
- Pipeline integration
- Observability
- Evaluation
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import RAG components
try:
    from rag.config import RAGConfig
    from rag.document_processor import DocumentProcessor, DocumentChunk, ProcessedDocument
    from rag.embeddings import EmbeddingManager
    from rag.vector_store import ChromaVectorStore
    from rag.retriever import HybridRetriever, RetrievalResponse
    from rag.rag_pipeline import RAGPipeline
    from rag.observability import RAGObservability, MetricsCollector, QueryMetrics
    from rag.evaluation import RAGEvaluator, RetrievalEvaluator, GenerationEvaluator
except ImportError as e:
    pytest.skip(f"RAG modules not available: {e}", allow_module_level=True)


class TestRAGConfig:
    """Test RAG configuration system."""
    
    def test_default_config_creation(self):
        """Test creating default RAG configuration."""
        config = RAGConfig()
        
        assert config.embeddings.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.chromadb.collection_name == "rag_documents"
        assert config.retrieval.k_final == 5
        assert config.azure_doc_intelligence.endpoint is None
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = RAGConfig()
        
        # Should not raise exception for valid config
        config.validate()
        
        # Test invalid k values
        config.retrieval.k_dense = 0
        with pytest.raises(ValueError, match="k_dense must be positive"):
            config.validate()
    
    def test_config_serialization(self):
        """Test configuration serialization to/from dict and JSON."""
        config = RAGConfig()
        
        # Test to_dict
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert "embeddings" in config_dict
        assert "chromadb" in config_dict
        
        # Test from_dict
        new_config = RAGConfig.from_dict(config_dict)
        assert new_config.embeddings.model_name == config.embeddings.model_name
        
        # Test JSON serialization
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config.save_to_json(f.name)
            loaded_config = RAGConfig.load_from_json(f.name)
            assert loaded_config.retrieval.k_final == config.retrieval.k_final
        
        os.unlink(f.name)
    
    def test_config_directory_creation(self):
        """Test automatic directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = RAGConfig()
            config.chromadb.persist_directory = os.path.join(temp_dir, "test_chroma")
            config.output_dir = os.path.join(temp_dir, "test_output")
            
            config._create_directories()
            
            assert os.path.exists(config.chromadb.persist_directory)
            assert os.path.exists(config.output_dir)


class TestDocumentProcessor:
    """Test document processing components."""
    
    @pytest.fixture
    def mock_azure_client(self):
        """Mock Azure Document Intelligence client."""
        with patch('rag.document_processor.DocumentIntelligenceClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            # Mock analyze_document response
            mock_result = Mock()
            mock_result.content = "Test document content with multiple paragraphs. This is the second sentence."
            mock_result.tables = []
            mock_result.key_value_pairs = []
            mock_result.paragraphs = [
                Mock(content="Test document content with multiple paragraphs."),
                Mock(content="This is the second sentence.")
            ]
            
            mock_instance.begin_analyze_document.return_value.result.return_value = mock_result
            
            yield mock_instance
    
    def test_document_chunk_creation(self):
        """Test DocumentChunk creation and properties."""
        chunk = DocumentChunk(
            chunk_id="test_chunk_1",
            content="This is test content for the chunk.",
            document_id="test_doc",
            metadata={"section": "introduction", "chunk_index": 0, "start_char": 0, "end_char": 35}
        )
        
        assert chunk.chunk_id == "test_chunk_1"
        assert len(chunk.content) == 35
        assert chunk.metadata["section"] == "introduction"
        assert chunk.token_count > 0  # Should estimate tokens
    
    def test_semantic_chunker(self):
        """Test semantic chunking functionality."""
        from rag.document_processor import SemanticChunker
        
        config = RAGConfig()
        chunker = SemanticChunker(config.chunking)
        
        # Test text chunking
        text = "This is the first paragraph. It has multiple sentences. \n\nThis is the second paragraph. It also has content."
        
        chunks = chunker.chunk_text(text, "test_doc")
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert all(chunk.document_id == "test_doc" for chunk in chunks)
        
        # Test that chunks don't exceed max size
        for chunk in chunks:
            assert chunk.token_count <= config.chunking.max_chunk_size
    
    @patch('rag.document_processor.DocumentIntelligenceClient')
    def test_azure_document_processor(self, mock_client_class):
        """Test Azure Document Intelligence integration."""
        from rag.document_processor import AzureDocumentProcessor
        
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_result = Mock()
        mock_result.content = "Test document content"
        mock_result.tables = []
        mock_result.key_value_pairs = []
        mock_result.paragraphs = [Mock(content="Test document content")]
        
        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document.return_value = mock_poller
        
        # Test processor
        config = RAGConfig()
        config.azure_doc_intelligence.endpoint = "https://test.cognitiveservices.azure.com/"
        config.azure_doc_intelligence.api_key = "test_key"
        
        processor = AzureDocumentProcessor(config.azure_doc_intelligence)
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"Test content")
            f.flush()
            
            result = processor.extract_content(f.name)
            
            assert result["content"] == "Test document content"
            assert "metadata" in result
        
        os.unlink(f.name)


class TestEmbeddingManager:
    """Test embedding management."""
    
    @patch('rag.embeddings.BGE_M3_Embeddings')
    def test_embedding_manager_initialization(self, mock_bge_model):
        """Test EmbeddingManager initialization."""
        # Mock the BGE_M3_Embeddings
        mock_model = Mock()
        mock_bge_model.return_value = mock_model
        
        config = RAGConfig()
        embedding_manager = EmbeddingManager(config.embeddings)
        
        assert embedding_manager.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert embedding_manager.device in ["cpu", "cuda", "mps"]
    
    @patch('rag.embeddings.BGE_M3_Embeddings')
    def test_embedding_generation(self, mock_bge_model):
        """Test embedding generation for documents."""
        # Mock the model and its methods
        mock_model = Mock()
        mock_bge_model.return_value = mock_model
        
        # Mock encode method to return dummy embeddings
        mock_model.encode.return_value = {
            'dense_vecs': [[0.1, 0.2, 0.3] for _ in range(2)]
        }
        
        config = RAGConfig()
        embedding_manager = EmbeddingManager(config.embeddings)
        
        texts = ["First document text", "Second document text"]
        embeddings = embedding_manager.embed_documents(texts)
        
        assert len(embeddings) == 2
        assert all('dense' in emb for emb in embeddings)
    
    @patch('rag.embeddings.BGE_M3_Embeddings')
    def test_embedding_caching(self, mock_bge_model):
        """Test embedding caching functionality."""
        mock_model = Mock()
        mock_bge_model.return_value = mock_model
        mock_model.encode.return_value = {
            'dense_vecs': [[0.1, 0.2, 0.3]]
        }
        
        config = RAGConfig()
        embedding_manager = EmbeddingManager(config.embeddings)
        
        text = "Test document for caching"
        
        # First call should hit the model
        embeddings1 = embedding_manager.embed_documents([text], use_cache=True)
        
        # Second call should use cache
        embeddings2 = embedding_manager.embed_documents([text], use_cache=True)
        
        # Should be called only once due to caching
        assert mock_model.encode.call_count == 1
        assert embeddings1 == embeddings2


class TestVectorStore:
    """Test ChromaDB vector store."""
    
    def test_vector_store_initialization(self):
        """Test ChromaVectorStore initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = RAGConfig()
            config.chromadb.persist_directory = temp_dir
            
            vector_store = ChromaVectorStore(config.chromadb)
            
            assert vector_store.collection_name == "rag_documents"
            assert vector_store.client is not None
    
    def test_document_operations(self):
        """Test adding, searching, and deleting documents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = RAGConfig()
            config.chromadb.persist_directory = temp_dir
            
            vector_store = ChromaVectorStore(config.chromadb)
            
            # Create test chunks
            chunks = [
                DocumentChunk(
                    chunk_id="chunk_1",
                    content="This is the first test document",
                    document_id="doc_1",
                    metadata={"chunk_index": 0, "start_char": 0, "end_char": 33}
                ),
                DocumentChunk(
                    chunk_id="chunk_2",
                    content="This is the second test document",
                    document_id="doc_1",
                    metadata={"chunk_index": 1, "start_char": 34, "end_char": 67}
                )
            ]
            
            # Mock embeddings
            embeddings = [
                {'dense': [0.1, 0.2, 0.3]},
                {'dense': [0.4, 0.5, 0.6]}
            ]
            
            # Add documents
            vector_store.add_documents(chunks, embeddings)
            
            # Search documents
            query_embedding = {'dense': [0.2, 0.3, 0.4]}
            results = vector_store.search(query_embedding, k=2)
            
            assert len(results) <= 2
            assert all('id' in result for result in results)
            assert all('score' in result for result in results)
    
    def test_collection_stats(self):
        """Test collection statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = RAGConfig()
            config.chromadb.persist_directory = temp_dir
            
            vector_store = ChromaVectorStore(config.chromadb)
            
            stats = vector_store.get_collection_stats()
            
            assert "total_documents" in stats
            assert "collection_name" in stats
            assert isinstance(stats["total_documents"], int)


class TestRAGPipeline:
    """Test complete RAG pipeline."""
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_pipeline_initialization(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test RAG pipeline initialization."""
        config = RAGConfig()
        
        # Mock all components
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        pipeline = RAGPipeline(config)
        
        assert pipeline.is_initialized
        assert pipeline.config == config
        assert "documents_processed" in pipeline.stats
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_document_indexing(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test document indexing workflow."""
        config = RAGConfig()
        
        # Setup mocks
        mock_processed_doc = ProcessedDocument(
            file_path="test.txt",
            document_id="test_doc",
            chunks=[
                DocumentChunk(
                    chunk_id="chunk_1",
                    content="Test content",
                    document_id="test_doc",
                    metadata={"chunk_index": 0, "start_char": 0, "end_char": 12}
                )
            ],
            processing_stats={"total_tokens": 10}
        )
        
        mock_doc_processor.return_value.process_multiple_documents.return_value = [mock_processed_doc]
        mock_embedding_manager.return_value.embed_documents.return_value = [
            {'dense': [0.1, 0.2, 0.3]}
        ]
        mock_vector_store.return_value.add_documents.return_value = None
        
        pipeline = RAGPipeline(config)
        
        # Test indexing
        result = pipeline.index_documents(["test.txt"])
        
        assert result["success"]
        assert result["documents_processed"] == 1
        assert result["chunks_indexed"] == 1
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_query_processing(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test query processing workflow."""
        config = RAGConfig()
        
        # Setup mocks
        mock_retrieval_response = RetrievalResponse(
            query="test query",
            results=[
                Mock(id="chunk_1", content="Test result", metadata={}, score=0.9, rank=1, retrieval_method="hybrid")
            ],
            total_candidates=1,
            retrieval_time=0.1,
            reranking_time=0.05,
            fusion_method="rrf"
        )
        
        mock_retriever.return_value.retrieve.return_value = mock_retrieval_response
        
        pipeline = RAGPipeline(config)
        
        # Test query
        result = pipeline.query("test query")
        
        assert result["success"]
        assert len(result["results"]) == 1
        assert "context" in result


class TestObservability:
    """Test observability system."""
    
    def test_metrics_collector_initialization(self):
        """Test MetricsCollector initialization."""
        collector = MetricsCollector(max_history=1000)
        
        assert len(collector.query_metrics) == 0
        assert len(collector.indexing_metrics) == 0
        assert collector.max_history == 1000
    
    def test_query_metrics_recording(self):
        """Test recording query metrics."""
        collector = MetricsCollector()
        
        metrics = QueryMetrics(
            query_id="test_query_1",
            query_text="test query",
            timestamp=datetime.now(),
            retrieval_time=0.1,
            reranking_time=0.05,
            total_time=0.2,
            results_count=5,
            k_requested=5,
            retrieval_method="hybrid",
            fusion_method="rrf",
            avg_score=0.8,
            top_score=0.95,
            metadata_filter=None,
            success=True
        )
        
        collector.record_query_metrics(metrics)
        
        assert len(collector.query_metrics) == 1
        assert collector.counters["total_queries"] == 1
        assert collector.counters["successful_queries"] == 1
    
    def test_query_statistics(self):
        """Test query statistics calculation."""
        collector = MetricsCollector()
        
        # Add multiple query metrics
        for i in range(5):
            metrics = QueryMetrics(
                query_id=f"query_{i}",
                query_text=f"test query {i}",
                timestamp=datetime.now(),
                retrieval_time=0.1 + i * 0.01,
                reranking_time=0.05,
                total_time=0.2 + i * 0.01,
                results_count=5,
                k_requested=5,
                retrieval_method="hybrid",
                fusion_method="rrf",
                avg_score=0.8,
                top_score=0.95,
                metadata_filter=None,
                success=True
            )
            collector.record_query_metrics(metrics)
        
        stats = collector.get_query_statistics()
        
        assert stats["total_queries"] == 5
        assert stats["success_rate"] == 1.0
        assert "query_times" in stats
        assert "avg" in stats["query_times"]
    
    def test_rag_observability_initialization(self):
        """Test RAGObservability system initialization."""
        observability = RAGObservability()
        
        assert observability.metrics_collector is not None
        assert hasattr(observability, 'logger')
    
    def test_performance_tracking(self):
        """Test performance tracking context manager."""
        observability = RAGObservability()
        
        with observability.track_operation("test_operation") as tracker:
            # Simulate some work
            import time
            time.sleep(0.01)
        
        duration = tracker.get_duration()
        assert duration is not None
        assert duration > 0


class TestEvaluation:
    """Test evaluation system."""
    
    def test_retrieval_evaluator(self):
        """Test retrieval evaluation metrics."""
        evaluator = RetrievalEvaluator()
        
        retrieved_docs = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant_docs = ["doc1", "doc3", "doc6", "doc7"]
        
        evaluation = evaluator.evaluate_retrieval(
            query_id="test_query",
            query_text="test query",
            retrieved_docs=retrieved_docs,
            relevant_docs=relevant_docs
        )
        
        assert evaluation.query_id == "test_query"
        assert 1 in evaluation.precision_at_k
        assert 5 in evaluation.precision_at_k
        assert evaluation.mrr > 0  # Should find doc1 at position 1
        assert 0 <= evaluation.precision_at_k[5] <= 1
    
    def test_generation_evaluator(self):
        """Test generation evaluation metrics."""
        evaluator = GenerationEvaluator()
        
        evaluation = evaluator.evaluate_generation(
            query_id="test_query",
            query_text="What is the capital of France?",
            generated_response="The capital of France is Paris, which is located in the northern part of the country.",
            retrieved_context=[
                "Paris is the capital and most populous city of France.",
                "France is a country in Western Europe."
            ]
        )
        
        assert evaluation.query_id == "test_query"
        assert 0 <= evaluation.faithfulness_score <= 1
        assert 0 <= evaluation.relevance_score <= 1
        assert 0 <= evaluation.coherence_score <= 1
        assert 0 <= evaluation.groundedness_score <= 1
    
    def test_rag_evaluator_end_to_end(self):
        """Test end-to-end RAG evaluation."""
        evaluator = RAGEvaluator()
        
        evaluation = evaluator.evaluate_end_to_end(
            query_id="test_query",
            query_text="What is machine learning?",
            retrieved_docs=["doc1", "doc2", "doc3"],
            relevant_docs=["doc1", "doc4"],
            generated_response="Machine learning is a subset of artificial intelligence that enables computers to learn.",
            retrieved_context=[
                "Machine learning is a method of data analysis.",
                "AI and machine learning are related fields."
            ]
        )
        
        assert evaluation.query_id == "test_query"
        assert hasattr(evaluation, 'retrieval_eval')
        assert hasattr(evaluation, 'generation_eval')
        assert 0 <= evaluation.overall_score <= 1
    
    def test_evaluation_report_generation(self):
        """Test evaluation report generation."""
        evaluator = RAGEvaluator()
        
        # Add some test evaluations
        for i in range(3):
            evaluator.evaluate_end_to_end(
                query_id=f"query_{i}",
                query_text=f"Test query {i}",
                retrieved_docs=["doc1", "doc2"],
                relevant_docs=["doc1"],
                generated_response="Test response",
                retrieved_context=["Test context"]
            )
        
        report = evaluator.generate_evaluation_report()
        
        assert "RAG System Evaluation Report" in report
        assert "Total Evaluations: 3" in report
        assert "Overall Performance:" in report


class TestIntegration:
    """Integration tests for complete RAG system."""
    
    @pytest.mark.integration
    def test_full_rag_workflow_mock(self):
        """Test complete RAG workflow with mocked components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup configuration
            config = RAGConfig()
            config.chromadb.persist_directory = temp_dir
            config.output_dir = temp_dir
            
            # This would be a full integration test with real components
            # For now, we'll test that the configuration and setup work
            config._validate_config()
            config._create_directories()
            
            assert os.path.exists(config.chromadb.persist_directory)
            assert os.path.exists(config.output_dir)
    
    def test_config_integration_with_components(self):
        """Test that configuration integrates properly with all components."""
        config = RAGConfig()
        
        # Test that config can be used to initialize all components
        # (with mocked dependencies)
        
        with patch('rag.embeddings.BGE_M3_Embeddings'):
            embedding_manager = EmbeddingManager(config.embeddings)
            assert embedding_manager.config.model_name == config.embeddings.model_name
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config.chromadb.persist_directory = temp_dir
            vector_store = ChromaVectorStore(config.chromadb)
            assert vector_store.collection_name == config.chromadb.collection_name


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])