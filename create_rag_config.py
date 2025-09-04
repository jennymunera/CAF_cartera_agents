#!/usr/bin/env python3
"""
Script para crear el archivo rag_config.json necesario para el sistema RAG.
"""

import os
import sys
import logging
from pathlib import Path

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Variables de entorno cargadas desde .env")
except ImportError:
    print("⚠️ python-dotenv no disponible, usando variables de entorno del sistema")

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_rag_config():
    """Crea el archivo rag_config.json con la configuración por defecto"""
    logger.info("🔧 Creando configuración RAG...")
    
    try:
        from rag.config import RAGConfig
        
        # Crear configuración por defecto
        config = RAGConfig()
        
        # Ajustar rutas para el proyecto actual
        project_root = Path.cwd()
        config.base_dir = str(project_root)
        config.input_dir = str(project_root / "input_docs")
        config.output_dir = str(project_root / "output_docs")
        
        # Configurar ChromaDB
        config.chromadb.persist_directory = str(project_root / "rag_vectorstore")
        config.chromadb.use_http_client = True
        config.chromadb.host = "localhost"
        config.chromadb.port = 8000
        
        # Configurar Azure Document Intelligence desde variables de entorno
        azure_endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
        azure_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
        
        if azure_endpoint and azure_key:
            config.azure_di.endpoint = azure_endpoint
            config.azure_di.api_key = azure_key
            logger.info("✅ Credenciales de Azure Document Intelligence configuradas")
        else:
            logger.warning("⚠️ Credenciales de Azure Document Intelligence no encontradas en .env")
            logger.warning("   El sistema funcionará pero sin procesamiento de documentos")
        
        # Configurar embeddings
        config.embeddings.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        config.embeddings.device = "cpu"
        config.embeddings.batch_size = 32
        
        # Configurar chunking
        config.chunking.target_tokens = 512
        config.chunking.overlap_tokens = 50
        config.chunking.min_tokens = 100
        
        # Configurar retrieval
        config.retrieval.k_dense = 10
        config.retrieval.k_sparse = 10
        config.retrieval.k_final = 5
        config.retrieval.dense_weight = 0.7
        config.retrieval.sparse_weight = 0.3
        
        # Crear directorios necesarios
        logger.info("📁 Creando directorios necesarios...")
        config._create_directories()
        
        # Guardar configuración
        config_path = project_root / "rag_config.json"
        config.save_to_file(str(config_path))
        
        logger.info(f"✅ Configuración RAG guardada en: {config_path}")
        logger.info(f"   Directorio de persistencia: {config.chromadb.persist_directory}")
        logger.info(f"   Modelo de embeddings: {config.embeddings.model_name}")
        logger.info(f"   Chunk size: {config.chunking.target_tokens} tokens")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando configuración RAG: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_rag_config():
    """Verifica que la configuración RAG se puede cargar correctamente"""
    logger.info("\n🔍 Verificando configuración RAG...")
    
    try:
        from rag.config import RAGConfig
        
        config_path = Path.cwd() / "rag_config.json"
        if not config_path.exists():
            logger.error(f"❌ Archivo de configuración no encontrado: {config_path}")
            return False
            
        # Cargar configuración
        config = RAGConfig.load_from_file(str(config_path))
        logger.info("✅ Configuración cargada correctamente")
        
        # Verificar componentes clave
        logger.info(f"   Modelo embeddings: {config.embeddings.model_name}")
        logger.info(f"   ChromaDB host: {config.chromadb.host}:{config.chromadb.port}")
        logger.info(f"   Directorio persistencia: {config.chromadb.persist_directory}")
        
        if config.azure_di.endpoint:
            logger.info(f"   Azure DI endpoint: {config.azure_di.endpoint[:50]}...")
        else:
            logger.warning("   Azure DI no configurado")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando configuración: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_tool_initialization():
    """Prueba que el RAGTool se puede inicializar con la nueva configuración"""
    logger.info("\n🤖 Probando inicialización del RAGTool...")
    
    try:
        from agents.agents import RAGTool
        
        # Crear RAGTool (debería encontrar rag_config.json ahora)
        rag_tool = RAGTool()
        
        if rag_tool._rag_pipeline is not None:
            logger.info("✅ RAGTool inicializado correctamente con pipeline RAG")
            return True
        else:
            logger.warning("⚠️ RAGTool inicializado pero sin pipeline RAG")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error inicializando RAGTool: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 Iniciando creación de configuración RAG...")
    
    # Paso 1: Crear configuración
    success1 = create_rag_config()
    
    if not success1:
        logger.error("❌ Falló la creación de configuración")
        sys.exit(1)
    
    # Paso 2: Verificar configuración
    success2 = verify_rag_config()
    
    if not success2:
        logger.error("❌ Falló la verificación de configuración")
        sys.exit(1)
    
    # Paso 3: Probar RAGTool
    success3 = test_rag_tool_initialization()
    
    if success1 and success2 and success3:
        logger.info("\n🎉 ¡Configuración RAG creada y verificada exitosamente!")
        logger.info("\n✅ El RAGTool ahora debería funcionar correctamente con CrewAI")
        logger.info("\n📋 Próximos pasos:")
        logger.info("   1. Ejecutar: python index_documents.py (para indexar documentos)")
        logger.info("   2. Probar CrewAI con rag_search")
        sys.exit(0)
    else:
        logger.error("\n❌ Algunos pasos fallaron")
        sys.exit(1)