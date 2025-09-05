#!/usr/bin/env python3
"""
Test de debug para main.py - Procesamiento completo de documentos

Este script replica la lógica de main.py en modo debug para probar específicamente
el archivo INI-CFA009660-Nota ABC 2017-0688.pdf con logs detallados.

Flujo de test:
1. Configuración de procesadores con logs detallados
2. Procesamiento con Document Intelligence
3. Chunking (si es necesario)
4. Verificación de resultados
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Agregar el directorio padre al path para importar los módulos
sys.path.append(str(Path(__file__).parent.parent))

# Importar procesadores locales
from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor

# Cargar variables de entorno
load_dotenv()

# Configurar logging detallado para debug
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('tests/debug_main_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configurar logging para los módulos importados
logging.getLogger('document_intelligence_processor').setLevel(logging.DEBUG)
logging.getLogger('chunking_processor').setLevel(logging.DEBUG)

# Archivo específico a probar
TEST_FILE = "INI-CFA009660-Nota ABC 2017-0688.pdf"
TEST_PROJECT = "CFA009660"

def debug_separator(title: str, char: str = "=", width: int = 80):
    """
    Imprime un separador visual para debug.
    """
    separator = char * width
    logger.info(f"\n{separator}")
    logger.info(f" {title.center(width-2)} ")
    logger.info(f"{separator}\n")

def debug_step(step_number: int, description: str):
    """
    Marca el inicio de un paso de debug.
    """
    logger.info(f"\n🔍 PASO {step_number}: {description}")
    logger.info("-" * 60)

def setup_document_intelligence_debug() -> DocumentIntelligenceProcessor:
    """
    Configura Document Intelligence con logs de debug detallados.
    """
    debug_step(1, "Configurando Azure Document Intelligence")
    
    # Verificar variables de entorno
    endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    api_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    logger.debug(f"📋 Endpoint configurado: {endpoint is not None}")
    logger.debug(f"📋 API Key configurada: {api_key is not None}")
    
    if not endpoint:
        logger.error("❌ AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT no configurado")
        raise ValueError("Falta AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    
    if not api_key:
        logger.error("❌ AZURE_DOCUMENT_INTELLIGENCE_KEY no configurada")
        raise ValueError("Falta AZURE_DOCUMENT_INTELLIGENCE_KEY")
    
    logger.info(f"✅ Credenciales verificadas")
    logger.debug(f"📋 Endpoint: {endpoint[:50]}...")
    
    # Crear procesador
    processor = DocumentIntelligenceProcessor(
        endpoint=endpoint,
        api_key=api_key,
        input_dir="input_docs",
        output_dir="tests/debug_output",
        auto_chunk=False
    )
    
    logger.info(f"✅ DocumentIntelligenceProcessor creado exitosamente")
    logger.debug(f"📋 Input dir: {processor.input_dir}")
    logger.debug(f"📋 Output dir: {processor.output_dir}")
    logger.debug(f"📋 Auto chunk: {processor.auto_chunk}")
    
    return processor

def setup_chunking_processor_debug() -> ChunkingProcessor:
    """
    Configura ChunkingProcessor con logs de debug detallados.
    """
    debug_step(2, "Configurando Chunking Processor")
    
    processor = ChunkingProcessor(
        max_tokens=100000,
        overlap_tokens=512,
        model_name="gpt-4",
        generate_jsonl=False
    )
    
    logger.info(f"✅ ChunkingProcessor creado exitosamente")
    logger.debug(f"📋 Max tokens: {processor.max_tokens}")
    logger.debug(f"📋 Overlap tokens: {processor.overlap_tokens}")
    logger.debug(f"📋 Model name: {processor.model_name}")
    logger.debug(f"📋 Generate JSONL: {processor.generate_jsonl}")
    
    return processor

def verify_test_file() -> Path:
    """
    Verifica que el archivo de test existe.
    """
    debug_step(3, "Verificando archivo de test")
    
    # Buscar el archivo en input_docs
    test_file_path = Path("input_docs") / TEST_PROJECT / TEST_FILE
    
    logger.debug(f"📋 Buscando archivo: {test_file_path}")
    logger.debug(f"📋 Archivo existe: {test_file_path.exists()}")
    
    if not test_file_path.exists():
        logger.error(f"❌ Archivo no encontrado: {test_file_path}")
        
        # Listar archivos disponibles
        project_dir = Path("input_docs") / TEST_PROJECT
        if project_dir.exists():
            logger.info(f"📁 Archivos disponibles en {project_dir}:")
            for file in project_dir.iterdir():
                if file.is_file():
                    logger.info(f"   - {file.name}")
        
        raise FileNotFoundError(f"Archivo de test no encontrado: {test_file_path}")
    
    logger.info(f"✅ Archivo de test encontrado: {test_file_path}")
    logger.debug(f"📋 Tamaño del archivo: {test_file_path.stat().st_size} bytes")
    
    return test_file_path

def process_document_debug(processor: DocumentIntelligenceProcessor, file_path: Path) -> Dict[str, Any]:
    """
    Procesa el documento con logs de debug detallados.
    """
    debug_step(4, f"Procesando documento: {file_path.name}")
    
    logger.info(f"📄 Iniciando procesamiento de Document Intelligence")
    logger.debug(f"📋 Archivo: {file_path}")
    logger.debug(f"📋 Tamaño: {file_path.stat().st_size} bytes")
    
    try:
        # Procesar documento
        logger.debug("🔄 Llamando a process_single_document...")
        result = processor.process_single_document(file_path)
        
        logger.info(f"✅ Procesamiento completado exitosamente")
        logger.debug(f"📋 Tipo de resultado: {type(result)}")
        logger.debug(f"📋 Claves en resultado: {list(result.keys()) if isinstance(result, dict) else 'No es dict'}")
        
        if isinstance(result, dict):
            if 'content' in result:
                content_length = len(result['content'])
                logger.info(f"📊 Contenido extraído: {content_length} caracteres")
                logger.debug(f"📋 Primeros 200 caracteres: {result['content'][:200]}...")
            
            if 'metadata' in result:
                logger.debug(f"📋 Metadata: {result['metadata']}")
            
            if 'filename' in result:
                logger.debug(f"📋 Filename en resultado: {result['filename']}")
        
        # Crear directorio de salida personalizado
        output_dir = Path("tests/debug_output") / TEST_PROJECT / "DI"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"📋 Directorio de salida creado: {output_dir}")
        
        # Guardar resultado
        output_file = output_dir / f"{file_path.stem}.json"
        logger.debug(f"📋 Guardando resultado en: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Resultado guardado: {output_file}")
        logger.debug(f"📋 Tamaño del archivo JSON: {output_file.stat().st_size} bytes")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error durante el procesamiento: {str(e)}")
        logger.exception("Detalles del error:")
        raise

def process_chunking_debug(chunking_processor: ChunkingProcessor, document_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Procesa el chunking con logs de debug detallados.
    """
    debug_step(5, "Procesando chunking")
    
    if not isinstance(document_result, dict) or 'content' not in document_result:
        logger.error("❌ Resultado de documento inválido para chunking")
        return None
    
    content = document_result['content']
    content_length = len(content)
    
    logger.info(f"📝 Evaluando necesidad de chunking")
    logger.debug(f"📋 Longitud del contenido: {content_length} caracteres")
    
    try:
        # Procesar chunking
        logger.debug("🔄 Llamando a process_document_content...")
        chunking_result = chunking_processor.process_document_content(content, TEST_PROJECT)
        
        logger.debug(f"📋 Tipo de resultado chunking: {type(chunking_result)}")
        logger.debug(f"📋 Claves en resultado: {list(chunking_result.keys()) if isinstance(chunking_result, dict) else 'No es dict'}")
        
        if not chunking_result.get('requires_chunking', False):
            logger.info(f"✅ Documento NO requiere chunking (dentro del límite)")
            logger.debug(f"📋 Total tokens estimados: {chunking_result.get('total_tokens', 'N/A')}")
            return chunking_result
        
        chunks = chunking_result.get('chunks', [])
        num_chunks = len(chunks)
        
        logger.info(f"📝 Documento REQUIERE chunking - Generando {num_chunks} chunks")
        logger.debug(f"📋 Total tokens: {chunking_result.get('total_tokens', 'N/A')}")
        
        # Crear directorio para chunks
        chunks_dir = Path("tests/debug_output") / TEST_PROJECT / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"📋 Directorio de chunks creado: {chunks_dir}")
        
        # Guardar cada chunk
        saved_chunks = []
        document_name = Path(document_result.get('filename', 'unknown')).stem
        
        for i, chunk in enumerate(chunks):
            chunk_filename = f"{document_name}_chunk_{chunk.get('index', i):03d}.json"
            chunk_path = chunks_dir / chunk_filename
            
            logger.debug(f"📋 Procesando chunk {i+1}/{num_chunks}: {chunk_filename}")
            logger.debug(f"📋 Tokens del chunk: {chunk.get('tokens', 'N/A')}")
            logger.debug(f"📋 Contenido del chunk: {len(chunk.get('content', ''))} caracteres")
            
            chunk_data = {
                'document_name': document_name,
                'chunk_index': chunk.get('index', i),
                'content': chunk.get('content', ''),
                'tokens': chunk.get('tokens', 0),
                'sections_range': chunk.get('sections_range', []),
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'project_name': TEST_PROJECT,
                    'total_chunks': num_chunks
                }
            }
            
            with open(chunk_path, 'w', encoding='utf-8') as f:
                json.dump(chunk_data, f, indent=2, ensure_ascii=False)
            
            saved_chunks.append(str(chunk_path))
            logger.info(f"💾 Chunk guardado: {chunk_filename}")
            logger.debug(f"📋 Tamaño del archivo: {chunk_path.stat().st_size} bytes")
        
        chunking_result['saved_chunks'] = saved_chunks
        logger.info(f"✅ Chunking completado - {num_chunks} chunks guardados")
        
        return chunking_result
        
    except Exception as e:
        logger.error(f"❌ Error durante el chunking: {str(e)}")
        logger.exception("Detalles del error:")
        raise

