import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import openai
import sys

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor
from openai_processor import OpenAIProcessor


def main(msg: func.ServiceBusMessage) -> None:
    """
    Azure Function con Service Bus trigger para procesamiento de documentos.
    
    Estructura del mensaje esperado:
    {
        "projectName": "nombre_del_proyecto",
        "requestId": "uuid-unico",
        "timestamp": "2024-01-15T10:30:00Z",
        "documents": ["doc1.pdf", "doc2.pdf"],  # Opcional, si no se especifica procesa todos
        "processingSteps": ["DI", "chunking", "openai"]  # Opcional, por defecto todos
    }
    """
    
    logging.info('🚀 Azure Function OpenAiProcess_local iniciada')
    
    try:
        # Decodificar mensaje del Service Bus
        message_body = msg.get_body().decode('utf-8')
        message_data = json.loads(message_body)
        
        logging.info(f"📨 Mensaje recibido: {message_data}")
        
        # Validar estructura del mensaje
        project_name = message_data.get('projectName')
        request_id = message_data.get('requestId', 'unknown')
        
        if not project_name:
            raise ValueError("El campo 'projectName' es requerido en el mensaje")
        
        logging.info(f"🔄 Procesando proyecto: {project_name} (Request ID: {request_id})")
        
        # Configurar procesadores
        doc_processor = setup_document_intelligence()
        chunking_processor = setup_chunking_processor()
        openai_processor = setup_azure_openai()
        
        # Configurar cliente de Blob Storage
        blob_service_client = BlobServiceClient(
            account_url=f"https://{os.environ['AZURE_STORAGE_ACCOUNT']}.blob.core.windows.net",
            credential=os.environ['AZURE_STORAGE_KEY']
        )
        
        # Obtener pasos de procesamiento
        processing_steps = message_data.get('processingSteps', ['DI', 'chunking', 'openai'])
        
        # Procesar según los pasos especificados
        results = {}
        
        if 'DI' in processing_steps:
            logging.info("📄 ETAPA 1: Procesamiento con Document Intelligence")
            di_result = process_document_intelligence(
                doc_processor, blob_service_client, project_name, message_data.get('documents')
            )
            results['document_intelligence'] = di_result
        
        if 'chunking' in processing_steps:
            logging.info("📝 ETAPA 2: Procesamiento de Chunking")
            chunking_result = process_chunking(
                chunking_processor, blob_service_client, project_name
            )
            results['chunking'] = chunking_result
        
        if 'openai' in processing_steps:
            logging.info("🤖 ETAPA 3: Procesamiento con Azure OpenAI")
            openai_result = process_openai(
                openai_processor, blob_service_client, project_name
            )
            results['openai'] = openai_result
        
        # Guardar resumen final
        save_processing_summary(blob_service_client, project_name, request_id, results)
        
        logging.info(f"✅ Proyecto {project_name} procesado exitosamente")
        
    except Exception as e:
        logging.error(f"❌ Error procesando mensaje: {str(e)}")
        # En un entorno de producción, aquí podrías enviar el mensaje a una cola de errores
        raise


def setup_document_intelligence() -> DocumentIntelligenceProcessor:
    """Configurar procesador de Document Intelligence."""
    return DocumentIntelligenceProcessor(
        endpoint=os.environ['AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'],
        key=os.environ['AZURE_DOCUMENT_INTELLIGENCE_KEY']
    )


def setup_chunking_processor() -> ChunkingProcessor:
    """Configurar procesador de chunking."""
    return ChunkingProcessor()


def setup_azure_openai() -> OpenAIProcessor:
    """Configurar procesador de Azure OpenAI."""
    return OpenAIProcessor(
        api_key=os.environ['AZURE_OPENAI_API_KEY'],
        endpoint=os.environ['AZURE_OPENAI_ENDPOINT'],
        api_version=os.environ['AZURE_OPENAI_API_VERSION'],
        deployment_name=os.environ['AZURE_OPENAI_DEPLOYMENT_NAME']
    )


