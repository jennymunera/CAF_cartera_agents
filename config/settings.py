import os
from typing import Dict, Any
from crewai import LLM

class Settings:
    """
    Centralized configuration for the CrewAI project.
    """
    
    # Azure OpenAI configuration
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    ENDPOINT_URL: str = os.getenv("ENDPOINT_URL", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "")
    DEPLOYMENT_NAME: str = os.getenv("DEPLOYMENT_NAME", "")
    
    # Azure Document Intelligence configuration
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    
    # Project configuration
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "CrewAI_Project")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Agent configuration
    AGENT_CONFIG: Dict[str, Any] = {
        "verbose": True,
        "allow_delegation": False,
        "temperature": 0.7,
    }
    
    # Task configuration
    TASK_CONFIG: Dict[str, Any] = {
        "verbose": True,
        "async_execution": False,
    }
    
    # Crew configuration
    CREW_CONFIG: Dict[str, Any] = {
        "verbose": 2,
        "process": "sequential",  # or "hierarchical"
        "memory": True,
    }
    
    @classmethod
    def validate_config(cls, check_document_intelligence: bool = False) -> bool:
        """
        Validates that the configuration is complete.
        
        Args:
            check_document_intelligence: Whether to validate Document Intelligence configuration
        
        Returns:
            True if configuration is valid, False otherwise
        """
        is_valid = True
        
        # Validate Azure OpenAI configuration
        if not cls.AZURE_OPENAI_API_KEY:
            print("WARNING: AZURE_OPENAI_API_KEY is not configured")
            is_valid = False
        if not cls.ENDPOINT_URL:
            print("WARNING: ENDPOINT_URL is not configured")
            is_valid = False
        if not cls.DEPLOYMENT_NAME:
            print("WARNING: DEPLOYMENT_NAME is not configured")
            is_valid = False
        
        # Validate Document Intelligence configuration if requested
        if check_document_intelligence:
            if not cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:
                print("WARNING: AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured")
                is_valid = False
            if not cls.AZURE_DOCUMENT_INTELLIGENCE_KEY:
                print("WARNING: AZURE_DOCUMENT_INTELLIGENCE_KEY is not configured")
                is_valid = False
        
        if is_valid:
            print("Configuration validated successfully")
        
        return is_valid
    
    @classmethod
    def get_llm_config(cls) -> Dict[str, Any]:
        """
        Returns the configuration for the LLM model.
        
        Returns:
            Dictionary with LLM configuration
        """
        return {
            "model": cls.DEPLOYMENT_NAME,
            "temperature": cls.AGENT_CONFIG["temperature"],
        }
    
    @classmethod
    def get_llm(cls):
        """
        Returns a configured instance of CrewAI LLM for Azure OpenAI.
        
        Returns:
            Configured CrewAI LLM instance
        """
        if not cls.AZURE_OPENAI_API_KEY:
            print("WARNING: AZURE_OPENAI_API_KEY is not configured. Using default configuration.")
            
        return LLM(
            model=f"azure/{cls.DEPLOYMENT_NAME}",
            api_key=cls.AZURE_OPENAI_API_KEY,
            base_url=cls.ENDPOINT_URL,
            api_version=cls.AZURE_OPENAI_API_VERSION,
        )
    
    @classmethod
    def get_document_intelligence_config(cls) -> Dict[str, str]:
        """
        Returns the configuration for Azure Document Intelligence.
        
        Returns:
            Dictionary with Document Intelligence configuration
        """
        return {
            "endpoint": cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
            "api_key": cls.AZURE_DOCUMENT_INTELLIGENCE_KEY
        }

# Global configuration instance
settings = Settings()