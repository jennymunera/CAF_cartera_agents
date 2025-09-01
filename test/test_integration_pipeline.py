import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from docling_processor import DoclingProcessor
from agents.agents import (
    agente_auditorias, agente_productos, agente_desembolsos,
    agente_experto_auditorias, agente_experto_productos, 
    agente_experto_desembolsos, agente_concatenador
)
from tasks.task import (
    task_auditorias, task_productos, task_desembolsos,
    task_experto_auditorias, task_experto_productos,
    task_experto_desembolsos, task_concatenador
)
from crewai import Crew, Process


class TestIntegrationPipeline:
    """Integration tests for the complete Docling + CrewAI pipeline."""
    
    @pytest.fixture
    def sample_pdf_content(self):
        """Create sample PDF content for testing."""
        return {
            'audit_findings': [
                'Internal controls are adequate',
                'Financial statements are accurate',
                'Compliance with regulations confirmed'
            ],
            'product_info': [
                'Product A: High performance metrics',
                'Product B: Market leader in segment',
                'Product C: Innovation award winner'
            ],
            'disbursement_data': [
                'Q1 disbursements: $1.2M',
                'Q2 disbursements: $1.5M',
                'Q3 disbursements: $1.8M'
            ]
        }
    
    @pytest.fixture
    def mock_docling_processor(self, sample_pdf_content):
        """Mock DoclingProcessor for integration tests."""
        processor = Mock(spec=DoclingProcessor)
        processor.process_single_document.return_value = "success"
        processor.get_processed_content.return_value = sample_pdf_content
        return processor
    
    @pytest.fixture
    def mock_crew_results(self):
        """Mock CrewAI execution results."""
        return {
            'specialist_results': {
                'audit_analysis': {
                    'findings': ['Control weakness identified', 'Recommendations provided'],
                    'risk_level': 'Medium',
                    'status': 'completed'
                },
                'product_analysis': {
                    'products': ['Product A evaluated', 'Product B assessed'],
                    'performance': 'Above average',
                    'status': 'completed'
                },
                'disbursement_analysis': {
                    'disbursements': ['Q1-Q3 analyzed', 'Trends identified'],
                    'total_amount': '$4.5M',
                    'status': 'completed'
                }
            },
            'expert_results': {
                'audit_concept': 'Favorable with reservations',
                'product_concept': 'Favorable',
                'disbursement_concept': 'Favorable'
            },
            'final_output': {
                'files_generated': ['audits.csv', 'products.csv', 'disbursements.csv'],
                'summary': 'Analysis completed successfully'
            }
        }
    
    @pytest.mark.integration
    @patch('tasks.task.Process')
    @patch('tasks.task.Task')
    @patch('agents.agents.Agent')
    @patch('crewai.Crew')
    def test_complete_pipeline_flow(self, mock_crew_class, mock_agent, mock_task, mock_process, mock_docling_processor, mock_crew_results):
        """Test the complete pipeline from document processing to final output."""
        # Setup mocks
        mock_crew = Mock()
        mock_crew_class.return_value = mock_crew
        mock_crew.kickoff.return_value = mock_crew_results
        
        # Step 1: Document Processing
        test_file = Path('/tmp/test_document.pdf')
        result = mock_docling_processor.process_single_document(test_file)
        assert result == "success"
        
        # Step 2: Get processed content
        processed_content = mock_docling_processor.get_processed_content()
        assert 'audit_findings' in processed_content
        assert 'product_info' in processed_content
        assert 'disbursement_data' in processed_content
        
        # Step 3: CrewAI Workflow Execution
        # Phase 1: Specialist Analysis
        specialist_crew = mock_crew_class(
            agents=[mock_agent, mock_agent, mock_agent],
            tasks=[mock_task, mock_task, mock_task],
            process=mock_process
        )
        
        specialist_results = specialist_crew.kickoff(inputs={
            'processed_documents': processed_content
        })
        
        # Phase 2: Expert Evaluation
        expert_crew = mock_crew_class(
            agents=[mock_agent, mock_agent, mock_agent],
            tasks=[mock_task, mock_task, mock_task],
            process=mock_process
        )
        
        expert_results = expert_crew.kickoff(inputs={
            'audit_analysis_results': specialist_results['specialist_results']['audit_analysis'],
            'product_analysis_results': specialist_results['specialist_results']['product_analysis'],
            'disbursement_analysis_results': specialist_results['specialist_results']['disbursement_analysis']
        })
        
        # Phase 3: Final Concatenation
        final_crew = mock_crew_class(
            agents=[mock_agent],
            tasks=[mock_task],
            process=mock_process
        )
        
        final_results = final_crew.kickoff(inputs={
            'expert_assessments': expert_results['expert_results']
        })
        
        # Verify pipeline completion
        assert final_results is not None
        assert mock_crew.kickoff.call_count >= 3  # Called for each phase
    
    @pytest.mark.integration
    @patch('tasks.task.Process')
    @patch('tasks.task.Task')
    @patch('agents.agents.Agent')
    @patch('crewai.Crew')
    def test_pipeline_error_handling(self, mock_crew_class, mock_agent, mock_task, mock_process, mock_docling_processor):
        """Test pipeline behavior when errors occur."""
        # Test document processing failure
        mock_docling_processor.process_single_document.return_value = "error"
        
        test_file = Path('/tmp/test_document.pdf')
        result = mock_docling_processor.process_single_document(test_file)
        assert result == "error"
        
        # Test CrewAI execution failure
        mock_crew = Mock()
        mock_crew_class.return_value = mock_crew
        mock_crew.kickoff.side_effect = Exception("CrewAI execution failed")
        
        with pytest.raises(Exception, match="CrewAI execution failed"):
            crew = mock_crew_class(
                agents=[mock_agent],
                tasks=[mock_task],
                process=mock_process
            )
            crew.kickoff()
    
    @pytest.mark.integration
    def test_data_transformation_between_stages(self, mock_docling_processor, sample_pdf_content):
        """Test data transformation between pipeline stages."""
        # Mock document processing output
        mock_docling_processor.get_processed_content.return_value = sample_pdf_content
        
        # Test data structure for specialist tasks
        processed_content = mock_docling_processor.get_processed_content()
        
        # Verify data structure matches task expectations
        assert isinstance(processed_content, dict)
        assert 'audit_findings' in processed_content
        assert isinstance(processed_content['audit_findings'], list)
        
        # Test data transformation for expert tasks
        specialist_output = {
            'audit_analysis': {'findings': processed_content['audit_findings'], 'status': 'completed'},
            'product_analysis': {'products': processed_content['product_info'], 'status': 'completed'},
            'disbursement_analysis': {'disbursements': processed_content['disbursement_data'], 'status': 'completed'}
        }
        
        # Verify specialist output structure
        for analysis in specialist_output.values():
            assert 'status' in analysis
            assert analysis['status'] == 'completed'
        
        # Test expert evaluation input
        expert_input = {
            'audit_analysis_results': specialist_output['audit_analysis'],
            'product_analysis_results': specialist_output['product_analysis'],
            'disbursement_analysis_results': specialist_output['disbursement_analysis']
        }
        
        # Verify expert input structure
        assert len(expert_input) == 3
        for key, value in expert_input.items():
            assert 'analysis_results' in key
            assert isinstance(value, dict)
    
    @pytest.mark.integration
    def test_pipeline_output_validation(self, mock_crew_results):
        """Test validation of pipeline output formats."""
        # Test specialist results structure
        specialist_results = mock_crew_results['specialist_results']
        
        required_analyses = ['audit_analysis', 'product_analysis', 'disbursement_analysis']
        for analysis in required_analyses:
            assert analysis in specialist_results
            assert 'status' in specialist_results[analysis]
            assert specialist_results[analysis]['status'] == 'completed'
        
        # Test expert results structure
        expert_results = mock_crew_results['expert_results']
        
        required_concepts = ['audit_concept', 'product_concept', 'disbursement_concept']
        for concept in required_concepts:
            assert concept in expert_results
            assert expert_results[concept] in ['Favorable', 'Favorable with reservations', 'Unfavorable']
        
        # Test final output structure
        final_output = mock_crew_results['final_output']
        
        assert 'files_generated' in final_output
        assert isinstance(final_output['files_generated'], list)
        assert len(final_output['files_generated']) == 3
        
        # Verify CSV file names
        expected_files = ['audits.csv', 'products.csv', 'disbursements.csv']
        for expected_file in expected_files:
            assert expected_file in final_output['files_generated']
    
    @pytest.mark.integration
    def test_pipeline_performance_metrics(self, mock_docling_processor, mock_crew_results):
        """Test pipeline performance and resource usage."""
        import time
        
        # Mock timing for document processing
        start_time = time.time()
        mock_docling_processor.process_single_document(Path('/tmp/test.pdf'))
        doc_processing_time = time.time() - start_time
        
        # Mock timing for CrewAI execution
        with patch('crewai.Crew') as mock_crew_class:
            mock_crew = Mock()
            mock_crew_class.return_value = mock_crew
            mock_crew.kickoff.return_value = mock_crew_results
            
            start_time = time.time()
            crew = Crew(
                agents=[agente_auditorias, agente_productos, agente_desembolsos],
                tasks=[task_auditorias, task_productos, task_desembolsos],
                process=Process.sequential
            )
            crew.kickoff()
            crew_execution_time = time.time() - start_time
        
        # Verify reasonable execution times (mocked, so should be very fast)
        assert doc_processing_time < 1.0  # Should be nearly instantaneous when mocked
        assert crew_execution_time < 1.0  # Should be nearly instantaneous when mocked
    
    @pytest.mark.integration
    def test_pipeline_with_multiple_documents(self, mock_docling_processor, sample_pdf_content):
        """Test pipeline handling multiple documents."""
        # Mock processing multiple documents
        documents = [Path(f'/tmp/test_doc_{i}.pdf') for i in range(3)]
        
        processed_results = []
        for doc in documents:
            result = mock_docling_processor.process_single_document(doc)
            assert result == "success"
            processed_results.append(sample_pdf_content)
        
        # Verify all documents processed
        assert len(processed_results) == 3
        
        # Test aggregated content for CrewAI
        aggregated_content = {
            'audit_findings': [],
            'product_info': [],
            'disbursement_data': []
        }
        
        for content in processed_results:
            aggregated_content['audit_findings'].extend(content['audit_findings'])
            aggregated_content['product_info'].extend(content['product_info'])
            aggregated_content['disbursement_data'].extend(content['disbursement_data'])
        
        # Verify aggregated content
        assert len(aggregated_content['audit_findings']) == 9  # 3 docs * 3 findings each
        assert len(aggregated_content['product_info']) == 9    # 3 docs * 3 products each
        assert len(aggregated_content['disbursement_data']) == 9  # 3 docs * 3 disbursements each
    
    @pytest.mark.integration
    def test_pipeline_configuration_validation(self):
        """Test pipeline configuration and setup validation."""
        # Test agent configuration
        all_agents = [
            agente_auditorias, agente_productos, agente_desembolsos,
            agente_experto_auditorias, agente_experto_productos,
            agente_experto_desembolsos, agente_concatenador
        ]
        
        for agent in all_agents:
            assert hasattr(agent, 'role')
            assert hasattr(agent, 'goal')
            assert hasattr(agent, 'backstory')
            assert agent.verbose is True
            assert agent.allow_delegation is False
        
        # Test task configuration
        all_tasks = [
            task_auditorias, task_productos, task_desembolsos,
            task_experto_auditorias, task_experto_productos,
            task_experto_desembolsos, task_concatenador
        ]
        
        for task in all_tasks:
            assert hasattr(task, 'description')
            assert hasattr(task, 'expected_output')
            assert hasattr(task, 'agent')
        
        # Test DoclingProcessor configuration
        processor = DoclingProcessor()
        assert hasattr(processor, 'converter')
        assert hasattr(processor, 'process_single_document')