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

# Agregar el directorio padre al path para importar los módulos compartidos
sys.path.append(str(Path(__file__).parent.parent))

# Importar utilidades desde shared_code
from shared_code.utils.app_insights_logger import get_logger, generate_operation_id
from shared_code.utils.blob_storage_client import BlobStorageClient

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
        Configura el cliente de Azure OpenAI usando el mismo patrón que OpenAiProcess
        """
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://oai-poc-idatafactory-cr.openai.azure.com/')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
        
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY no encontrada en variables de entorno")
        
        self.logger.info(f"Configurando cliente OpenAI con endpoint: {endpoint}")
        self.logger.info(f"API Version: {api_version}")
        
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
        Procesa el contenido JSONL de los resultados del batch y los organiza por prompt
        
        Args:
            content: Contenido JSONL de los resultados
            batch_id: ID del batch
            
        Returns:
            Dict con resultados procesados organizados por prompt
        """
        results_by_document = {}
        results_by_prompt = {"auditoria": [], "desembolsos": [], "productos": []}
        total_processed = 0
        successful_responses = 0
        failed_responses = 0
        errors = []
        
        # Procesar cada línea del JSONL
        for line in content.strip().split('\n'):
            if not line.strip():
                continue
                
            try:
                result = json.loads(line)
                total_processed += 1
                
                custom_id = result.get('custom_id', '')
                response = result.get('response', {})
                
                if response.get('status_code') == 200:
                    successful_responses += 1
                    self._process_successful_response(result, results_by_document, results_by_prompt)
                else:
                    failed_responses += 1
                    error_info = {
                        'custom_id': custom_id,
                        'status_code': response.get('status_code'),
                        'error': response.get('body', {}),
                        'processed_at': datetime.now().isoformat()
                    }
                    errors.append(error_info)
                    self.logger.warning(f"Respuesta fallida para {custom_id}: {response.get('status_code')}")
                        
            except json.JSONDecodeError as e:
                failed_responses += 1
                error_info = {
                    'error': f"Error parsing JSON: {str(e)}",
                    'line': line,
                    'processed_at': datetime.now().isoformat()
                }
                errors.append(error_info)
                self.logger.error(f"Error parseando línea de resultado: {str(e)}")
        
        return {
            'batch_id': batch_id,
            'results_by_document': results_by_document,
            'results_by_prompt': results_by_prompt,
            'errors': errors,
            'total_processed': total_processed,
            'successful_responses': successful_responses,
            'failed_responses': failed_responses,
            'success_rate': (successful_responses / total_processed * 100) if total_processed > 0 else 0,
            'processed_at': datetime.now().isoformat()
        }
    
    def _process_successful_response(self, result: Dict[str, Any], results_by_document: Dict, results_by_prompt: Dict):
        """
        Procesa una respuesta exitosa y la organiza en las estructuras de datos.
        
        Args:
            result: Resultado individual del batch
            results_by_document: Dict para organizar por documento
            results_by_prompt: Dict para organizar por prompt
        """
        try:
            custom_id = result.get('custom_id', '')
            response = result.get('response', {})
            body = response.get('body', {})
            
            # Extraer información del custom_id
            # Formato: {project}_{document}_{prompt_type}[_chunk_{num}]
            parts = custom_id.split('_')
            if len(parts) < 3:
                self.logger.warning(f"Formato de custom_id inválido: {custom_id}")
                return
            
            project_name = parts[0]
            prompt_type = None
            document_name = None
            chunk_info = None
            
            # Identificar prompt type y document name
            if 'auditoria' in custom_id:
                prompt_type = 'auditoria'
                document_name = custom_id.replace(f"{project_name}_", "").replace("_auditoria", "")
            elif 'desembolsos' in custom_id:
                prompt_type = 'desembolsos'
                document_name = custom_id.replace(f"{project_name}_", "").replace("_desembolsos", "")
            elif 'productos' in custom_id:
                prompt_type = 'productos'
                document_name = custom_id.replace(f"{project_name}_", "").replace("_productos", "")
            
            # Extraer información de chunk si existe
            if '_chunk_' in document_name:
                chunk_match = document_name.split('_chunk_')
                if len(chunk_match) == 2:
                    document_name = chunk_match[0]
                    chunk_info = f"chunk_{chunk_match[1]}"
            
            # Extraer contenido de la respuesta
            choices = body.get('choices', [])
            if not choices:
                self.logger.warning(f"No hay choices en la respuesta para {custom_id}")
                return
            
            content = choices[0].get('message', {}).get('content', '')
            
            # Crear estructura de resultado
            result_data = {
                "custom_id": custom_id,
                "document_name": document_name,
                "prompt_type": prompt_type,
                "chunk_info": chunk_info,
                "content": content,
                "usage": body.get('usage', {}),
                "processed_at": datetime.now().isoformat()
            }
            
            # Organizar por documento
            if document_name not in results_by_document:
                results_by_document[document_name] = {}
            
            if prompt_type not in results_by_document[document_name]:
                results_by_document[document_name][prompt_type] = []
            
            results_by_document[document_name][prompt_type].append(result_data)
            
            # Organizar por prompt
            if prompt_type in results_by_prompt:
                results_by_prompt[prompt_type].append(result_data)
            
        except Exception as e:
            self.logger.error(f"Error procesando respuesta exitosa {result.get('custom_id', 'unknown')}: {str(e)}")
    
    def _extract_json_content(self, content: str) -> Any:
        """
        Extrae y parsea contenido JSON de diferentes formatos:
        1. Bloques de código ```json
        2. JSON directo
        3. JSON embebido en texto
        4. Manejo de JSON truncado/incompleto
        """
        if not content or not isinstance(content, str):
            return content
            
        # Caso 1: Contenido en bloque de código ```json
        if content.startswith('```json\n'):
            # Manejar diferentes terminaciones: \n```, \n```\n, etc.
            if content.endswith('\n```'):
                json_content = content[8:-4]  # Remover ```json\n y \n```
            elif content.endswith('\n```\n'):
                json_content = content[8:-5]  # Remover ```json\n y \n```\n
            elif content.endswith('```'):
                json_content = content[8:-3]  # Remover ```json\n y ```
            else:
                # Buscar el final del bloque o manejar JSON truncado
                end_pos = content.rfind('```')
                if end_pos > 8:
                    json_content = content[8:end_pos].rstrip('\n')
                else:
                    # JSON posiblemente truncado - intentar reparar
                    json_content = content[8:]  # Remover ```json\n
                    # Si termina de forma incompleta, intentar completar
                    if not json_content.rstrip().endswith(('}', ']')):
                        # Contar llaves/corchetes para intentar cerrar
                        open_braces = json_content.count('{') - json_content.count('}')
                        open_brackets = json_content.count('[') - json_content.count(']')
                        
                        # Intentar cerrar las estructuras abiertas
                        if open_braces > 0 or open_brackets > 0:
                            json_content = json_content.rstrip()
                            # Remover comas finales
                            if json_content.endswith(','):
                                json_content = json_content[:-1]
                            # Cerrar estructuras
                            json_content += '}' * open_braces + ']' * open_brackets
            
            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e:
                self.logger.warning(f"No se pudo parsear JSON del bloque de código: {str(e)[:100]}")
                return content
        
        # Caso 2: Contenido que empieza directamente con { o [
        content_stripped = content.strip()
        if content_stripped.startswith(('{', '[')):
            try:
                return json.loads(content_stripped)
            except json.JSONDecodeError:
                self.logger.warning(f"No se pudo parsear JSON directo")
                return content
        
        # Caso 3: Devolver contenido original si no es JSON
        return content
     
    def _save_processed_results(self, results: Dict[str, Any], batch_id: str, batch_info: Dict[str, Any]) -> None:
        """
        Guarda los resultados procesados en Azure Blob Storage organizados por prompt
        
        Args:
            results: Resultados procesados organizados por prompt
            batch_id: ID del batch
            batch_info: Información del batch
        """
        try:
            # Extraer información del proyecto desde la metadata del batch
            metadata = batch_info.get('metadata', {})
            project_name = metadata.get('project') or metadata.get('project_name')
            document_name = metadata.get('document') or metadata.get('document_name')
            
            if not project_name:
                self.logger.warning(f"No se encontró project_name en metadata del batch {batch_id}. Metadata disponible: {metadata}")
                raise ValueError(f"Información de proyecto faltante en metadata del batch {batch_id}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Guardar resultados organizados por documento
            results_by_document_filename = f"results_by_document_{project_name}_{timestamp}.json"
            self.blob_client.save_result(
                project_name=project_name,
                result_name=results_by_document_filename,
                content=results.get('results_by_document', {})
            )
            
            # Guardar resultados organizados por prompt
            results_by_prompt_filename = f"results_by_prompt_{project_name}_{timestamp}.json"
            self.blob_client.save_result(
                project_name=project_name,
                result_name=results_by_prompt_filename,
                content=results.get('results_by_prompt', {})
            )
            
            # Crear archivos separados por tipo de prompt (auditoria.json, productos.json, desembolsos.json)
            results_by_prompt = results.get('results_by_prompt', {})
            prompt_files_saved = []
            
            for prompt_type, prompt_results in results_by_prompt.items():
                if prompt_results:  # Solo procesar si hay resultados
                    # Extraer solo el contenido de cada resultado
                    content_list = []
                    for result in prompt_results:
                        if result.get('content'):
                            content = result['content']
                            parsed_content = self._extract_json_content(content)
                            content_list.append(parsed_content)
                    
                    # Guardar archivo separado por prompt
                    prompt_filename = f"{prompt_type}.json"
                    prompt_content = {
                        "prompt_type": prompt_type,
                        "total_results": len(content_list),
                        "results": content_list
                    }
                    self.blob_client.save_result(
                        project_name=project_name,
                        result_name=prompt_filename,
                        content=prompt_content
                    )
                    
                    prompt_files_saved.append(f"{prompt_type}.json ({len(content_list)} elementos)")
                    self.logger.info(f"Archivo {prompt_type}.json guardado: {len(content_list)} elementos")
            
            # Guardar resumen del batch
            summary = {
                "project_name": project_name,
                "batch_id": batch_id,
                "processed_at": results.get('processed_at'),
                "statistics": {
                    "total_processed": results.get('total_processed', 0),
                    "successful_responses": results.get('successful_responses', 0),
                    "failed_responses": results.get('failed_responses', 0),
                    "success_rate": results.get('success_rate', 0)
                },
                "output_files": {
                    "by_document": results_by_document_filename,
                    "by_prompt": results_by_prompt_filename,
                    "separated_prompts": prompt_files_saved
                },
                "documents_processed": len(results.get('results_by_document', {})),
                "prompts_results": {
                    prompt_type: len(prompt_results) for prompt_type, prompt_results in results_by_prompt.items()
                }
            }
            
            summary_filename = f"batch_summary_{project_name}_{timestamp}.json"
            self.blob_client.save_result(
                project_name=project_name,
                result_name=summary_filename,
                content=summary
            )
            
            self.logger.log_batch_operation(
                batch_id=batch_id,
                operation_id=self.operation_id,
                status="results_saved",
                results_count=results.get('successful_responses', 0),
                errors_count=results.get('failed_responses', 0)
            )
            
            # Log resumen detallado
            self.logger.info(f"📊 Procesamiento completado para batch {batch_id}:")
            self.logger.info(f"   📄 Total procesadas: {results.get('total_processed', 0)}")
            self.logger.info(f"   ✅ Exitosas: {results.get('successful_responses', 0)}")
            self.logger.info(f"   ❌ Fallidas: {results.get('failed_responses', 0)}")
            self.logger.info(f"   📈 Tasa de éxito: {results.get('success_rate', 0):.1f}%")
            self.logger.info(f"   📁 Archivos generados:")
            self.logger.info(f"      📋 Por documento: {results_by_document_filename}")
            self.logger.info(f"      🎯 Por prompt: {results_by_prompt_filename}")
            self.logger.info(f"      📊 Resumen: {summary_filename}")
            if prompt_files_saved:
                self.logger.info(f"      🗂️ Archivos separados por prompt:")
                for file_info in prompt_files_saved:
                    self.logger.info(f"         {file_info}")
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error guardando resultados del batch {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code="SAVE_RESULTS_ERROR",
                batch_id=batch_id
            )