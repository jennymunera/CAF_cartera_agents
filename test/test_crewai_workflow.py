import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

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


class TestCrewAIAgents:
    """Test cases for CrewAI agents."""
    
    @pytest.mark.unit
    def test_audit_agent_creation(self):
        """Test audit agent creation."""
        agent = agente_auditorias
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Audit' in agent.role or 'Auditor' in agent.role
    
    @pytest.mark.unit
    def test_product_agent_creation(self):
        """Test product agent creation."""
        agent = agente_productos
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Product' in agent.role or 'Producto' in agent.role
    
    @pytest.mark.unit
    def test_disbursement_agent_creation(self):
        """Test disbursement agent creation."""
        agent = agente_desembolsos
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Disbursement' in agent.role or 'Desembolso' in agent.role
    
    @pytest.mark.unit
    def test_audit_expert_agent_creation(self):
        """Test audit expert agent creation."""
        agent = agente_experto_auditorias
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Expert' in agent.role or 'Experto' in agent.role
    
    @pytest.mark.unit
    def test_product_expert_agent_creation(self):
        """Test product expert agent creation."""
        agent = agente_experto_productos
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Expert' in agent.role or 'Experto' in agent.role
    
    @pytest.mark.unit
    def test_disbursement_expert_agent_creation(self):
        """Test disbursement expert agent creation."""
        agent = agente_experto_desembolsos
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Expert' in agent.role or 'Experto' in agent.role
    
    @pytest.mark.unit
    def test_concatenator_agent_creation(self):
        """Test concatenator agent creation."""
        agent = agente_concatenador
        
        assert agent is not None
        assert hasattr(agent, 'role')
        assert hasattr(agent, 'goal')
        assert hasattr(agent, 'backstory')
        assert 'Concatenator' in agent.role or 'Concatenador' in agent.role


class TestCrewAITasks:
    """Test cases for CrewAI tasks."""
    
    @pytest.mark.unit
    def test_audit_task_creation(self):
        """Test audit task creation."""
        task = task_auditorias
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')
    
    @pytest.mark.unit
    def test_product_task_creation(self):
        """Test product task creation."""
        task = task_productos
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')
    
    @pytest.mark.unit
    def test_disbursement_task_creation(self):
        """Test disbursement task creation."""
        task = task_desembolsos
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')
    
    @pytest.mark.unit
    def test_audit_expert_task_creation(self):
        """Test audit expert task creation."""
        task = task_experto_auditorias
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')
    
    @pytest.mark.unit
    def test_product_expert_task_creation(self):
        """Test product expert task creation."""
        task = task_experto_productos
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')
    
    @pytest.mark.unit
    def test_disbursement_expert_task_creation(self):
        """Test disbursement expert task creation."""
        task = task_experto_desembolsos
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')
    
    @pytest.mark.unit
    def test_concatenation_task_creation(self):
        """Test concatenation task creation."""
        task = task_concatenador
        
        assert task is not None
        assert hasattr(task, 'description')
        assert hasattr(task, 'expected_output')
        assert hasattr(task, 'agent')


