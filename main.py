#!/usr/bin/env python3
"""
Script principal para el procesamiento completo de documentos.

Flujo:
1. Procesamiento de documentos con Azure Document Intelligence
2. Chunking de documentos (si es necesario > 100k tokens)
3. Procesamiento con Azure OpenAI (pendiente)

Estructura de salida:
- /output_docs/{project}/DI/{document}.json - Resultados de Document Intelligence
- /output_docs/{project}/chunks/{document_chunk_{XXX}}.json - Chunks individuales
"""

# ============================================================================
# 1. IMPORTACIONES
# ============================================================================

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Importar procesadores locales
from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor
from openai_processor import OpenAIProcessor

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('main_processing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# 2. PROCESAMIENTO DE DOCUMENTOS CON AZURE DOCUMENT INTELLIGENCE
# ============================================================================

def setup_document_intelligence() -> DocumentIntelligenceProcessor:
    """
    Configura y retorna el procesador de Document Intelligence.
    
    Returns:
        DocumentIntelligenceProcessor: Instancia configurada del procesador
    """
    logger.info("🔧 Configurando Azure Document Intelligence...")
    
    # Obtener credenciales del entorno
    endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    api_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    if not endpoint or not api_key:
        raise ValueError("Faltan credenciales de Azure Document Intelligence en las variables de entorno")
    
    processor = DocumentIntelligenceProcessor(
        endpoint=endpoint,
        api_key=api_key,
        input_dir="input_docs",
        output_dir="output_docs",
        auto_chunk=False  # Manejamos chunking manualmente
    )
    
    logger.info("✅ Document Intelligence configurado correctamente")
    return processor


def process_single_document_with_custom_output(processor: DocumentIntelligenceProcessor, 
                                              file_path: Path, 
                                              project_name: str) -> tuple[Dict[str, Any], bool]:
    """
    Procesa un documento individual y guarda el resultado en la estructura personalizada.
    
    Args:
        processor: Instancia del procesador de Document Intelligence
        file_path: Ruta al archivo a procesar
        project_name: Nombre del proyecto
        
    Returns:
        Tuple con (Dict con los resultados del procesamiento, bool indicando si fue saltado)
    """
    logger.info(f"📄 Procesando documento: {file_path.name}")
    
    # Verificar si el documento ya está procesado
    if processor._is_document_already_processed(file_path, project_name):
        logger.info(f"⏭️ Documento ya procesado, saltando: {file_path.name}")
        
        # Intentar cargar resultado existente de la carpeta DI
        output_base = Path("output_docs") / project_name / "DI"
        document_name = file_path.stem
        output_file = output_base / f"{document_name}.json"
        
        if output_file.exists():
            # Cargar desde archivo DI
            with open(output_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            return result, True  # True indica que fue saltado
        else:
            # El documento está chunkeado pero no tiene archivo DI
            # Crear un resultado mínimo para indicar que está procesado
            result = {
                "metadata": {
                    "processing_status": "chunked_only",
                    "document_name": file_path.name,
                    "processed_date": datetime.now().isoformat()
                },
                "content": "Document already chunked - no DI processing needed"
            }
            return result, True  # True indica que fue saltado
    
    # Procesar documento
    result = processor.process_single_document(file_path)
    
    # Crear estructura de directorios personalizada
    output_base = Path("output_docs") / project_name / "DI"
    output_base.mkdir(parents=True, exist_ok=True)
    
    # Guardar resultado en formato JSON
    document_name = file_path.stem
    output_file = output_base / f"{document_name}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    logger.info(f"💾 Resultado guardado: {output_file}")
    return result, False  # False indica que fue procesado


def process_project_documents_with_custom_output(processor: DocumentIntelligenceProcessor, 
                                                project_name: str) -> Dict[str, Any]:
    """
    Procesa todos los documentos de un proyecto y guarda cada uno individualmente.
    
    Args:
        processor: Instancia del procesador de Document Intelligence
        project_name: Nombre del proyecto a procesar
        
    Returns:
        Dict con resumen del procesamiento del proyecto
    """
    logger.info(f"📁 Procesando proyecto: {project_name}")
    
    # Obtener lista de documentos del proyecto
    project_path = Path("input_docs") / project_name
    if not project_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_path}")
    
    # Extensiones soportadas
    supported_extensions = ['*.pdf', '*.docx', '*.doc', '*.xlsx', '*.xls']
    
    # Encontrar todos los documentos
    all_documents = []
    for ext in supported_extensions:
        all_documents.extend(project_path.glob(ext))
    
    # Filtrar por prefijos requeridos
    required_prefixes = ['INI', 'IXP', 'DEC', 'ROP', 'IFS']
    filtered_documents = []
    
    for doc_path in all_documents:
        filename = doc_path.name.upper()
        if any(filename.startswith(prefix) for prefix in required_prefixes):
            filtered_documents.append(doc_path)
    
    logger.info(f"📊 Documentos encontrados: {len(all_documents)} total, {len(filtered_documents)} con prefijos requeridos")
    
    # Procesar cada documento individualmente
    processed_documents = []
    successful_count = 0
    failed_count = 0
    skipped_count = 0
    
    for doc_path in filtered_documents:
        try:
            result, was_skipped = process_single_document_with_custom_output(processor, doc_path, project_name)
            
            if was_skipped:
                processed_documents.append({
                    'filename': doc_path.name,
                    'status': 'skipped',
                    'content_length': len(result['content']),
                    'metadata': result['metadata']
                })
                skipped_count += 1
            else:
                processed_documents.append({
                    'filename': doc_path.name,
                    'status': 'success',
                    'content_length': len(result['content']),
                    'metadata': result['metadata']
                })
                successful_count += 1
            
        except Exception as e:
            logger.error(f"❌ Error procesando {doc_path.name}: {str(e)}")
            processed_documents.append({
                'filename': doc_path.name,
                'status': 'failed',
                'error': str(e)
            })
            failed_count += 1
    
    summary = {
        'project_name': project_name,
        'total_documents': len(filtered_documents),
        'successful_documents': successful_count,
        'skipped_documents': skipped_count,
        'failed_documents': failed_count,
        'processed_documents': processed_documents,
        'processing_timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"✅ Procesamiento completado - Exitosos: {successful_count}, Saltados: {skipped_count}, Fallidos: {failed_count}")
    return summary


# ============================================================================
# 3. CHUNKING DE DOCUMENTOS (SI ES NECESARIO > 100K TOKENS)
# ============================================================================

def setup_chunking_processor() -> ChunkingProcessor:
    """
    Configura y retorna el procesador de chunking.
    
    Returns:
        ChunkingProcessor: Instancia configurada del procesador
    """
    logger.info("🔧 Configurando Chunking Processor...")
    
    processor = ChunkingProcessor(
        max_tokens=100000,  # 100k tokens como límite
        overlap_tokens=512,
        model_name="gpt-4",
        generate_jsonl=False  # No generamos JSONL en esta etapa
    )
    
    logger.info("✅ Chunking Processor configurado correctamente")
    return processor


def process_document_chunking(chunking_processor: ChunkingProcessor,
                            document_result: Dict[str, Any],
                            project_name: str) -> Optional[Dict[str, Any]]:
    """
    Procesa el chunking de un documento si es necesario.
    
    Args:
        chunking_processor: Instancia del procesador de chunking
        document_result: Resultado del procesamiento de Document Intelligence
        project_name: Nombre del proyecto
        
    Returns:
        Dict con resultados del chunking o None si no fue necesario
    """
    document_name = Path(document_result['filename']).stem
    content = document_result['content']
    
    logger.info(f"🔄 Evaluando chunking para: {document_name}")
    
    # Procesar chunking
    chunking_result = chunking_processor.process_document_content(content, project_name)
    
    if not chunking_result['requires_chunking']:
        logger.info(f"✅ {document_name} no requiere chunking (dentro del límite de tokens)")
        return None
    
    logger.info(f"📝 {document_name} requiere chunking - Generando {len(chunking_result['chunks'])} chunks")
    
    # Crear directorio para chunks
    chunks_dir = Path("output_docs") / project_name / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    
    # Guardar cada chunk individualmente
    saved_chunks = []
    for chunk in chunking_result['chunks']:
        chunk_filename = f"{document_name}_chunk_{chunk['index']:03d}.json"
        chunk_path = chunks_dir / chunk_filename
        
        chunk_data = {
            'document_name': document_name,
            'chunk_index': chunk['index'],
            'content': chunk['content'],
            'tokens': chunk['tokens'],
            'sections_range': chunk['sections_range'],
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'project_name': project_name,
                'total_chunks': len(chunking_result['chunks'])
            }
        }
        
        with open(chunk_path, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, indent=2, ensure_ascii=False)
        
        saved_chunks.append(str(chunk_path))
        logger.info(f"💾 Chunk guardado: {chunk_filename}")
    
    chunking_result['saved_chunks'] = saved_chunks
    
    # Eliminar el documento original de la carpeta DI después del chunking exitoso
    try:
        original_doc_path = Path("output_docs") / project_name / "DI" / f"{document_name}.json"
        if original_doc_path.exists():
            original_doc_path.unlink()
            logger.info(f"🗑️ Documento original eliminado después del chunking: {original_doc_path.name}")
        else:
            logger.warning(f"⚠️ No se encontró el documento original para eliminar: {original_doc_path}")
    except Exception as e:
        logger.error(f"❌ Error eliminando documento original {document_name}: {str(e)}")
    
    return chunking_result


def process_project_chunking(chunking_processor: ChunkingProcessor, 
                           project_name: str) -> Dict[str, Any]:
    """
    Procesa el chunking de todos los documentos de un proyecto.
    
    Args:
        chunking_processor: Instancia del procesador de chunking
        project_name: Nombre del proyecto
        
    Returns:
        Dict con resumen del chunking del proyecto
    """
    logger.info(f"📁 Procesando chunking para proyecto: {project_name}")
    
    # Buscar archivos JSON de Document Intelligence
    di_dir = Path("output_docs") / project_name / "DI"
    if not di_dir.exists():
        raise FileNotFoundError(f"Directorio DI no encontrado: {di_dir}")
    
    json_files = list(di_dir.glob("*.json"))
    logger.info(f"📊 Documentos encontrados para chunking: {len(json_files)}")
    
    chunking_summary = {
        'project_name': project_name,
        'total_documents': len(json_files),
        'documents_chunked': 0,
        'documents_no_chunking': 0,
        'total_chunks_created': 0,
        'chunking_results': [],
        'processing_timestamp': datetime.now().isoformat()
    }
    
    for json_file in json_files:
        try:
            # Cargar resultado de Document Intelligence
            with open(json_file, 'r', encoding='utf-8') as f:
                document_result = json.load(f)
            
            # Procesar chunking
            chunking_result = process_document_chunking(chunking_processor, document_result, project_name)
            
            if chunking_result:
                chunking_summary['documents_chunked'] += 1
                chunking_summary['total_chunks_created'] += len(chunking_result['chunks'])
                chunking_summary['chunking_results'].append({
                    'document': document_result['filename'],
                    'chunks_created': len(chunking_result['chunks']),
                    'saved_chunks': chunking_result['saved_chunks']
                })
            else:
                chunking_summary['documents_no_chunking'] += 1
                chunking_summary['chunking_results'].append({
                    'document': document_result['filename'],
                    'chunks_created': 0,
                    'note': 'No chunking required'
                })
                
        except Exception as e:
            logger.error(f"❌ Error procesando chunking para {json_file.name}: {str(e)}")
    
    logger.info(f"✅ Chunking completado - Documentos chunkeados: {chunking_summary['documents_chunked']}, Sin chunking: {chunking_summary['documents_no_chunking']}")
    return chunking_summary


# ============================================================================
# 4. PROCESAMIENTO CON AZURE OPENAI [PENDIENTE]
# ============================================================================

def setup_azure_openai() -> OpenAIProcessor:
    """
    Configuración de Azure OpenAI.
    
    Returns:
        OpenAIProcessor: Instancia configurada del procesador de OpenAI
    """
    logger.info("🔧 Configurando Azure OpenAI Processor...")
    
    processor = OpenAIProcessor()
    
    logger.info("✅ Azure OpenAI Processor configurado correctamente")
    return processor


def process_with_azure_openai(openai_processor: OpenAIProcessor, project_name: str):
    """
    Procesamiento con Azure OpenAI de todos los documentos y chunks de un proyecto.
    
    Args:
        openai_processor: Instancia del procesador de OpenAI
        project_name: Nombre del proyecto
    """
    logger.info(f"🤖 Iniciando procesamiento con Azure OpenAI para proyecto: {project_name}")
    
    # Procesar todos los documentos y chunks del proyecto
    results = openai_processor.process_project_documents(project_name)
    
    logger.info(f"✅ Procesamiento OpenAI completado:")
    logger.info(f"   📄 Documentos procesados: {results['summary']['total_documents']}")
    logger.info(f"   🧩 Chunks procesados: {results['summary']['total_chunks']}")
    logger.info(f"   🎯 Prompts ejecutados: {results['summary']['total_prompts_processed']}")
    logger.info(f"   📁 Proyecto: {results['project_name']}")
    
    return results


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """
    Función principal que ejecuta todo el flujo de procesamiento.
    """
    try:
        logger.info("🚀 Iniciando procesamiento completo de documentos")
        logger.info("=" * 60)
        
        # Configurar procesadores
        doc_processor = setup_document_intelligence()
        chunking_processor = setup_chunking_processor()
        openai_processor = setup_azure_openai()
        
        # Obtener lista de proyectos disponibles
        input_dir = Path("input_docs")
        if not input_dir.exists():
            raise FileNotFoundError("Directorio input_docs no encontrado")
        
        projects = [p.name for p in input_dir.iterdir() if p.is_dir()]
        logger.info(f"📁 Proyectos disponibles: {projects}")
        
        if not projects:
            logger.warning("⚠️  No se encontraron proyectos en input_docs")
            return
        
        # Procesar cada proyecto
        for project_name in projects:
            logger.info(f"\n🔄 Procesando proyecto: {project_name}")
            logger.info("-" * 40)
            
            try:
                # Etapa 1: Document Intelligence
                logger.info("📄 ETAPA 1: Procesamiento con Document Intelligence")
                di_summary = process_project_documents_with_custom_output(doc_processor, project_name)
                
                # Etapa 2: Chunking
                logger.info("\n📝 ETAPA 2: Procesamiento de Chunking")
                chunking_summary = process_project_chunking(chunking_processor, project_name)
                
                # Etapa 3: Azure OpenAI
                logger.info("\n🤖 ETAPA 3: Procesamiento con Azure OpenAI")
                openai_summary = process_with_azure_openai(openai_processor, project_name)
                
                logger.info(f"✅ Proyecto {project_name} procesado exitosamente")
                
            except Exception as e:
                logger.error(f"❌ Error procesando proyecto {project_name}: {str(e)}")
                continue
        
        logger.info("\n🎉 Procesamiento completo finalizado")
        
    except Exception as e:
        logger.error(f"❌ Error crítico en el procesamiento: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()