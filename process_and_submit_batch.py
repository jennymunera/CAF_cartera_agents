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
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Importar procesadores locales
from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor
from openai_batch_processor import OpenAIBatchProcessor
from utils.app_insights_logger import get_logger, generate_operation_id
from utils.blob_storage_client import BlobStorageClient

# Cargar variables de entorno
load_dotenv()

# Configurar logging con Azure Application Insights
logger = get_logger('main_processor')


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
                                              project_name: str,
                                              document_name: str,
                                              blob_client: BlobStorageClient) -> tuple[Dict[str, Any], bool]:
    """
    Procesa un documento individual desde Azure Blob Storage y guarda el resultado en la estructura personalizada.
    
    Args:
        processor: Instancia del procesador de Document Intelligence
        project_name: Nombre del proyecto
        document_name: Nombre del documento a procesar
        blob_client: Cliente de Azure Blob Storage
        
    Returns:
        Tuple con (Dict con los resultados del procesamiento, bool indicando si fue saltado)
    """
    logger.info(f"📄 Procesando documento: {document_name}")
    
    # Verificar si el documento ya está procesado
    document_stem = Path(document_name).stem
    output_base = Path("output_docs") / project_name / "DI"
    output_file = output_base / f"{document_stem}.json"
    
    if output_file.exists():
        logger.info(f"⏭️ Documento ya procesado, saltando: {document_name}")
        # Cargar desde archivo DI
        with open(output_file, 'r', encoding='utf-8') as f:
            result = json.load(f)
        return result, True  # True indica que fue saltado
    
    # Verificar si ya está chunkeado
    chunks_dir = Path("output_docs") / project_name / "chunks"
    if chunks_dir.exists():
        chunk_files = list(chunks_dir.glob(f"{document_stem}_chunk_*.json"))
        if chunk_files:
            logger.info(f"⏭️ Documento ya chunkeado, saltando: {document_name}")
            result = {
                "metadata": {
                    "processing_status": "chunked_only",
                    "document_name": document_name,
                    "processed_date": datetime.now().isoformat()
                },
                "content": "Document already chunked - no DI processing needed"
            }
            return result, True  # True indica que fue saltado
    
    # Descargar documento desde Blob Storage
    temp_file_path = blob_client.download_document(project_name, document_name)
    
    try:
        # Procesar documento
        result = processor.process_single_document(Path(temp_file_path))
        
        # Crear estructura de directorios personalizada
        output_base.mkdir(parents=True, exist_ok=True)
        
        # Guardar resultado en formato JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Resultado guardado: {output_file}")
        return result, False  # False indica que fue procesado
        
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def process_project_documents_with_custom_output(processor: DocumentIntelligenceProcessor, 
                                                project_name: str,
                                                blob_client: BlobStorageClient) -> Dict[str, Any]:
    """
    Procesa todos los documentos de un proyecto desde Azure Blob Storage y guarda cada uno individualmente.
    
    Args:
        processor: Instancia del procesador de Document Intelligence
        project_name: Nombre del proyecto a procesar
        blob_client: Cliente de Azure Blob Storage
        
    Returns:
        Dict con resumen del procesamiento del proyecto
    """
    logger.info(f"📁 Procesando proyecto: {project_name}")
    
    # Obtener lista de documentos del proyecto desde Blob Storage
    all_documents = blob_client.list_documents(project_name)
    
    if not all_documents:
        logger.info(f"📊 No se encontraron documentos en el proyecto: {project_name}")
        return {
            'project_name': project_name,
            'total_documents': 0,
            'successful_documents': 0,
            'skipped_documents': 0,
            'failed_documents': 0,
            'processed_documents': [],
            'processing_timestamp': datetime.now().isoformat()
        }
    
    # Filtrar por prefijos requeridos
    required_prefixes = ['Auditoria', 'Desembolsos', 'Productos']
    filtered_documents = []
    
    for doc_name in all_documents:
        if any(doc_name.startswith(prefix) for prefix in required_prefixes):
            filtered_documents.append(doc_name)
    
    logger.info(f"📊 Documentos encontrados: {len(all_documents)} total, {len(filtered_documents)} con prefijos requeridos")
    
    # Procesar cada documento individualmente
    processed_documents = []
    successful_count = 0
    failed_count = 0
    skipped_count = 0
    
    for doc_name in filtered_documents:
        try:
            result, was_skipped = process_single_document_with_custom_output(processor, project_name, doc_name, blob_client)
            
            if was_skipped:
                processed_documents.append({
                    'filename': doc_name,
                    'status': 'skipped',
                    'content_length': len(result['content']),
                    'metadata': result['metadata']
                })
                skipped_count += 1
            else:
                processed_documents.append({
                    'filename': doc_name,
                    'status': 'success',
                    'content_length': len(result['content']),
                    'metadata': result['metadata']
                })
                successful_count += 1
            
        except Exception as e:
            logger.error(f"❌ Error procesando {doc_name}: {str(e)}")
            processed_documents.append({
                'filename': doc_name,
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

def setup_azure_openai_batch() -> OpenAIBatchProcessor:
    """
    Configura y retorna una instancia del procesador de Azure OpenAI Batch.
    
    Returns:
        OpenAIBatchProcessor: Instancia configurada del procesador batch
    """
    logger.info("🔧 Configurando Azure OpenAI Batch Processor...")
    
    processor = OpenAIBatchProcessor()
    
    logger.info("✅ Azure OpenAI Batch Processor configurado correctamente")
    return processor


def create_batch_job(batch_processor: OpenAIBatchProcessor, project_name: str):
    """
    Crea un batch job para procesar todos los documentos y chunks de un proyecto.
    
    Args:
        batch_processor: Instancia del procesador batch de OpenAI
        project_name: Nombre del proyecto
    """
    logger.info(f"🤖 Creando batch job para proyecto: {project_name}")
    
    # Crear batch job con todos los documentos y chunks del proyecto
    batch_info = batch_processor.create_batch_job(project_name)
    
    logger.info(f"✅ Batch job creado exitosamente:")
    logger.info(f"   📋 Batch ID: {batch_info['batch_id']}")
    logger.info(f"   📊 Total requests: {batch_info['total_requests']}")
    logger.info(f"   📁 Proyecto: {batch_info['project_name']}")
    logger.info(f"   📄 Archivo info: batch_info_{project_name}_{batch_info['batch_id']}.json")
    logger.info(f"")
    logger.info(f"🔄 Para procesar los resultados cuando estén listos, ejecuta:")
    logger.info(f"   python results.py {batch_info['batch_id']} {project_name}")
    
    return batch_info


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """
    Función principal que ejecuta todo el flujo de procesamiento.
    """
    operation_id = generate_operation_id()
    logger.log_operation_start(
        operation_name="document_processing_pipeline",
        operation_id=operation_id,
        description="Procesamiento completo de documentos con Document Intelligence, Chunking y OpenAI Batch"
    )
    
    try:
        logger.info("🚀 Iniciando procesamiento completo de documentos")
        logger.info("=" * 60)
        
        # Configurar procesadores
        doc_processor = setup_document_intelligence()
        chunking_processor = setup_chunking_processor()
        batch_processor = setup_azure_openai_batch()
        
        # Configurar cliente de Blob Storage
        blob_client = BlobStorageClient()
        
        # Obtener lista de proyectos disponibles desde Blob Storage
        projects = blob_client.list_projects()
        logger.info(
            f"📁 Proyectos disponibles en Blob Storage: {projects}",
            projects=projects,
            project_count=len(projects),
            operation_id=operation_id
        )
        
        if not projects:
            logger.warning("⚠️  No se encontraron proyectos en el Blob Storage")
            return
        
        # Procesar cada proyecto
        for project_name in projects:
            project_operation_id = generate_operation_id()
            logger.log_operation_start(
                operation_name="process_project",
                operation_id=project_operation_id,
                description=f"Procesamiento completo del proyecto {project_name}",
                parent_operation_id=operation_id
            )
            
            logger.info(f"\n🔄 Procesando proyecto: {project_name}")
            logger.info("-" * 40)
            
            try:
                # Etapa 1: Document Intelligence
                logger.info("📄 ETAPA 1: Procesamiento con Document Intelligence")
                di_summary = process_project_documents_with_custom_output(doc_processor, project_name, blob_client)
                
                # Etapa 2: Chunking
                logger.info("\n📝 ETAPA 2: Procesamiento de Chunking")
                chunking_summary = process_project_chunking(chunking_processor, project_name)
                
                # Etapa 3: Crear Batch Job
                logger.info("\n🤖 ETAPA 3: Creación de Batch Job")
                batch_info = create_batch_job(batch_processor, project_name)
                
                logger.log_operation_end(
                    operation_name="project_processing",
                    operation_id=project_operation_id,
                    success=True,
                    result_summary={
                        "document_intelligence": di_summary,
                        "chunking": chunking_summary,
                        "batch_job": batch_info
                    }
                )
                logger.info(f"✅ Proyecto {project_name} procesado exitosamente")
                
            except Exception as e:
                logger.log_operation_end(
                    operation_name="project_processing",
                    operation_id=project_operation_id,
                    success=False,
                    error_message=str(e)
                )
                logger.log_error(
                    message=f"Error procesando proyecto {project_name}: {str(e)}",
                    operation_id=operation_id,
                    error_type=type(e).__name__,
                    additional_properties={"project_name": project_name}
                )
                continue
        
        logger.log_operation_end(
            operation_name="document_processing_pipeline",
            operation_id=operation_id,
            success=True,
            result_summary={"processed_projects": len(projects)}
        )
        logger.info("\n🎉 Procesamiento completo finalizado")
        
    except Exception as e:
        logger.log_operation_end(
            operation_name="document_processing_pipeline",
            operation_id=operation_id,
            success=False,
            error_message=str(e)
        )
        logger.log_error(
            message=f"Error crítico en el procesamiento: {str(e)}",
            operation_id=operation_id,
            error_type=type(e).__name__
        )
        sys.exit(1)


if __name__ == "__main__":
    main()