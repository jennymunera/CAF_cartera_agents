import azure.functions as func
import logging
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import AzureOpenAI

# Agregar el directorio padre al path para importar los módulos locales
sys.path.append(str(Path(__file__).parent))

# Importar utilidades locales
from utils.app_insights_logger import get_logger, generate_operation_id
from utils.blob_storage_client import BlobStorageClient

# Cargar variables de entorno
load_dotenv()

# Configurar logger
logger = get_logger("PoolingProcess")

def main(mytimer: func.TimerRequest) -> None:
    """
    Azure Function con Timer Trigger que se ejecuta cada 5 minutos para verificar
    el estado de los batches de OpenAI y procesar los resultados completados.
    
    Args:
        mytimer: Objeto TimerRequest de Azure Functions
    """
    operation_id = generate_operation_id()
    
    try:
        logger.log_operation_start(
            operation_name="batch_polling_check",
            operation_id=operation_id,
            timer_info={
                "is_past_due": mytimer.past_due,
                "schedule_status": str(mytimer.schedule_status) if mytimer.schedule_status else None
            }
        )
        
        if mytimer.past_due:
            logger.warning(f"Timer trigger ejecutado tarde. Operation ID: {operation_id}")
        
        # Inicializar el procesador de resultados de batch
        batch_processor = BatchResultsProcessor(operation_id=operation_id)
        
        # Verificar batches pendientes
        pending_batches = batch_processor.get_pending_batches()
        
        if not pending_batches:
            logger.info("No hay batches pendientes para procesar")
            logger.log_operation_end(
                operation_name="batch_polling_check",
                operation_id=operation_id,
                success=True,
                batches_processed=0
            )
            return
        
        logger.info(f"Encontrados {len(pending_batches)} batches pendientes")
        
        processed_count = 0
        completed_count = 0
        
        # Procesar cada batch pendiente
        for batch_info in pending_batches:
            try:
                batch_id = batch_info.get('batch_id')
                if not batch_id:
                    continue
                
                logger.log_batch_operation(
                    batch_id=batch_id,
                    operation_id=operation_id,
                    status="checking"
                )
                
                # Verificar estado del batch
                batch_status = batch_processor.check_batch_status(batch_id)
                
                if batch_status == 'completed':
                    # Procesar resultados del batch completado
                    results = batch_processor.process_completed_batch(
                        batch_id=batch_id,
                        batch_info=batch_info
                    )
                    
                    if results:
                        completed_count += 1
                        logger.log_batch_operation(
                            batch_id=batch_id,
                            operation_id=operation_id,
                            status="completed_and_processed",
                            results_count=len(results.get('processed_results', []))
                        )
                
                processed_count += 1
                
            except Exception as batch_error:
                logger.log_error(
                    message=f"Error procesando batch {batch_info.get('batch_id', 'unknown')}: {str(batch_error)}",
                    operation_id=operation_id,
                    error_code="BATCH_PROCESSING_ERROR",
                    batch_id=batch_info.get('batch_id')
                )
                continue
        
        # Log del resultado final
        logger.log_operation_end(
            operation_name="batch_polling_check",
            operation_id=operation_id,
            success=True,
            batches_processed=processed_count,
            batches_completed=completed_count
        )
        
        logging.info(f"Polling completado. Procesados: {processed_count}, Completados: {completed_count}")
        
    except Exception as e:
        logger.log_error(
            message=f"Error en PoolingProcess: {str(e)}",
            operation_id=operation_id,
            error_code="POLLING_PROCESS_ERROR"
        )
        
        logger.log_operation_end(
            operation_name="batch_polling_check",
            operation_id=operation_id,
            success=False,
            error_message=str(e)
        )
        
        logging.error(f"Error en PoolingProcess: {str(e)}")
        raise