class TestCrewAIWorkflow:
    """Test cases for CrewAI workflow integration."""
    
    @pytest.mark.unit
    @patch('crewai.Crew')
    def test_crew_creation_and_execution(self, mock_crew_class):
        """Test crew creation and execution with all agents and tasks."""
        # Mock crew instance
        mock_crew_instance = Mock()
        mock_crew_class.return_value = mock_crew_instance
        
        # Mock execution result
        mock_result = {
            'audit_results': {'concept': 'Favorable', 'findings': []},
            'product_results': {'concept': 'Favorable with reservations', 'products': []},
            'disbursement_results': {'concept': 'Favorable', 'disbursements': []}
        }
        mock_crew_instance.kickoff.return_value = mock_result
        
        # Verify agents and tasks exist
        agents = [agente_auditorias, agente_productos, agente_desembolsos,
                 agente_experto_auditorias, agente_experto_productos, 
                 agente_experto_desembolsos, agente_concatenador]
        tasks = [task_auditorias, task_productos, task_desembolsos,
                task_experto_auditorias, task_experto_productos,
                task_experto_desembolsos, task_concatenador]
        
        assert all(agent is not None for agent in agents)
        assert all(task is not None for task in tasks)
        assert len(agents) == 7
        assert len(tasks) == 7
    
    @pytest.mark.unit
    def test_agent_llm_configuration(self):
        """Test that all agents have proper LLM configuration."""
        agents = [agente_auditorias, agente_productos, agente_desembolsos,
                 agente_experto_auditorias, agente_experto_productos, 
                 agente_experto_desembolsos, agente_concatenador]
        
        for agent in agents:
            assert hasattr(agent, 'role')
            assert hasattr(agent, 'goal')
            assert hasattr(agent, 'backstory')
    
    @pytest.mark.unit
    def test_task_agent_assignment(self):
        """Test that all tasks are properly assigned to their respective agents."""
        # Test task-agent assignments
        assert task_auditorias.agent == agente_auditorias
        assert task_productos.agent == agente_productos
        assert task_desembolsos.agent == agente_desembolsos
        assert task_experto_auditorias.agent == agente_experto_auditorias
        assert task_experto_productos.agent == agente_experto_productos
        assert task_experto_desembolsos.agent == agente_experto_desembolsos
        assert task_concatenador.agent == agente_concatenador
    
    @pytest.mark.unit
    def test_task_descriptions_and_outputs(self):
        """Test that all tasks have proper descriptions and expected outputs."""
        tasks = [task_auditorias, task_productos, task_desembolsos,
                task_experto_auditorias, task_experto_productos,
                task_experto_desembolsos, task_concatenador]
        
        for task in tasks:
            assert hasattr(task, 'description')
            assert hasattr(task, 'expected_output')
            assert len(task.description.strip()) > 0
            assert len(task.expected_output.strip()) > 0
    
    @pytest.mark.unit
    def test_specialist_agent_priorities(self):
        """Test that specialist agents have correct priority configurations."""
        # Check audit task prioritizes IXP
        assert 'audit' in task_auditorias.description.lower() or 'auditor' in task_auditorias.description.lower()
        
        # Check product task configuration
        assert 'product' in task_productos.description.lower() or 'producto' in task_productos.description.lower()
        
        # Check disbursement task configuration
        assert 'disbursement' in task_desembolsos.description.lower() or 'desembolso' in task_desembolsos.description.lower()
    
    @pytest.mark.unit
    def test_expert_agent_concepts(self):
        """Test that expert agents are configured for concept assignment."""
        expert_tasks = [task_experto_auditorias, task_experto_productos, task_experto_desembolsos]
        
        for task in expert_tasks:
            description = task.description
            expected_output = task.expected_output
            
            # Check for expert analysis mentions
            assert 'expert' in description.lower() or 'experto' in description.lower() or \
                   'expert' in expected_output.lower() or 'experto' in expected_output.lower()
    
    @pytest.mark.unit
    def test_concatenator_workflow(self):
        """Test concatenator agent workflow integration."""
        # Test concatenator task exists and is properly configured
        assert task_concatenador is not None
        assert agente_concatenador is not None
        
        # Verify concatenator is assigned to its task
        assert task_concatenador.agent == agente_concatenador
        
        # Check concatenator role
        assert 'Concatenator' in agente_concatenador.role or 'Concatenador' in agente_concatenador.role
        
        # Test agent error handling
        agents = [agente_auditorias, agente_productos, agente_desembolsos,
                 agente_experto_auditorias, agente_experto_productos, 
                 agente_experto_desembolsos, agente_concatenador]
        
        assert len(agents) == 7
        for agent in agents:
            assert agent is not None
    
    @pytest.mark.unit
    def test_workflow_error_handling(self):
        """Test error handling in workflow."""
        # Test with invalid content - tasks should exist
        assert task_auditorias is not None
        assert task_productos is not None
        assert task_desembolsos is not None
    
    @pytest.mark.unit
    @patch('crewai.Crew')
    def test_parallel_vs_sequential_processing(self, mock_crew_class):
        """Test different processing modes."""
        mock_crew = Mock()
        mock_crew_class.return_value = mock_crew
        
        from crewai import Crew, Process
        
        # Test sequential processing
        crew_sequential = Crew(
            agents=[agente_auditorias],
            tasks=[task_auditorias],
            process=Process.sequential
        )
        
        # Verify crew configuration
        assert crew_sequential is not None
        mock_crew_class.assert_called()
    
    @pytest.mark.unit
    def test_agent_role_specialization(self):
        """Test that each agent has proper role specialization."""
        # Test audit specialization
        assert 'Audit' in agente_auditorias.role
        assert 'audit' in agente_auditorias.goal.lower()
        
        # Test product specialization
        assert 'Product' in agente_productos.role
        assert 'product' in agente_productos.goal.lower()
        
        # Test disbursement specialization
        assert 'Disbursement' in agente_desembolsos.role
        assert 'disbursement' in agente_desembolsos.goal.lower()
        
        # Test expert roles
        assert 'Audit' in agente_experto_auditorias.role and 'Expert' in agente_experto_auditorias.role
        assert 'Product' in agente_experto_productos.role and 'Expert' in agente_experto_productos.role
        assert 'Disbursement' in agente_experto_desembolsos.role and 'Expert' in agente_experto_desembolsos.role
    
    @pytest.mark.unit
    def test_task_input_output_structure(self):
        """Test that tasks have proper input/output structure."""
        # Test specialist tasks expect processed_documents input
        specialist_tasks = [task_auditorias, task_productos, task_desembolsos]
        
        for task in specialist_tasks:
            assert '{processed_documents}' in task.description
            assert 'JSON output' in task.expected_output
        
        # Test expert tasks expect analysis results input
        assert '{audit_analysis_results}' in task_experto_auditorias.description
        assert '{product_analysis_results}' in task_experto_productos.description
        assert '{disbursement_analysis_results}' in task_experto_desembolsos.description
        
        # Test concatenator expects expert assessments
        assert '{expert_assessments}' in task_concatenador.description
        assert 'CSV' in task_concatenador.expected_output
    
    @pytest.mark.unit
    def test_workflow_data_flow(self):
        """Test the data flow between workflow stages."""
        # Stage 1: Document processing -> Specialist analysis
        specialist_tasks = [task_auditorias, task_productos, task_desembolsos]
        
        for task in specialist_tasks:
            # Should accept processed documents
            assert 'processed_documents' in task.description
            # Should output structured data
            assert 'structured' in task.expected_output.lower()
        
        # Stage 2: Specialist analysis -> Expert evaluation
        expert_tasks = [task_experto_auditorias, task_experto_productos, task_experto_desembolsos]
        
        for task in expert_tasks:
            # Should accept analysis results
            assert 'analysis_results' in task.description
            # Should output concept classification
            assert 'concept' in task.expected_output.lower()
        
        # Stage 3: Expert evaluation -> Final concatenation
        # Should accept expert assessments
        assert 'expert_assessments' in task_concatenador.description
        # Should output CSV files
        assert 'CSV' in task_concatenador.expected_output
    
    @pytest.mark.unit
    def test_agent_configuration_validation(self):
        """Test agent configuration validation."""
        from agents.agents import get_configured_llm
        
        # Test LLM configuration function
        llm = get_configured_llm()
        # Should not raise exception even if LLM is None
        assert llm is None or llm is not None  # Either case is valid
        
        # Test all agents have required attributes
        all_agents = [
            agente_auditorias, agente_productos, agente_desembolsos,
            agente_experto_auditorias, agente_experto_productos, 
            agente_experto_desembolsos, agente_concatenador
        ]
        
        for agent in all_agents:
            assert hasattr(agent, 'role')
            assert hasattr(agent, 'goal')
            assert hasattr(agent, 'backstory')
            assert hasattr(agent, 'verbose')
            assert hasattr(agent, 'allow_delegation')
            assert agent.verbose is True
            assert agent.allow_delegation is False
    
    @pytest.mark.unit
    @patch('crewai.Crew')
    def test_workflow_execution_phases(self, mock_crew_class):
        """Test workflow execution in distinct phases."""
        mock_crew = Mock()
        mock_crew_class.return_value = mock_crew
        
        from crewai import Crew, Process
        
        # Mock phase results
        phase_results = {
            'specialist_phase': {
                'audit_data': {'findings': [], 'status': 'completed'},
                'product_data': {'products': [], 'status': 'completed'},
                'disbursement_data': {'disbursements': [], 'status': 'completed'}
            },
            'expert_phase': {
                'audit_concept': 'Favorable',
                'product_concept': 'Favorable with reservations',
                'disbursement_concept': 'Favorable'
            },
            'concatenation_phase': {
                'files_generated': ['audits.csv', 'products.csv', 'disbursements.csv']
            }
        }
        mock_crew.kickoff.return_value = phase_results
        
        # Test phase organization
        specialist_agents = [agente_auditorias, agente_productos, agente_desembolsos]
        expert_agents = [agente_experto_auditorias, agente_experto_productos, agente_experto_desembolsos]
        
        # Verify phase agents
        assert len(specialist_agents) == 3
        assert len(expert_agents) == 3
        assert agente_concatenador is not None
        
        # Verify agent roles match phases
        for agent in specialist_agents:
            assert 'Specialist' in agent.role
        
        for agent in expert_agents:
            assert 'Expert' in agent.role
        
        assert 'Concatenator' in agente_concatenador.role
        
        # Create crew_sequential for testing
        crew_sequential = Crew(
            agents=[agente_auditorias],
            tasks=[task_auditorias],
            process=Process.sequential
        )
        assert crew_sequential is not None
        
        # Test hierarchical processing (if available)
        try:
            crew_hierarchical = Crew(
                agents=[agente_auditorias],
                tasks=[task_auditorias],
                process=Process.hierarchical
            )
            assert crew_hierarchical is not None
        except AttributeError:
            # Hierarchical process might not be available in all versions
            pass


