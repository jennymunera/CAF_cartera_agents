"""Tests for CrewAI integration with RAG system.

Tests the integration between CrewAI agents and the RAG pipeline,
including context retrieval, agent tool usage, and workflow integration.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import CrewAI components
try:
    from crewai import Agent, Task, Crew
    from crewai.tools import BaseTool
except ImportError:
    pytest.skip("CrewAI not available", allow_module_level=True)

# Import RAG components
try:
    from rag.config import RAGConfig
    from rag.rag_pipeline import RAGPipeline
    from rag.document_processor import DocumentChunk
    from rag.retriever import RetrievalResponse, RetrievalResult
    from agents.agents import RAGTool
except ImportError as e:
    pytest.skip(f"RAG modules not available: {e}", allow_module_level=True)


class TestRAGTool:
    """Test RAG tool for CrewAI integration."""
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_rag_tool_initialization(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test RAG tool initialization with mocked pipeline."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        
        # Create RAG tool
        rag_tool = RAGTool()
        
        assert rag_tool.name == "rag_search"
        assert "busca información relevante" in rag_tool.description.lower()
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_rag_tool_successful_search(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test successful RAG search through tool."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        
        # Mock successful query result
        mock_results = [
            RetrievalResult(
                id="chunk_1",
                content="This is relevant information about auditorías.",
                metadata={"document_id": "audit_doc_1", "section": "introduction"},
                score=0.95,
                rank=1,
                retrieval_method="hybrid"
            ),
            RetrievalResult(
                id="chunk_2",
                content="Additional context about audit processes.",
                metadata={"document_id": "audit_doc_2", "section": "procedures"},
                score=0.87,
                rank=2,
                retrieval_method="hybrid"
            )
        ]
        
        rag_pipeline.query = Mock(return_value={
            "success": True,
            "results": mock_results,
            "context": "Combined context from retrieved documents",
            "retrieval_time": 0.15,
            "total_time": 0.25,
            "query_id": "test_query_1"
        })
        
        # Create and test RAG tool
        rag_tool = RAGTool()
        result = rag_tool._run("What are the audit procedures?")
        
        assert "This is relevant information about auditorías" in result
        assert "Additional context about audit processes" in result
        assert "Score: 0.950" in result
        assert "Score: 0.870" in result
        assert "audit_doc_1" in result
        assert "RAG Search Metadata" in result
        assert "Results found: 2" in result
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_rag_tool_error_handling(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test RAG tool error handling."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        
        # Mock failed query result
        rag_pipeline.query = Mock(return_value={
            "success": False,
            "error": "Vector store connection failed"
        })
        
        # Create and test RAG tool
        rag_tool = RAGTool()
        result = rag_tool._run("Test query")
        
        assert "Error in RAG search" in result
        assert "Vector store connection failed" in result
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_rag_tool_exception_handling(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test RAG tool exception handling."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        
        # Mock exception during query
        rag_pipeline.query = Mock(side_effect=Exception("Connection timeout"))
        
        # Create and test RAG tool
        rag_tool = RAGTool()
        result = rag_tool._run("Test query")
        
        assert "Error executing RAG search" in result
        assert "Connection timeout" in result


class TestCrewAIAgentIntegration:
    """Test CrewAI agent integration with RAG system."""
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_agent_with_rag_tool(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test CrewAI agent using RAG tool."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        
        # Mock successful RAG query
        rag_pipeline.query = Mock(return_value={
            "success": True,
            "results": [
                RetrievalResult(
                    id="chunk_1",
                    content="Audit procedures include risk assessment and testing.",
                    metadata={"document_id": "audit_manual"},
                    score=0.92,
                    rank=1,
                    retrieval_method="hybrid"
                )
            ],
            "context": "Audit procedures include risk assessment and testing.",
            "retrieval_time": 0.1,
            "total_time": 0.2
        })
        
        # Create RAG tool
        rag_tool = RAGTool()
        
        # Create agent with RAG tool
        agent = Agent(
            role="Audit Expert",
            goal="Provide expert audit guidance using company documentation",
            backstory="You are an experienced auditor with access to company audit procedures and guidelines.",
            tools=[rag_tool],
            verbose=True
        )
        
        assert agent.role == "Audit Expert"
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "rag_search"
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_multiple_agents_with_rag(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test multiple agents sharing RAG system."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        
        # Create RAG tool
        rag_tool = RAGTool()
        
        # Create multiple agents with different specializations
        audit_agent = Agent(
            role="Audit Specialist",
            goal="Conduct thorough audits using company procedures",
            backstory="Expert in audit procedures and compliance",
            tools=[rag_tool]
        )
        
        product_agent = Agent(
            role="Product Specialist",
            goal="Provide product information and recommendations",
            backstory="Expert in product catalog and specifications",
            tools=[rag_tool]
        )
        
        disbursement_agent = Agent(
            role="Disbursement Specialist",
            goal="Process and validate disbursement requests",
            backstory="Expert in disbursement procedures and validation",
            tools=[rag_tool]
        )
        
        agents = [audit_agent, product_agent, disbursement_agent]
        
        # Verify all agents have access to RAG
        for agent in agents:
            assert len(agent.tools) == 1
            assert agent.tools[0].name == "rag_search"
            assert isinstance(agent.tools[0], RAGTool)
    
    def test_rag_tool_with_metadata_filtering(self):
        """Test RAG tool with metadata filtering for agent specialization."""
        with patch('rag.rag_pipeline.DocumentProcessor'), \
             patch('rag.rag_pipeline.EmbeddingManager'), \
             patch('rag.rag_pipeline.ChromaVectorStore'), \
             patch('rag.rag_pipeline.HybridRetriever'):
            
            config = RAGConfig()
            rag_pipeline = RAGPipeline(config)
            
            # Mock query with metadata filter
            rag_pipeline.query = Mock(return_value={
                "success": True,
                "results": [
                    RetrievalResult(
                        id="audit_chunk_1",
                        content="Specific audit procedure for risk assessment.",
                        metadata={"document_type": "audit", "section": "procedures"},
                        score=0.95,
                        rank=1,
                        retrieval_method="hybrid"
                    )
                ],
                "context": "Filtered audit context",
                "retrieval_time": 0.12,
                "total_time": 0.22
            })
            
            rag_tool = RAGTool()
            
            # Test with metadata filter
            result = rag_tool._run(
                query="What are the risk assessment procedures?",
                metadata_filter={"document_type": "audit"}
            )
            
            # Verify the query was called with metadata filter
            rag_pipeline.query.assert_called_once_with(
                query="What are the risk assessment procedures?",
                k=5,
                metadata_filter={"document_type": "audit"}
            )
            
            assert "Specific audit procedure" in result
            assert "document_type" not in result  # Metadata shouldn't be in formatted output


class TestRAGWorkflowIntegration:
    """Test complete workflow integration between CrewAI and RAG."""
    
    @patch('rag.rag_pipeline.DocumentProcessor')
    @patch('rag.rag_pipeline.EmbeddingManager')
    @patch('rag.rag_pipeline.ChromaVectorStore')
    @patch('rag.rag_pipeline.HybridRetriever')
    def test_crew_with_rag_workflow(self, mock_retriever, mock_vector_store, mock_embedding_manager, mock_doc_processor):
        """Test complete crew workflow with RAG integration."""
        # Setup mocks
        mock_doc_processor.return_value = Mock()
        mock_embedding_manager.return_value = Mock()
        mock_vector_store.return_value = Mock()
        mock_retriever.return_value = Mock()
        
        config = RAGConfig()
        rag_pipeline = RAGPipeline(config)
        rag_tool = RAGTool()
        
        # Create agents
        researcher = Agent(
            role="Research Specialist",
            goal="Research and gather relevant information",
            backstory="Expert at finding and analyzing information",
            tools=[rag_tool]
        )
        
        analyst = Agent(
            role="Analysis Specialist",
            goal="Analyze information and provide insights",
            backstory="Expert at analyzing data and providing recommendations",
            tools=[rag_tool]
        )
        
        # Create tasks
        research_task = Task(
            description="Research audit procedures for financial institutions",
            agent=researcher,
            expected_output="Comprehensive list of audit procedures"
        )
        
        analysis_task = Task(
            description="Analyze the research findings and provide recommendations",
            agent=analyst,
            expected_output="Analysis report with recommendations"
        )
        
        # Create crew
        crew = Crew(
            agents=[researcher, analyst],
            tasks=[research_task, analysis_task],
            verbose=True
        )
        
        # Verify crew setup
        assert len(crew.agents) == 2
        assert len(crew.tasks) == 2
        assert all(len(agent.tools) == 1 for agent in crew.agents)
        assert all(agent.tools[0].name == "rag_search" for agent in crew.agents)
    
    def test_rag_context_building_for_agents(self):
        """Test RAG context building specifically for agent consumption."""
        with patch('rag.rag_pipeline.DocumentProcessor'), \
             patch('rag.rag_pipeline.EmbeddingManager'), \
             patch('rag.rag_pipeline.ChromaVectorStore'), \
             patch('rag.rag_pipeline.HybridRetriever'):
            
            config = RAGConfig()
            rag_pipeline = RAGPipeline(config)
            
            # Mock complex query result with multiple documents
            mock_results = [
                RetrievalResult(
                    id="chunk_1",
                    content="Financial audit procedures require thorough documentation.",
                    metadata={
                        "document_id": "audit_manual_v2",
                        "section": "documentation",
                        "page": 15,
                        "document_type": "audit"
                    },
                    score=0.95,
                    rank=1,
                    retrieval_method="hybrid"
                ),
                RetrievalResult(
                    id="chunk_2",
                    content="Risk assessment is the first step in any audit process.",
                    metadata={
                        "document_id": "risk_guidelines",
                        "section": "process",
                        "page": 3,
                        "document_type": "audit"
                    },
                    score=0.89,
                    rank=2,
                    retrieval_method="hybrid"
                ),
                RetrievalResult(
                    id="chunk_3",
                    content="Compliance checks must be performed according to regulations.",
                    metadata={
                        "document_id": "compliance_manual",
                        "section": "regulations",
                        "page": 22,
                        "document_type": "compliance"
                    },
                    score=0.82,
                    rank=3,
                    retrieval_method="dense"
                )
            ]
            
            rag_pipeline.query = Mock(return_value={
                "success": True,
                "results": mock_results,
                "context": "Combined context from all retrieved documents",
                "retrieval_time": 0.18,
                "total_time": 0.35,
                "query_id": "complex_query_1"
            })
            
            rag_tool = RAGTool()
            result = rag_tool._run("What are the key audit procedures?")
            
            # Verify comprehensive context formatting
            assert "[Document 1]" in result
            assert "[Document 2]" in result
            assert "[Document 3]" in result
            assert "Score: 0.950" in result
            assert "Score: 0.890" in result
            assert "Score: 0.820" in result
            assert "audit_manual_v2" in result
            assert "risk_guidelines" in result
            assert "compliance_manual" in result
            assert "Results found: 3" in result
            assert "Retrieval time: 0.180s" in result


class TestRAGAgentSpecialization:
    """Test RAG integration with specialized agents."""
    
    def test_audit_agent_rag_specialization(self):
        """Test audit agent with RAG specialization."""
        with patch('rag.rag_pipeline.DocumentProcessor'), \
             patch('rag.rag_pipeline.EmbeddingManager'), \
             patch('rag.rag_pipeline.ChromaVectorStore'), \
             patch('rag.rag_pipeline.HybridRetriever'):
            
            config = RAGConfig()
            rag_pipeline = RAGPipeline(config)
            rag_tool = RAGTool()
            
            # Create specialized audit agent
            audit_agent = Agent(
                role="Senior Audit Specialist",
                goal="Conduct comprehensive audits following company procedures and regulatory requirements",
                backstory="""You are a senior auditor with 15+ years of experience in financial auditing.
                You have deep knowledge of audit procedures, risk assessment, and compliance requirements.
                You always reference company audit manuals and procedures when providing guidance.
                Use the RAG search tool to find relevant audit procedures and guidelines before responding.""",
                tools=[rag_tool],
                verbose=True
            )
            
            assert "Senior Audit Specialist" in audit_agent.role
            assert "audit procedures" in audit_agent.backstory
            assert "RAG search tool" in audit_agent.backstory
            assert len(audit_agent.tools) == 1
    
    def test_product_agent_rag_specialization(self):
        """Test product agent with RAG specialization."""
        with patch('rag.rag_pipeline.DocumentProcessor'), \
             patch('rag.rag_pipeline.EmbeddingManager'), \
             patch('rag.rag_pipeline.ChromaVectorStore'), \
             patch('rag.rag_pipeline.HybridRetriever'):
            
            config = RAGConfig()
            rag_pipeline = RAGPipeline(config)
            rag_tool = RAGTool()
            
            # Create specialized product agent
            product_agent = Agent(
                role="Product Information Specialist",
                goal="Provide accurate product information, specifications, and recommendations",
                backstory="""You are a product expert with comprehensive knowledge of the company's product catalog.
                You help customers and internal teams understand product features, specifications, and compatibility.
                Always search the product documentation using RAG before providing product information.
                Filter your searches by document_type='product' to get relevant product information.""",
                tools=[rag_tool],
                verbose=True
            )
            
            assert "Product Information Specialist" in product_agent.role
            assert "product catalog" in product_agent.backstory
            assert "document_type='product'" in product_agent.backstory
            assert len(product_agent.tools) == 1
    
    def test_disbursement_agent_rag_specialization(self):
        """Test disbursement agent with RAG specialization."""
        with patch('rag.rag_pipeline.DocumentProcessor'), \
             patch('rag.rag_pipeline.EmbeddingManager'), \
             patch('rag.rag_pipeline.ChromaVectorStore'), \
             patch('rag.rag_pipeline.HybridRetriever'):
            
            config = RAGConfig()
            rag_pipeline = RAGPipeline(config)
            rag_tool = RAGTool()
            
            # Create specialized disbursement agent
            disbursement_agent = Agent(
                role="Disbursement Processing Specialist",
                goal="Process and validate disbursement requests according to company policies",
                backstory="""You are a disbursement specialist responsible for processing financial disbursements.
                You ensure all disbursements comply with company policies and regulatory requirements.
                Use RAG search to find relevant disbursement procedures, validation rules, and approval workflows.
                Filter searches by document_type='disbursement' for relevant procedures.""",
                tools=[rag_tool],
                verbose=True
            )
            
            assert "Disbursement Processing Specialist" in disbursement_agent.role
            assert "disbursement procedures" in disbursement_agent.backstory
            assert "document_type='disbursement'" in disbursement_agent.backstory
            assert len(disbursement_agent.tools) == 1


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])