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
    
    # Project configuration
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "CrewAI_Project")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Agent configuration
    AGENT_CONFIG: Dict[str, Any] = {
        "verbose": True,
        "allow_delegation": False,
        "temperature": 0.7,
        "max_tokens": 2000,
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
    def validate_config(cls) -> bool:
        """
        Validates that the configuration is complete.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        if not cls.AZURE_OPENAI_API_KEY:
            print("WARNING: AZURE_OPENAI_API_KEY is not configured")
            return False
        if not cls.ENDPOINT_URL:
            print("WARNING: ENDPOINT_URL is not configured")
            return False
        if not cls.DEPLOYMENT_NAME:
            print("WARNING: DEPLOYMENT_NAME is not configured")
            return False
            
        print("Configuration validated successfully")
        return True
    
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
            "max_tokens": cls.AGENT_CONFIG["max_tokens"],
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
            api_version=cls.AZURE_OPENAI_API_VERSION
        )

# Global configuration instance
settings = Settings()