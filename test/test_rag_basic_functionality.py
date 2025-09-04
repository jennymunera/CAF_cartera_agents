"""Tests básicos para verificar la funcionalidad RAG sin dependencias externas."""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Import RAG components
try:
    from rag.config import RAGConfig
    from rag.rag_pipeline import RAGPipeline
    from agents.agents import RAGTool
except ImportError as e:
    pytest.skip(f"RAG modules not available: {e}", allow_module_level=True)


class TestRAGBasicFunctionality:
    """Tests básicos para verificar que el sistema RAG está correctamente implementado."""
    
    def test_rag_config_creation(self):
        """Test que RAGConfig se puede crear correctamente."""
        config = RAGConfig()
        assert config is not None
        assert hasattr(config, 'chromadb')
        assert hasattr(config, 'embeddings')
        assert hasattr(config, 'azure_di')
        assert hasattr(config, 'chunking')
        assert hasattr(config, 'retrieval')
    
    def test_rag_tool_creation(self):
        """Test que RAGTool se puede crear sin errores."""
        rag_tool = RAGTool()
        assert rag_tool is not None
        assert rag_tool.name == "rag_search"
        assert "busca información relevante" in rag_tool.description.lower()
    
    def test_rag_tool_without_pipeline(self):
        """Test que RAGTool maneja correctamente la ausencia de pipeline."""
        rag_tool = RAGTool()
        result = rag_tool._run("test query")
        assert "RAG system not available" in result
    
    @patch('rag.rag_pipeline.RAGPipeline')
    def test_rag_tool_with_mock_pipeline(self, mock_pipeline_class):
        """Test que RAGTool funciona con un pipeline mock."""
        # Setup mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.query.return_value = [
            {
                'content': 'Test content',
                'score': 0.95,
                'metadata': {
                    'source_file': 'test.pdf',
                    'document_type': 'audit',
                    'page_number': 1
                }
            }
        ]
        
        # Create RAGTool with mock pipeline
        rag_tool = RAGTool(rag_pipeline=mock_pipeline)
        
        # Test query
        result = rag_tool._run("test query")
        
        # Verify pipeline was called
        mock_pipeline.query.assert_called_once()
        
        # Verify result format
        assert "test content" in result.lower()
        assert "0.950" in result  # Score formatting
        assert "test.pdf" in result
    
    def test_rag_config_from_dict(self):
        """Test que RAGConfig se puede crear desde un diccionario."""
        config_dict = {
            "chromadb": {
                "persist_directory": "./test_chroma_db",
                "collection_name": "test_collection"
            },
            "embeddings": {
                "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                "device": "cpu"
            }
        }
        
        config = RAGConfig.from_dict(config_dict)
        assert config.chromadb.persist_directory == "./test_chroma_db"
        assert config.embeddings.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    
    def test_rag_config_json_serialization(self):
        """Test que RAGConfig se puede serializar y deserializar desde JSON."""
        config = RAGConfig()
        
        # Test to_dict
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert "chromadb" in config_dict
        assert "embeddings" in config_dict
        assert "azure_di" in config_dict
        
        # Test JSON serialization
        json_str = json.dumps(config_dict)
        assert isinstance(json_str, str)
        
        # Test deserialization
        loaded_dict = json.loads(json_str)
        new_config = RAGConfig.from_dict(loaded_dict)
        assert new_config.chromadb.persist_directory == config.chromadb.persist_directory
        assert new_config.embeddings.model_name == config.embeddings.model_name
    
    def test_rag_pipeline_creation_with_config(self):
        """Test que RAGPipeline se puede crear con configuración."""
        config = RAGConfig()
        
        # Mock all dependencies
        with patch('rag.rag_pipeline.DocumentProcessor'), \
             patch('rag.rag_pipeline.EmbeddingManager'), \
             patch('rag.rag_pipeline.ChromaVectorStore'), \
             patch('rag.rag_pipeline.HybridRetriever'):
            
            pipeline = RAGPipeline(config)
            assert pipeline is not None
            assert pipeline.config == config
    
    def test_integration_components_exist(self):
        """Test que todos los componentes necesarios para la integración existen."""
        # Verify RAG modules exist
        from rag import config, rag_pipeline, document_processor, embeddings, vector_store, retriever
        
        # Verify key classes exist
        assert hasattr(config, 'RAGConfig')
        assert hasattr(rag_pipeline, 'RAGPipeline')
        assert hasattr(document_processor, 'DocumentProcessor')
        assert hasattr(embeddings, 'EmbeddingManager')
        assert hasattr(vector_store, 'ChromaVectorStore')
        assert hasattr(retriever, 'HybridRetriever')
        
        # Verify agents integration
        from agents.agents import RAGTool
        assert RAGTool is not None
    
    def test_rag_tool_error_handling(self):
        """Test que RAGTool maneja errores correctamente."""
        # Create mock pipeline that raises exception
        mock_pipeline = Mock()
        mock_pipeline.query.side_effect = Exception("Test error")
        
        rag_tool = RAGTool(rag_pipeline=mock_pipeline)
        result = rag_tool._run("test query")
        
        assert "Error en búsqueda RAG" in result
        assert "Test error" in result