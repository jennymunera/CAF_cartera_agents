import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from document_intelligence_processor import DocumentIntelligenceProcessor
from config.settings import settings
from agents.agents import (
    agente_auditorias,
    agente_productos,
    agente_desembolsos,
    agente_experto_auditorias,
    agente_experto_productos,
    agente_experto_desembolsos,
    agente_concatenador
)
from tasks.task import (
    task_auditorias,
    task_productos,
    task_desembolsos,
    task_experto_auditorias,
    task_experto_productos,
    task_experto_desembolsos,
    task_concatenador
)

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return "This is a sample PDF content for testing purposes. It contains multiple paragraphs and sections."

@pytest.fixture
def sample_pdf(temp_dir):
    """Create a sample PDF file for testing."""
    pdf_path = Path(temp_dir) / "sample.pdf"
    # Create a minimal PDF file
    pdf_path.write_bytes(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n174\n%%EOF')
    return pdf_path

@pytest.fixture
def mock_document_intelligence_processor():
    """Mock DocumentIntelligenceProcessor for testing."""
    processor = Mock(spec=DocumentIntelligenceProcessor)
    processor.process_single_document.return_value = {
        'success': True,
        'content': 'Sample document content',
        'metadata': {'pages': 1, 'file_size': 1024}
    }
    processor.process_project_documents.return_value = {
        'success': True,
        'content': 'Combined document content',
        'processed_files': ['doc1.pdf', 'doc2.pdf'],
        'failed_files': []
    }
    return processor

@pytest.fixture
def sample_project_structure(temp_dir):
    """Create a sample project structure for testing."""
    project_path = Path(temp_dir) / "test_project"
    project_path.mkdir()
    
    # Create sample PDF files (empty for testing)
    (project_path / "document1.pdf").touch()
    (project_path / "document2.pdf").touch()
    (project_path / "README.md").write_text("# Test Project\nThis is a test project.")
    
    return str(project_path)

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for testing."""
    return {
        'choices': [{
            'message': {
                'content': 'This is a mock response from the AI agent.'
            }
        }]
    }

@pytest.fixture
def mock_crew_agents():
    """Mock CrewAI agents for testing."""
    return {
        'agente_auditorias': Mock(),
        'agente_productos': Mock(),
        'agente_desembolsos': Mock(),
        'agente_experto_auditorias': Mock(),
        'agente_experto_productos': Mock(),
        'agente_experto_desembolsos': Mock(),
        'agente_concatenador': Mock()
    }

@pytest.fixture
def sample_analysis_results():
    """Sample analysis results for testing."""
    return {
        'audit_analysis': {
            'summary': 'Audit analysis summary',
            'findings': ['Finding 1', 'Finding 2', 'Finding 3'],
            'status': 'completed'
        },
        'product_analysis': {
            'products': ['Product 1', 'Product 2'],
            'recommendations': ['Rec 1', 'Rec 2'],
            'status': 'completed'
        },
        'disbursement_analysis': {
            'disbursements': ['Disbursement 1', 'Disbursement 2'],
            'total_amount': 100000,
            'status': 'completed'
        },
        'expert_audit_analysis': {
            'concept': 'Favorable',
            'observations': ['Obs 1', 'Obs 2']
        },
        'expert_product_analysis': {
            'concept': 'Favorable with reservations',
            'observations': ['Obs 1', 'Obs 2']
        },
        'expert_disbursement_analysis': {
            'concept': 'Favorable',
            'observations': ['Obs 1', 'Obs 2']
        },
        'business_analysis': {
            'business_value': 'High',
            'market_impact': 'Significant'
        }
    }

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_MODEL_NAME': 'gpt-4',
        'AZURE_OPENAI_API_KEY': 'test-azure-key',
        'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
        'AZURE_OPENAI_API_VERSION': '2024-02-15-preview',
        'AZURE_OPENAI_DEPLOYMENT_NAME': 'gpt-4'
    }):
        yield

@pytest.fixture
def mock_crewai_tasks():
    """Mock CrewAI tasks for testing."""
    mock_tasks = {
        'task_auditorias': Mock(),
        'task_productos': Mock(),
        'task_desembolsos': Mock(),
        'task_experto_auditorias': Mock(),
        'task_experto_productos': Mock(),
        'task_experto_desembolsos': Mock(),
        'task_concatenador': Mock()
    }
    
    # Mock task execution
    for task in mock_tasks.values():
        task.execute.return_value = "Mock task result"
    
    return mock_tasks

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    mock_settings = Mock()
    mock_settings.debug_mode = True
    mock_settings.verbose_output = True
    mock_settings.max_documents = 10
    mock_settings.max_file_size_mb = 50
    mock_settings.output_format = 'json'
    mock_settings.save_intermediate_results = True
    return mock_settings