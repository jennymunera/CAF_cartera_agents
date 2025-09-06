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
    """
    Azure Function con Service Bus Trigger para procesar documentos y enviar batches a OpenAI.
    
    Esta función recibe mensajes del Service Bus que contienen información sobre documentos
    a procesar, los analiza usando Azure Document Intelligence, los divide en chunks y
    envía batches a OpenAI para análisis.
    
    Args:
        msg: Mensaje del Service Bus con información del documento a procesar
    """
    operation_id = generate_operation_id()
    
    try:
        # Obtener el mensaje del Service Bus
        message_body = msg.get_body().decode('utf-8')
        message_data = json.loads(message_body)
        
        logger.log_operation_start(
            operation_name="process_document_batch",
            operation_id=operation_id,
            message_data=message_data
        )
        
        # Validar datos del mensaje
        required_fields = ['project_name', 'document_name', 'document_type', 'queue_type']
        for field in required_fields:
            if field not in message_data:
                raise ValueError(f"Campo requerido '{field}' no encontrado en el mensaje")
        
        project_name = message_data['project_name']
        document_name = message_data['document_name']
        document_type = message_data['document_type']
        queue_type = message_data['queue_type']
        
        logger.info(f"Procesando documento: {document_name}, proyecto: {project_name}, tipo: {document_type}, cola: {queue_type}")
        
        # Configurar cliente de Blob Storage
        blob_client = BlobStorageClient()
        
        # Verificar que el documento existe en el blob storage
        if not blob_client.document_exists(project_name, document_name):
            raise ValueError(f"Documento {document_name} no encontrado en el proyecto {project_name}")
        
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
            processed_result = doc_processor.process_document(
                document_path=temp_document_path,
                document_type=document_type,
                operation_id=operation_id
            )
        finally:
            # Limpiar archivo temporal
            blob_client.cleanup_temp_file(temp_document_path)
        
        if not processed_result or 'chunks' not in processed_result:
            raise ValueError("No se pudieron generar chunks del documento")
        
        # Configurar OpenAI Batch Processor
        batch_processor = OpenAIBatchProcessor(
            operation_id=operation_id,
            document_type=document_type
        )
        
        # Enviar batch a OpenAI
        logger.log_document_processing(
            document_name=document_name,
            operation_id=operation_id,
            stage="openai_batch_submission"
        )
        
        batch_result = batch_processor.process_chunks(
            chunks=processed_result['chunks'],
            document_name=document_name,
            queue_type=queue_type
        )
        
        # Log del resultado exitoso
        logger.log_operation_end(
            operation_name="process_document_batch",
            operation_id=operation_id,
            success=True,
            batch_id=batch_result.get('batch_id'),
            document_name=document_name
        )
        
        logging.info(f"Documento procesado exitosamente. Batch ID: {batch_result.get('batch_id')}")
        
    except Exception as e:
        logger.log_error(
            message=f"Error procesando documento: {str(e)}",
            operation_id=operation_id,
            error_code="DOCUMENT_PROCESSING_ERROR",
            document_path=message_data.get('document_name', 'unknown')
        )
        
        logger.log_operation_end(
            operation_name="process_document_batch",
            operation_id=operation_id,
            success=False,
            error_message=str(e)
        )
        
        logging.error(f"Error en OpenAiProcess: {str(e)}")
        raise

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
        key=key
    )