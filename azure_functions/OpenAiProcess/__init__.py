import azure.functions as func
import logging
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
# Agregar el directorio padre al path para importar los módulos locales
sys.path.append(str(Path(__file__).parent))

# Importar procesadores locales
from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor
from openai_batch_processor import OpenAIBatchProcessor
from utils.app_insights_logger import get_logger, generate_operation_id
from utils.blob_storage_client import BlobStorageClient

# Configurar logger
logger = get_logger("OpenAiProcess")

def main(msg: func.ServiceBusMessage) -> None:
    """Main Service Bus trigger function."""
    try:
        # Parse message body
        message_body = msg.get_body().decode('utf-8')
        message_data = json.loads(message_body)
        
        logger.info(f"Received message: {message_data}")
        
        # Validate required fields
        required_fields = ['project_name', 'queue_type']
        for field in required_fields:
            if field not in message_data:
                logger.error(f"Missing required field: {field}")
                return
        
        project_name = message_data['project_name']
        queue_type = message_data['queue_type']
        
        logger.info(f"Processing project: {project_name}, queue_type: {queue_type}")
        
        # Always process entire project (no individual document processing)
        logger.info(f"Processing complete project: {project_name}")
        process_complete_project(project_name, queue_type)
            
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing message JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

def process_single_document(project_name: str, document_name: str, document_type: str, operation_id: str):
    """
    Procesa un documento específico
    """
    # Configurar cliente de Blob Storage
    blob_client = BlobStorageClient()
    
    # Verificar que el documento existe en el blob storage
    if not blob_client.document_exists(project_name, document_name):
        logger.error(f"Documento {document_name} no encontrado en el proyecto {project_name}")
        logger.error(f"Verificar que el documento existe en la ruta: {project_name}/{document_name}")
        raise FileNotFoundError(f"Documento {document_name} no encontrado en el proyecto {project_name}")
    
    # Crear archivo temporal del documento desde blob storage
    temp_document_path = blob_client.create_temp_file_from_blob(project_name, document_name)
    
    # Configurar Document Intelligence
    doc_processor = setup_document_intelligence()
    
    # Procesar documento
    logger.log_document_processing(
        document_name=document_name,
        operation_id=operation_id,
        stage="document_intelligence_processing"
    )
    
    try:
        processed_result = doc_processor.process_single_document(
            file_path=temp_document_path
        )
    finally:
        # Limpiar archivo temporal
        blob_client.cleanup_temp_file(temp_document_path)
    
    if not processed_result or 'content' not in processed_result:
        raise ValueError("No se pudo procesar el documento")
    
    # Generar chunks del contenido procesado
    chunking_processor = ChunkingProcessor(max_tokens=100000, generate_jsonl=True)
    chunks_result = chunking_processor.process_document_content(
        content=processed_result['content'],
        project_name=project_name
    )
    
    if not chunks_result or 'chunks' not in chunks_result:
        raise ValueError("No se pudieron generar chunks del documento")
    
    # Configurar OpenAI Batch Processor
    batch_processor = OpenAIBatchProcessor()
    
    # Enviar batch a OpenAI
    logger.log_document_processing(
        document_name=document_name,
        operation_id=operation_id,
        stage="openai_batch_submission"
    )
    
    batch_result = batch_processor.process_chunks(
        chunks=chunks_result['chunks'],
        document_name=document_name,
        queue_type="processing"
    )
    
    logging.info(f"Documento {document_name} procesado exitosamente. Batch ID: {batch_result.get('batch_id')}")

