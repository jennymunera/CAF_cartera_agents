import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from document_intelligence_processor import DocumentIntelligenceProcessor, process_documents


class TestDocumentIntelligenceProcessor:
    """Test cases for DocumentIntelligenceProcessor class."""
    
    @pytest.mark.unit
    def test_init(self):
        """Test DocumentIntelligenceProcessor initialization."""
        with patch('document_intelligence_processor.DocumentIntelligenceClient'):
            processor = DocumentIntelligenceProcessor(
                endpoint="https://test.cognitiveservices.azure.com/",
                api_key="test_key"
            )
            assert processor is not None
            assert hasattr(processor, 'process_single_document')
            assert hasattr(processor, 'process_project_documents')
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceClient')
    def test_process_single_document_success(self, mock_client_class):
        """Test successful document processing."""
        # Setup mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the analyze_document response
        mock_result = Mock()
        mock_result.content = "Test document content"
        mock_result.tables = []
        mock_result.key_value_pairs = []
        mock_result.paragraphs = [Mock(content="Test paragraph")]
        
        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document.return_value = mock_poller
        
        processor = DocumentIntelligenceProcessor(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test_key"
        )
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(b'%PDF-1.4 fake pdf content')
            temp_path = Path(temp_file.name)
        
        try:
            result = processor.process_single_document(temp_path)
            
            assert 'filename' in result
            assert 'content' in result
            assert 'json_data' in result
            assert 'metadata' in result
            assert result['metadata']['processing_status'] == 'success'
            assert len(result['content']) > 0
        finally:
            temp_path.unlink()
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceClient')
    def test_process_single_document_failure(self, mock_client_class):
        """Test handling of document processing failure."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.begin_analyze_document.side_effect = Exception("Processing failed")
        
        processor = DocumentIntelligenceProcessor(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test_key"
        )
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(b'%PDF-1.4 fake pdf content')
            temp_path = Path(temp_file.name)
        
        try:
            result = processor.process_single_document(temp_path)
            
            assert 'filename' in result
            assert 'content' in result
            assert 'metadata' in result
            assert result['metadata']['processing_status'] == 'error'
            assert result['content'] == ""
            assert 'error_message' in result['metadata']
        finally:
            temp_path.unlink()
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceClient')
    def test_process_single_document_nonexistent_file(self, mock_client_class):
        """Test handling of nonexistent file."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        processor = DocumentIntelligenceProcessor(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test_key"
        )
        
        nonexistent_path = Path('/path/to/nonexistent/file.pdf')
        result = processor.process_single_document(nonexistent_path)
        
        assert 'filename' in result
        assert 'content' in result
        assert 'metadata' in result
        assert result['metadata']['processing_status'] == 'error'
        assert result['content'] == ""
        assert 'error_message' in result['metadata']
        assert result['filename'] == 'file.pdf'
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceProcessor.process_single_document')
    def test_process_project_documents_success(self, mock_process_single, sample_project_structure):
        """Test successful processing of project documents."""
        # Setup mock
        mock_process_single.return_value = {
            'filename': 'test.pdf',
            'content': 'Document content',
            'json_data': {'test': 'data'},
            'metadata': {'processing_status': 'success'}
        }
        
        with patch('document_intelligence_processor.DocumentIntelligenceClient'):
            processor = DocumentIntelligenceProcessor(
                endpoint="https://test.cognitiveservices.azure.com/",
                api_key="test_key",
                input_docs_path=str(sample_project_structure['input_dir']),
                output_docs_path=str(sample_project_structure['output_dir'])
            )
            
            result = processor.process_project_documents('test_project')
            
            assert 'project_name' in result
            assert 'documents' in result
            assert 'concatenated_content' in result
            assert 'metadata' in result
            assert result['project_name'] == 'test_project'
            assert result['metadata']['processing_status'] == 'completed'
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceClient')
    def test_process_project_documents_nonexistent_project(self, mock_client_class):
        """Test handling of nonexistent project."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        processor = DocumentIntelligenceProcessor(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test_key"
        )
        
        result = processor.process_project_documents('nonexistent_project')
        
        assert result['project_name'] == 'nonexistent_project'
        assert result['metadata']['processing_status'] == 'project_not_found'
        assert result['metadata']['total_documents'] == 0
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceProcessor.process_single_document')
    def test_process_project_documents_mixed_results(self, mock_process_single, sample_project_structure):
        """Test processing with mixed success/failure results."""
        # Setup mock to return alternating success/failure
        mock_process_single.side_effect = [
            {
                'filename': 'success.pdf',
                'content': 'Success content',
                'json_data': {'test': 'data'},
                'metadata': {'processing_status': 'success'}
            },
            {
                'filename': 'failure.pdf',
                'content': '',
                'json_data': {},
                'metadata': {'processing_status': 'error', 'error_message': 'Test error'}
            }
        ]
        
        with patch('document_intelligence_processor.DocumentIntelligenceClient'):
            processor = DocumentIntelligenceProcessor(
                endpoint="https://test.cognitiveservices.azure.com/",
                api_key="test_key",
                input_docs_path=str(sample_project_structure['input_dir']),
                output_docs_path=str(sample_project_structure['output_dir'])
            )
            
            result = processor.process_project_documents('test_project')
            
            assert result['metadata']['successful_documents'] == 1
            assert result['metadata']['failed_documents'] == 1
            assert result['metadata']['total_documents'] == 2


class TestProcessDocumentsFunction:
    """Test cases for the process_documents function."""
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.list_available_projects')
    def test_process_documents_list_projects(self, mock_list_projects):
        """Test listing available projects."""
        mock_list_projects.return_value = ['project1', 'project2']
        
        result = process_documents(None, processor_type="document_intelligence")
        
        assert 'available_projects' in result
        assert result['available_projects'] == ['project1', 'project2']
    
    @pytest.mark.unit
    @patch('document_intelligence_processor.DocumentIntelligenceProcessor')
    def test_process_documents_with_project(self, mock_processor_class):
        """Test processing a specific project."""
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        mock_processor.process_project_documents.return_value = {
            'project_name': 'test_project',
            'metadata': {'processing_status': 'completed'}
        }
        
        result = process_documents('test_project', processor_type="document_intelligence")
        
        assert result['project_name'] == 'test_project'
        assert result['metadata']['processing_status'] == 'completed'
        mock_processor.process_project_documents.assert_called_once_with('test_project')


class TestDocumentIntelligenceIntegration:
    """Integration tests for Document Intelligence processor."""
    
    @pytest.mark.integration
    @patch('document_intelligence_processor.DocumentIntelligenceClient')
    def test_full_workflow_with_mock_data(self, mock_client_class, temp_dir):
        """Test full workflow with mocked Azure Document Intelligence."""
        # Setup mock client with realistic response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_result = Mock()
        mock_result.content = "This is test document content extracted by Document Intelligence."
        mock_result.tables = []
        mock_result.key_value_pairs = []
        mock_result.paragraphs = [Mock(content="Test paragraph content")]
        
        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document.return_value = mock_poller
        
        # Create test project structure
        input_dir = temp_dir / "input_docs" / "test_project"
        input_dir.mkdir(parents=True)
        
        # Create a test PDF file
        test_pdf = input_dir / "test.pdf"
        test_pdf.write_bytes(b'%PDF-1.4 fake pdf content')
        
        processor = DocumentIntelligenceProcessor(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test_key",
            input_docs_path=str(temp_dir / "input_docs"),
            output_docs_path=str(temp_dir / "output_docs")
        )
        
        result = processor.process_project_documents('test_project')
        
        assert result['metadata']['processing_status'] == 'completed'
        assert result['metadata']['successful_documents'] > 0
        assert len(result['concatenated_content']) > 0
    
    @pytest.mark.integration
    @patch('document_intelligence_processor.DocumentIntelligenceClient')
    def test_error_handling_and_recovery(self, mock_client_class, temp_dir):
        """Test error handling in integration scenario."""
        # Setup mock to simulate service error
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.begin_analyze_document.side_effect = Exception("Service unavailable")
        
        # Create test project structure
        input_dir = temp_dir / "input_docs" / "test_project"
        input_dir.mkdir(parents=True)
        
        test_pdf = input_dir / "test.pdf"
        test_pdf.write_bytes(b'%PDF-1.4 fake pdf content')
        
        processor = DocumentIntelligenceProcessor(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test_key",
            input_docs_path=str(temp_dir / "input_docs"),
            output_docs_path=str(temp_dir / "output_docs")
        )
        
        result = processor.process_project_documents('test_project')
        
        # Should handle errors gracefully
        assert result['metadata']['processing_status'] == 'completed'
        assert result['metadata']['failed_documents'] > 0
        assert result['metadata']['successful_documents'] == 0
    
    @pytest.mark.integration
    def test_content_validation(self, sample_pdf_content):
        """Test content validation and structure."""
        # This test validates the structure of processed content
        # without requiring actual Azure Document Intelligence service
        
        expected_structure = {
            'filename': str,
            'content': str,
            'json_data': dict,
            'metadata': dict
        }
        
        # Validate that sample content matches expected structure
        for key, expected_type in expected_structure.items():
            assert key in sample_pdf_content
            assert isinstance(sample_pdf_content[key], expected_type)
        
        # Validate metadata structure
        assert 'processing_status' in sample_pdf_content['metadata']
        assert isinstance(sample_pdf_content['metadata'], dict)