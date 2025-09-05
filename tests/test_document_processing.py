#!/usr/bin/env python3
"""
Test script para procesar un documento específico usando Document Intelligence y Chunking Processor
Archivo objetivo: INI-CFA009660-Nota ABC 2017-0688.pdf

Este script está diseñado con logs detallados para debugging y seguimiento paso a paso.
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Agregar el directorio padre al path para importar los módulos
sys.path.append(str(Path(__file__).parent.parent))

from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor

# Configuración de logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/test_processing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def setup_environment():
    """Configura el entorno y verifica las variables necesarias."""
    logger.info("=" * 60)
    logger.info("INICIANDO TEST DE PROCESAMIENTO DE DOCUMENTOS")
    logger.info("=" * 60)
    
    # Verificar variables de entorno
    endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    api_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    if not endpoint or not api_key:
        logger.error("❌ Variables de entorno no configuradas:")
        logger.error(f"   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: {'✓' if endpoint else '❌'}")
        logger.error(f"   AZURE_DOCUMENT_INTELLIGENCE_KEY: {'✓' if api_key else '❌'}")
        raise ValueError("Configurar variables de entorno de Azure Document Intelligence")
    
    logger.info("✅ Variables de entorno configuradas correctamente")
    logger.info(f"   Endpoint: {endpoint[:50]}...")
    logger.info(f"   API Key: {'*' * 20}...{api_key[-4:]}")
    
    return endpoint, api_key

def verify_file_exists(file_path):
    """Verifica que el archivo objetivo existe."""
    logger.info(f"🔍 Verificando existencia del archivo: {file_path}")
    
    if not file_path.exists():
        logger.error(f"❌ Archivo no encontrado: {file_path}")
        logger.error("   Archivos disponibles en input_docs/CFA009660/:")
        
        input_dir = Path("input_docs/CFA009660")
        if input_dir.exists():
            for file in input_dir.iterdir():
                if file.is_file():
                    logger.error(f"     - {file.name}")
        else:
            logger.error(f"     Directorio no existe: {input_dir}")
        
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    
    file_size = file_path.stat().st_size
    logger.info(f"✅ Archivo encontrado")
    logger.info(f"   Tamaño: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    logger.info(f"   Extensión: {file_path.suffix}")
    
    return file_size

def test_document_intelligence_processing(processor, file_path):
    """Prueba el procesamiento con Document Intelligence."""
    logger.info("\n" + "=" * 50)
    logger.info("PASO 1: PROCESAMIENTO CON DOCUMENT INTELLIGENCE")
    logger.info("=" * 50)
    
    try:
        logger.info(f"📄 Iniciando procesamiento del documento: {file_path.name}")
        logger.info(f"   Modelo: prebuilt-layout")
        logger.info(f"   Procesador: Azure Document Intelligence")
        
        # Procesar documento
        start_time = datetime.now()
        logger.info(f"⏱️  Tiempo de inicio: {start_time.strftime('%H:%M:%S')}")
        
        result = processor.process_single_document(file_path)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        logger.info(f"⏱️  Tiempo de procesamiento: {processing_time:.2f} segundos")
        
        # Analizar resultados
        logger.info("\n📊 RESULTADOS DEL PROCESAMIENTO:")
        logger.info(f"   Archivo: {result['filename']}")
        logger.info(f"   Contenido extraído: {len(result['content']):,} caracteres")
        
        metadata = result['metadata']
        logger.info(f"   Estado: {metadata['processing_status']}")
        logger.info(f"   Páginas: {metadata['pages']}")
        logger.info(f"   Tablas encontradas: {metadata['tables_found']}")
        logger.info(f"   Imágenes encontradas: {metadata['images_found']}")
        
        if metadata.get('confidence_score'):
            logger.info(f"   Score de confianza promedio: {metadata['confidence_score']:.3f}")
        
        # Mostrar muestra del contenido
        content_preview = result['content'][:500] + "..." if len(result['content']) > 500 else result['content']
        logger.info(f"\n📝 MUESTRA DEL CONTENIDO EXTRAÍDO:")
        logger.info(f"   Primeros 500 caracteres:")
        logger.info(f"   {'-' * 40}")
        logger.info(f"   {content_preview}")
        logger.info(f"   {'-' * 40}")
        
        # Analizar datos estructurados
        json_data = result['json_data']
        logger.info(f"\n🏗️  DATOS ESTRUCTURADOS:")
        logger.info(f"   Tablas: {len(json_data.get('tables', []))}")
        logger.info(f"   Imágenes: {len(json_data.get('images', []))}")
        logger.info(f"   Pares clave-valor: {len(json_data.get('key_value_pairs', []))}")
        logger.info(f"   Párrafos: {len(json_data.get('paragraphs', []))}")
        
        if json_data.get('tables'):
            logger.info(f"   Detalles de tablas:")
            for i, table in enumerate(json_data['tables']):
                logger.info(f"     Tabla {i+1}: {table['row_count']}x{table['column_count']} celdas")
        
        logger.info("✅ Procesamiento con Document Intelligence completado exitosamente")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error en procesamiento con Document Intelligence: {str(e)}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        raise

def test_chunking_processing(chunking_processor, content, project_name):
    """Prueba el procesamiento de chunking."""
    logger.info("\n" + "=" * 50)
    logger.info("PASO 2: PROCESAMIENTO DE CHUNKING")
    logger.info("=" * 50)
    
    try:
        logger.info(f"📦 Iniciando chunking del contenido")
        logger.info(f"   Proyecto: {project_name}")
        logger.info(f"   Contenido total: {len(content):,} caracteres")
        logger.info(f"   Max tokens por chunk: {chunking_processor.max_tokens:,}")
        logger.info(f"   Overlap tokens: {chunking_processor.overlap_tokens:,}")
        
        # Contar tokens iniciales
        total_tokens = chunking_processor.count_tokens(content)
        logger.info(f"   Tokens totales: {total_tokens:,}")
        
        start_time = datetime.now()
        logger.info(f"⏱️  Tiempo de inicio chunking: {start_time.strftime('%H:%M:%S')}")
        
        # Procesar chunking
        chunking_result = chunking_processor.process_document_content(content, project_name)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        logger.info(f"⏱️  Tiempo de chunking: {processing_time:.2f} segundos")
        
        # Analizar resultados del chunking
        logger.info("\n📊 RESULTADOS DEL CHUNKING:")
        logger.info(f"   Requiere chunking: {chunking_result['requires_chunking']}")
        logger.info(f"   Estrategia utilizada: {chunking_result['chunking_strategy']}")
        logger.info(f"   Número de chunks: {len(chunking_result['chunks'])}")
        
        if chunking_result['requires_chunking']:
            logger.info(f"   Configuración:")
            logger.info(f"     Max tokens por chunk: {chunking_result['max_tokens_per_chunk']:,}")
            logger.info(f"     Overlap tokens: {chunking_result['overlap_tokens']:,}")
            
            logger.info(f"\n📋 DETALLES DE CHUNKS:")
            for i, chunk in enumerate(chunking_result['chunks']):
                logger.info(f"   Chunk {chunk['index']}:")
                logger.info(f"     Tokens: {chunk['tokens']:,}")
                logger.info(f"     Caracteres: {len(chunk['content']):,}")
                logger.info(f"     Rango: {chunk['sections_range']}")
                
                # Mostrar muestra del chunk
                chunk_preview = chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
                logger.info(f"     Muestra: {chunk_preview.replace(chr(10), ' ')[:150]}...")
        else:
            logger.info(f"   El documento no requiere chunking (está dentro del límite)")
        
        logger.info("✅ Procesamiento de chunking completado exitosamente")
        return chunking_result
        
    except Exception as e:
        logger.error(f"❌ Error en procesamiento de chunking: {str(e)}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        raise

def save_test_results(doc_result, chunking_result, output_dir="tests/output"):
    """Guarda los resultados del test para análisis posterior."""
    logger.info("\n" + "=" * 50)
    logger.info("PASO 3: GUARDANDO RESULTADOS")
    logger.info("=" * 50)
    
    try:
        # Crear directorio de salida
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Guardar resultado de Document Intelligence
        doc_file = output_path / f"document_intelligence_result_{timestamp}.json"
        with open(doc_file, 'w', encoding='utf-8') as f:
            json.dump(doc_result, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Resultado Document Intelligence guardado: {doc_file}")
        
        # Guardar resultado de Chunking
        chunk_file = output_path / f"chunking_result_{timestamp}.json"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunking_result, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Resultado Chunking guardado: {chunk_file}")
        
        # Contenido extraído no se guarda en formato TXT (eliminado por solicitud del usuario)
        
        # Chunks individuales no se guardan en formato TXT (eliminado por solicitud del usuario)
        
        logger.info("✅ Todos los resultados guardados exitosamente")
        
    except Exception as e:
        logger.error(f"❌ Error guardando resultados: {str(e)}")
        raise

def main():
    """Función principal del test."""
    try:
        # Configurar entorno
        endpoint, api_key = setup_environment()
        
        # Definir archivo objetivo
        target_file = Path("input_docs/CFA009660/INI-CFA009660-Nota ABC 2017-0688.pdf")
        project_name = "CFA009660"
        
        # Verificar archivo
        file_size = verify_file_exists(target_file)
        
        # Inicializar procesadores
        logger.info("\n🔧 INICIALIZANDO PROCESADORES")
        doc_processor = DocumentIntelligenceProcessor(
            endpoint=endpoint,
            api_key=api_key,
            input_dir="input_docs",
            output_dir="output_docs",
            auto_chunk=False  # Deshabilitamos auto-chunk para control manual
        )
        logger.info("✅ Document Intelligence Processor inicializado")
        
        chunking_processor = ChunkingProcessor(
            max_tokens=100000,
            overlap_tokens=512,
            model_name="gpt-4",
            generate_jsonl=True
        )
        logger.info("✅ Chunking Processor inicializado")
        
        # Ejecutar tests
        doc_result = test_document_intelligence_processing(doc_processor, target_file)
        chunking_result = test_chunking_processing(chunking_processor, doc_result['content'], project_name)
        
        # Guardar resultados
        save_test_results(doc_result, chunking_result)
        
        # Resumen final
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN FINAL DEL TEST")
        logger.info("=" * 60)
        logger.info(f"✅ Archivo procesado: {target_file.name}")
        logger.info(f"✅ Contenido extraído: {len(doc_result['content']):,} caracteres")
        logger.info(f"✅ Tokens totales: {chunking_result['total_tokens']:,}")
        logger.info(f"✅ Chunks generados: {len(chunking_result['chunks'])}")
        logger.info(f"✅ Estado: {doc_result['metadata']['processing_status']}")
        logger.info("✅ Test completado exitosamente")
        
    except Exception as e:
        logger.error(f"\n❌ ERROR CRÍTICO EN EL TEST: {str(e)}")
        logger.error(f"   Tipo: {type(e).__name__}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()