def verify_results_debug():
    """
    Verifica los resultados generados.
    """
    debug_step(6, "Verificando resultados")
    
    output_base = Path("tests/debug_output") / TEST_PROJECT
    
    # Verificar archivo DI
    di_dir = output_base / "DI"
    di_file = di_dir / f"{Path(TEST_FILE).stem}.json"
    
    logger.debug(f"📋 Verificando archivo DI: {di_file}")
    
    if di_file.exists():
        logger.info(f"✅ Archivo DI encontrado: {di_file}")
        logger.debug(f"📋 Tamaño: {di_file.stat().st_size} bytes")
        
        # Cargar y verificar contenido
        try:
            with open(di_file, 'r', encoding='utf-8') as f:
                di_data = json.load(f)
            logger.debug(f"📋 Claves en archivo DI: {list(di_data.keys())}")
            if 'content' in di_data:
                logger.debug(f"📋 Longitud del contenido: {len(di_data['content'])} caracteres")
        except Exception as e:
            logger.error(f"❌ Error leyendo archivo DI: {e}")
    else:
        logger.error(f"❌ Archivo DI no encontrado: {di_file}")
    
    # Verificar chunks
    chunks_dir = output_base / "chunks"
    logger.debug(f"📋 Verificando directorio de chunks: {chunks_dir}")
    
    if chunks_dir.exists():
        chunk_files = list(chunks_dir.glob("*.json"))
        logger.info(f"📊 Chunks encontrados: {len(chunk_files)}")
        
        for chunk_file in chunk_files:
            logger.debug(f"📋 Chunk: {chunk_file.name} ({chunk_file.stat().st_size} bytes)")
    else:
        logger.info(f"📊 No se encontró directorio de chunks (documento no requirió chunking)")