def process_document_intelligence(
    processor: DocumentIntelligenceProcessor,
    blob_client: BlobServiceClient,
    project_name: str,
    specific_documents: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Procesar documentos con Document Intelligence desde Blob Storage."""
    
    container_name = "caf-documents"
    raw_path = f"basedocuments/{project_name}/raw/"
    processed_path = f"basedocuments/{project_name}/processed/DI/"
    
    # Listar documentos en la carpeta raw
    container_client = blob_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=raw_path)
    
    processed_count = 0
    errors = []
    
    for blob in blobs:
        if blob.name.endswith('.pdf'):
            document_name = os.path.basename(blob.name)
            
            # Si se especificaron documentos específicos, filtrar
            if specific_documents and document_name not in specific_documents:
                continue
            
            try:
                logging.info(f"📄 Procesando documento: {document_name}")
                
                # Descargar blob
                blob_client_doc = blob_client.get_blob_client(
                    container=container_name, blob=blob.name
                )
                blob_data = blob_client_doc.download_blob().readall()
                
                # Procesar con Document Intelligence
                result = processor.process_document_from_bytes(blob_data, document_name)
                
                # Guardar resultado en processed/DI/
                result_name = f"{os.path.splitext(document_name)[0]}.json"
                result_blob_name = f"{processed_path}{result_name}"
                
                result_blob_client = blob_client.get_blob_client(
                    container=container_name, blob=result_blob_name
                )
                result_blob_client.upload_blob(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    overwrite=True
                )
                
                processed_count += 1
                logging.info(f"✅ Documento {document_name} procesado y guardado")
                
            except Exception as e:
                error_msg = f"Error procesando {document_name}: {str(e)}"
                logging.error(error_msg)
                errors.append(error_msg)
    
    return {
        "processed_documents": processed_count,
        "errors": errors,
        "timestamp": datetime.now().isoformat()
    }


def process_chunking(
    processor: ChunkingProcessor,
    blob_client: BlobServiceClient,
    project_name: str
) -> Dict[str, Any]:
    """Procesar chunking desde Blob Storage."""
    
    container_name = "caf-documents"
    di_path = f"basedocuments/{project_name}/processed/DI/"
    chunks_path = f"basedocuments/{project_name}/processed/chunks/"
    
    container_client = blob_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=di_path)
    
    processed_count = 0
    errors = []
    
    for blob in blobs:
        if blob.name.endswith('.json'):
            try:
                # Descargar resultado de DI
                blob_client_doc = blob_client.get_blob_client(
                    container=container_name, blob=blob.name
                )
                di_result = json.loads(blob_client_doc.download_blob().readall())
                
                # Procesar chunking
                chunks_result = processor.process_document_chunking(di_result)
                
                if chunks_result and 'chunks' in chunks_result:
                    # Guardar chunks individuales
                    document_name = os.path.splitext(os.path.basename(blob.name))[0]
                    
                    for i, chunk in enumerate(chunks_result['chunks']):
                        chunk_name = f"{document_name}_chunk_{i+1:03d}.json"
                        chunk_blob_name = f"{chunks_path}{chunk_name}"
                        
                        chunk_blob_client = blob_client.get_blob_client(
                            container=container_name, blob=chunk_blob_name
                        )
                        chunk_blob_client.upload_blob(
                            json.dumps(chunk, indent=2, ensure_ascii=False),
                            overwrite=True
                        )
                
                processed_count += 1
                
            except Exception as e:
                error_msg = f"Error en chunking {blob.name}: {str(e)}"
                logging.error(error_msg)
                errors.append(error_msg)
    
    return {
        "processed_documents": processed_count,
        "errors": errors,
        "timestamp": datetime.now().isoformat()
    }


def process_openai(
    processor: OpenAIProcessor,
    blob_client: BlobServiceClient,
    project_name: str
) -> Dict[str, Any]:
    """Procesar con Azure OpenAI desde Blob Storage."""
    
    try:
        # Usar el método existente del procesador adaptado para blob storage
        result = processor.process_project_documents_from_blob(
            blob_client, project_name
        )
        
        # Guardar resultados finales en results/
        container_name = "caf-documents"
        results_path = f"basedocuments/{project_name}/results/"
        
        # Guardar resumen de procesamiento
        summary_blob_name = f"{results_path}processing_summary.json"
        summary_blob_client = blob_client.get_blob_client(
            container=container_name, blob=summary_blob_name
        )
        summary_blob_client.upload_blob(
            json.dumps(result, indent=2, ensure_ascii=False),
            overwrite=True
        )
        
        return result
        
    except Exception as e:
        logging.error(f"Error en procesamiento OpenAI: {str(e)}")
        raise


def save_processing_summary(
    blob_client: BlobServiceClient,
    project_name: str,
    request_id: str,
    results: Dict[str, Any]
) -> None:
    """Guardar resumen final del procesamiento."""
    
    summary = {
        "project_name": project_name,
        "request_id": request_id,
        "processing_timestamp": datetime.now().isoformat(),
        "results": results,
        "status": "completed"
    }
    
    container_name = "caf-documents"
    summary_blob_name = f"basedocuments/{project_name}/results/final_summary_{request_id}.json"
    
    summary_blob_client = blob_client.get_blob_client(
        container=container_name, blob=summary_blob_name
    )
    summary_blob_client.upload_blob(
        json.dumps(summary, indent=2, ensure_ascii=False),
        overwrite=True
    )
    
    logging.info(f"📊 Resumen final guardado: {summary_blob_name}")