class BatchResultsProcessor:
    """
    Procesador de resultados de batches de OpenAI basado en la lógica de results.py
    """
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.logger = get_logger("BatchResultsProcessor")
        self.client = self._setup_client()
        self.blob_client = BlobStorageClient()
        
    def _setup_client(self) -> AzureOpenAI:
        """
        Configura el cliente de Azure OpenAI
        """
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
        
        if not api_key or not endpoint:
            raise ValueError("Faltan credenciales de Azure OpenAI")
        
        return AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
    
    def get_pending_batches(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de batches pendientes desde el almacenamiento
        
        Returns:
            Lista de información de batches pendientes
        """
        try:
            # Aquí se implementaría la lógica para obtener batches pendientes
            # desde Azure Storage, Cosmos DB, o el sistema de almacenamiento usado
            
            # Por ahora, obtenemos todos los batches y filtramos los pendientes
            batches = self.client.batches.list(limit=100)
            
            pending_batches = []
            for batch in batches.data:
                if batch.status in ['validating', 'in_progress', 'finalizing']:
                    pending_batches.append({
                        'batch_id': batch.id,
                        'status': batch.status,
                        'created_at': batch.created_at,
                        'metadata': batch.metadata
                    })
            
            return pending_batches
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error obteniendo batches pendientes: {str(e)}",
                operation_id=self.operation_id,
                error_code="GET_PENDING_BATCHES_ERROR"
            )
            return []
    
    def check_batch_status(self, batch_id: str) -> str:
        """
        Verifica el estado de un batch específico
        
        Args:
            batch_id: ID del batch a verificar
            
        Returns:
            Estado del batch
        """
        try:
            batch = self.client.batches.retrieve(batch_id)
            return batch.status
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error verificando estado del batch {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code="CHECK_BATCH_STATUS_ERROR",
                batch_id=batch_id
            )
            return 'error'
    
    def process_completed_batch(self, batch_id: str, batch_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Procesa un batch completado y descarga sus resultados
        
        Args:
            batch_id: ID del batch completado
            batch_info: Información adicional del batch
            
        Returns:
            Resultados procesados del batch
        """
        try:
            # Descargar resultados del batch
            batch = self.client.batches.retrieve(batch_id)
            
            if not batch.output_file_id:
                self.logger.warning(f"Batch {batch_id} completado pero sin archivo de salida")
                return None
            
            # Descargar archivo de resultados
            result_file_response = self.client.files.content(batch.output_file_id)
            result_content = result_file_response.content
            
            # Procesar contenido del archivo
            results = self._process_batch_results(result_content.decode('utf-8'), batch_id)
            
            # Guardar resultados procesados
            self._save_processed_results(results, batch_id, batch_info)
            
            return results
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error procesando batch completado {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code="PROCESS_COMPLETED_BATCH_ERROR",
                batch_id=batch_id
            )
            return None
    
    def _process_batch_results(self, content: str, batch_id: str) -> Dict[str, Any]:
        """
        Procesa el contenido de los resultados del batch
        
        Args:
            content: Contenido del archivo de resultados
            batch_id: ID del batch
            
        Returns:
            Resultados procesados
        """
        processed_results = []
        errors = []
        
        for line in content.strip().split('\n'):
            if not line.strip():
                continue
                
            try:
                result = json.loads(line)
                
                if result.get('error'):
                    errors.append(result)
                else:
                    processed_results.append(result)
                    
            except json.JSONDecodeError as e:
                errors.append({
                    'error': f"Error parsing JSON: {str(e)}",
                    'line': line
                })
        
        return {
            'batch_id': batch_id,
            'processed_results': processed_results,
            'errors': errors,
            'total_results': len(processed_results),
            'total_errors': len(errors),
            'processed_at': datetime.now().isoformat()
        }
    
    def _save_processed_results(self, results: Dict[str, Any], batch_id: str, batch_info: Dict[str, Any]) -> None:
        """
        Guarda los resultados procesados en Azure Blob Storage
        
        Args:
            results: Resultados procesados
            batch_id: ID del batch
            batch_info: Información del batch
        """
        try:
            # Extraer información del proyecto desde batch_info
            project_name = batch_info.get('project_name')
            document_name = batch_info.get('document_name')
            
            if not project_name or not document_name:
                raise ValueError(f"Información de proyecto faltante en batch_info para batch {batch_id}")
            
            # Crear nombre de archivo para los resultados
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_filename = f"{document_name}_{batch_id}_{timestamp}_results.json"
            
            # Guardar resultados en la carpeta results/ del proyecto
            self.blob_client.save_results(
                project_name=project_name,
                filename=results_filename,
                content=json.dumps(results, indent=2, ensure_ascii=False)
            )
            
            self.logger.log_batch_operation(
                batch_id=batch_id,
                operation_id=self.operation_id,
                status="results_saved",
                results_count=results.get('total_results', 0),
                errors_count=results.get('total_errors', 0)
            )
            
            self.logger.info(f"Resultados guardados en Blob Storage para batch {batch_id}: {results.get('total_results', 0)} resultados, {results.get('total_errors', 0)} errores. Archivo: {results_filename}")
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error guardando resultados del batch {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code="SAVE_RESULTS_ERROR",
                batch_id=batch_id
            )