def process_complete_project(project_name: str, queue_type: str):
    """
    Process complete project following the correct workflow:
    1. Document Intelligence processing from raw documents
    2. Chunking if needed
    3. OpenAI batch processing for entire project
    """
    try:
        logger.info(f"Starting complete project processing for: {project_name}")
        
        # Initialize blob storage client
        blob_client = BlobStorageClient()
        
        # Step 1: Document Intelligence Processing
        logger.info("Step 1: Document Intelligence processing...")
        
        # Setup Document Intelligence processor
        di_endpoint = os.environ.get('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
        di_key = os.environ.get('AZURE_DOCUMENT_INTELLIGENCE_KEY')
        
        if not di_endpoint or not di_key:
            raise ValueError("Document Intelligence credentials not configured")
        
        di_processor = DocumentIntelligenceProcessor(
            endpoint=di_endpoint,
            api_key=di_key,
            auto_chunk=True,
            max_tokens=100000
        )
        
        # Process all project documents using blob storage
        processing_result = di_processor.process_project_documents(project_name)
        
        if not processing_result or processing_result['metadata']['successful_documents'] == 0:
            logger.warning(f"No new documents processed for project: {project_name}")
        else:
            logger.info(f"Document Intelligence processing completed for project: {project_name}")
        
        # Continue with chunking and batch processing even if no new documents were processed
        
        # Step 2: Check if chunking is needed and process
        logger.info("Step 2: Checking if chunking is needed...")
        
        # Get concatenated content from all processed documents
        blob_client = BlobStorageClient()
        concatenated_content = ""
        
        # Get list of successfully processed documents from the result
        newly_processed_documents = processing_result.get('processed_documents', [])
        
        # Also get all existing DI processed documents that might need chunking
        container_name = "caf-documents"
        prefix = f"basedocuments/{project_name}/processed/DI/"
        
        try:
            blobs = blob_client.blob_service_client.get_container_client(container_name).list_blobs(name_starts_with=prefix)
            existing_di_documents = []
            for blob in blobs:
                if blob.name.endswith('.json'):
                    # Extract just the filename without path and extension
                    filename = blob.name.split('/')[-1].replace('.json', '')
                    existing_di_documents.append(filename)
            
            # Combine newly processed and existing documents, removing duplicates
            all_documents = list(set(newly_processed_documents + existing_di_documents))
            logger.info(f"Found {len(newly_processed_documents)} newly processed documents and {len(existing_di_documents)} existing DI documents")
            logger.info(f"Total documents to check for chunking: {len(all_documents)}")
            
        except Exception as e:
            logger.error(f"Error getting existing DI documents: {str(e)}")
            all_documents = newly_processed_documents
        
        # Process each document individually for chunking to maintain document names
        chunking_processor = ChunkingProcessor(
            max_tokens=100000,
            overlap_tokens=500
        )
        
        all_saved_files = []
        total_chunks_created = 0
        
        for doc_name in all_documents:
            try:
                # Check if document was already chunked
                if chunking_processor.is_document_already_chunked(doc_name, project_name):
                    logger.info(f"Document already chunked, skipping: {doc_name}")
                    continue
                
                doc_data = blob_client.load_processed_document(project_name, "DI", f"{doc_name}.json")
                if doc_data and 'content' in doc_data:
                    logger.info(f"Processing document for chunking: {doc_name}")
                    
                    # Process individual document content for chunking
                    chunking_result = chunking_processor.process_document_content(doc_data['content'], project_name)
                    
                    # Save chunks to blob storage if chunking is required
                    if chunking_result.get('requires_chunking', False):
                        saved_files = chunking_processor.save_chunks_to_blob_with_doc_name(chunking_result, project_name, doc_name)
                        all_saved_files.extend(saved_files)
                        total_chunks_created += len(chunking_result['chunks'])
                        logger.info(f"Document {doc_name} chunked into {len(chunking_result['chunks'])} chunks")
                    else:
                        logger.info(f"Document {doc_name} within token limit. No chunking required.")
                        
            except Exception as e:
                logger.warning(f"Could not process document {doc_name} for chunking: {str(e)}")
        
        if total_chunks_created > 0:
            logger.info(f"Chunking processing completed for project: {project_name}. Created {total_chunks_created} chunks across {len(all_saved_files)} files.")
        else:
            logger.info(f"No chunking needed for project: {project_name} (all documents within token limits)")
        
        # Step 3: OpenAI Batch Processing
        logger.info("Step 3: Creating OpenAI batch job for entire project...")
        
        # Initialize OpenAI batch processor
        batch_processor = OpenAIBatchProcessor()
        
        # Create batch job for the entire project using blob storage
        batch_info = batch_processor.create_batch_job(project_name)
        
        if batch_info and 'batch_id' in batch_info:
            logger.info(f"Batch job created successfully. Batch ID: {batch_info['batch_id']}")
            logger.info(f"Total requests in batch: {batch_info.get('total_requests', 'unknown')}")
        else:
            logger.error("Failed to create batch job")
        
        logger.info(f"Completed processing project: {project_name}")
        
    except Exception as e:
        logger.error(f"Error in process_complete_project: {str(e)}")
        raise

def determine_document_type(document_name: str) -> str:
    """
    Determina el tipo de documento basado en su nombre
    """
    document_name_lower = document_name.lower()
    
    if 'auditor' in document_name_lower or 'ixp' in document_name_lower:
        return 'Auditoria'
    elif 'desembolso' in document_name_lower or 'des' in document_name_lower:
        return 'Desembolsos'
    elif 'producto' in document_name_lower or 'prd' in document_name_lower:
        return 'Productos'
    else:
        return 'Auditoria'  # Tipo por defecto

def setup_document_intelligence() -> DocumentIntelligenceProcessor:
    """
    Configura y retorna una instancia del procesador de Document Intelligence.
    
    Returns:
        DocumentIntelligenceProcessor: Instancia configurada del procesador
    """
    endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    if not endpoint or not key:
        raise ValueError("Faltan credenciales de Azure Document Intelligence")
    
    return DocumentIntelligenceProcessor(
        endpoint=endpoint,
        api_key=key,
        auto_chunk=False  # Disable auto chunking - we handle chunking per document in main logic
    )