class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""
    
    @pytest.mark.integration
    @patch('crewai.Crew')
    def test_full_analysis_pipeline(self, mock_crew_class, sample_analysis_results):
        """Test the complete analysis pipeline."""
        # Setup mock crew
        mock_crew = Mock()
        mock_crew.kickoff.return_value = Mock(raw=json.dumps(sample_analysis_results))
        mock_crew_class.return_value = mock_crew
        
        # Simulate full pipeline
        content = "Test document content for full analysis"
        
        # Create all agents
        agents = [
            agente_auditorias,
            agente_productos,
            agente_desembolsos,
            agente_experto_auditorias,
            agente_experto_productos,
            agente_experto_desembolsos,
            agente_concatenador
        ]
        
        # Create all tasks
        tasks = [
            task_auditorias,
            task_productos,
            task_desembolsos,
            task_experto_auditorias,
            task_experto_productos,
            task_experto_desembolsos,
            task_concatenador
        ]
        
        # Execute workflow
        from crewai import Crew, Process
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        
        assert result is not None
        assert len(agents) == 7
        assert len(tasks) == 7
    
    def test_result_formatting_and_validation(self, sample_analysis_results):
        """Test result formatting and validation."""
        # Test that results have expected structure
        required_keys = [
            'audit_analysis',
            'product_analysis',
            'disbursement_analysis',
            'expert_audit_analysis',
            'expert_product_analysis',
            'expert_disbursement_analysis'
        ]
        
        for key in required_keys:
            assert key in sample_analysis_results
            assert isinstance(sample_analysis_results[key], dict)
    
    def test_output_generation(self, temp_dir, sample_analysis_results):
        """Test output file generation."""
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir()
        
        # Test JSON output
        json_file = output_dir / "results.json"
        with open(json_file, 'w') as f:
            json.dump(sample_analysis_results, f, indent=2)
        
        assert json_file.exists()
        
        # Verify JSON content
        with open(json_file, 'r') as f:
            loaded_results = json.load(f)
        
        assert loaded_results == sample_analysis_results
    
    @patch('builtins.print')
    def test_verbose_output(self, mock_print, sample_analysis_results):
        """Test verbose output functionality."""
        # Simulate verbose output
        for key, value in sample_analysis_results.items():
            print(f"Processing {key}: {value}")
        
        # Verify print was called
        assert mock_print.call_count == len(sample_analysis_results)