def main_debug():
    """
    Función principal de debug que ejecuta todo el flujo.
    """
    try:
        debug_separator("INICIO DEL TEST DE DEBUG MAIN.PY")
        logger.info(f"🚀 Iniciando test de debug para: {TEST_FILE}")
        logger.info(f"📁 Proyecto: {TEST_PROJECT}")
        logger.info(f"⏰ Timestamp: {datetime.now().isoformat()}")
        
        # Crear directorio de salida
        output_dir = Path("tests/debug_output")
        output_dir.mkdir(exist_ok=True)
        logger.debug(f"📋 Directorio de salida: {output_dir}")
        
        # Paso 1: Configurar Document Intelligence
        doc_processor = setup_document_intelligence_debug()
        
        # Paso 2: Configurar Chunking
        chunking_processor = setup_chunking_processor_debug()
        
        # Paso 3: Verificar archivo
        test_file_path = verify_test_file()
        
        # Paso 4: Procesar documento
        document_result = process_document_debug(doc_processor, test_file_path)
        
        # Paso 5: Procesar chunking
        chunking_result = process_chunking_debug(chunking_processor, document_result)
        
        # Paso 6: Verificar resultados
        verify_results_debug()
        
        # Resumen final
        debug_separator("RESUMEN FINAL")
        logger.info(f"✅ Test completado exitosamente")
        logger.info(f"📄 Documento procesado: {TEST_FILE}")
        
        if isinstance(document_result, dict) and 'content' in document_result:
            logger.info(f"📊 Contenido extraído: {len(document_result['content'])} caracteres")
        
        if chunking_result:
            if chunking_result.get('requires_chunking'):
                num_chunks = len(chunking_result.get('chunks', []))
                logger.info(f"📝 Chunks generados: {num_chunks}")
            else:
                logger.info(f"📝 Chunking: No requerido")
        
        logger.info(f"💾 Resultados guardados en: tests/debug_output/{TEST_PROJECT}/")
        
        debug_separator("TEST FINALIZADO EXITOSAMENTE", "=")
        
    except Exception as e:
        debug_separator("ERROR EN EL TEST", "!")
        logger.error(f"❌ Error crítico en el test: {str(e)}")
        logger.exception("Detalles completos del error:")
        debug_separator("TEST FINALIZADO CON ERRORES", "!")
        sys.exit(1)

if __name__ == "__main__":
    main_debug()