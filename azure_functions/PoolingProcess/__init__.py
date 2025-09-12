import azure.functions as func
import logging
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from openai import AzureOpenAI

# Agregar el directorio padre al path para importar los módulos compartidos
sys.path.append(str(Path(__file__).parent.parent))

# Importar utilidades desde shared_code
from shared_code.utils.app_insights_logger import get_logger, generate_operation_id
from shared_code.utils.blob_storage_client import BlobStorageClient
from shared_code.utils.cosmo_db_client import CosmosDBClient
from shared_code.utils.pooling_event_timer_processor import PoolingEventTimerProcessor

def _load_local_settings_env():
    """Carga azure_functions/local.settings.json a os.environ en entorno local.
    No se ejecuta en Azure (para no sobrescribir App Settings)."""
    try:
        # Detectar si estamos en Azure
        in_azure = (
            os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT') is not None or
            os.environ.get('WEBSITE_SITE_NAME') is not None
        )
        if in_azure:
            return
        # Ruta a local.settings.json (dos niveles arriba: azure_functions/)
        settings_path = Path(__file__).parent.parent / 'local.settings.json'
        if not settings_path.exists():
            return
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        values = data.get('Values', {}) or {}
        # Sobrescribir en favor de local.settings.json para evitar .env
        for k, v in values.items():
            if isinstance(v, str):
                os.environ[k] = v
    except Exception:
        # No interrumpir la función por esto
        pass

# Cargar variables de entorno desde local.settings.json en local
_load_local_settings_env()

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

                # Usar el estado actual ya verificado en get_pending_batches
                batch_status = batch_info.get('current_status', 'unknown')
                is_orphaned = batch_info.get('is_orphaned', False)
                
                logger.info(f"Procesando batch {batch_id} con estado: {batch_status} (huérfano: {is_orphaned})")

                if batch_status == 'completed':
                    # Procesar resultados del batch completado (normal o huérfano)
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
                elif batch_status in ['validating', 'in_progress', 'finalizing']:
                    logger.info(f"Batch {batch_id} aún en proceso: {batch_status}")

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
        Obtiene la lista de batches pendientes desde el blob storage
        buscando archivos batch_info y verificando su estado en OpenAI
        
        Returns:
            Lista de información de batches pendientes
        """
        try:
            pending_batches: List[Dict[str, Any]] = []
            
            # Buscar archivos batch_info en las rutas específicas de cada proyecto
            # Primero obtener lista de proyectos explorando basedocuments/
            project_prefixes = self.blob_client.list_blobs_with_prefix(
                prefix="basedocuments/"
            )
            
            # Extraer nombres de proyectos únicos
            projects = set()
            for blob_info in project_prefixes:
                path_parts = blob_info['name'].split('/')
                if len(path_parts) >= 2:
                    project_name = path_parts[1]  # basedocuments/{project}/...
                    projects.add(project_name)
            
            self.logger.info(f"Proyectos encontrados: {list(projects)}")
            
            # Si hay Cosmos configurado, filtrar proyectos a los que tengan isBatchPending=true
            pending_set: Optional[Set[str]] = None
            try:
                container_folder = os.environ.get("COSMOS_CONTAINER_FOLDER")
                if container_folder:
                    cdb = CosmosDBClient()
                    timer_proc = PoolingEventTimerProcessor(cdb)
                    pending_set = timer_proc.process_batch(container_folder)
                    if not pending_set:
                        self.logger.info("No pending folders in Cosmos; proceeding with no filtering")
                else:
                    self.logger.info("COSMOS_CONTAINER_FOLDER not set; proceeding without Cosmos filtering")
            except Exception as e:
                self.logger.warning(f"Cosmos filtering not available: {str(e)}")
                pending_set = None

            # Buscar archivos batch_info en cada proyecto (aplicando filtro si existe)
            batch_info_files = []
            for project in projects:
                if pending_set is not None and project not in pending_set:
                    # Saltar proyectos que no están marcados como pendientes
                    continue
                project_prefix = f"basedocuments/{project}/processed/openai_logs/"
                project_blobs = self.blob_client.list_blobs_with_prefix(
                    prefix=project_prefix
                )
                
                for blob_info in project_blobs:
                    blob_name = blob_info['name']
                    if 'batch_info_' in blob_name and blob_name.endswith('.json'):
                        batch_info_files.append(blob_info)
            
            self.logger.info(f"Encontrados {len(batch_info_files)} archivos batch_info")
            
            for blob_info in batch_info_files:
                try:
                    # Descargar y parsear el archivo batch_info
                    batch_info_content = self.blob_client.download_blob(
                        container_name=None,
                        blob_name=blob_info['name']
                    )
                    
                    batch_info = json.loads(batch_info_content)
                    batch_id = batch_info.get('batch_id')
                    
                    if not batch_id:
                        continue
                    
                    # Inferir project_name desde la ruta si no viene en el JSON
                    project_name = batch_info.get('project_name')
                    if not project_name:
                        try:
                            path_parts = blob_info['name'].split('/')
                            if len(path_parts) >= 2:
                                project_name = path_parts[1]
                        except Exception:
                            project_name = None

                    # Verificar el estado actual del batch en OpenAI
                    current_status = self.check_batch_status(batch_id)
                    
                    # Si ya está 'completed' y existe marcador por batch, saltar para evitar reprocesos
                    if current_status == 'completed' and project_name and \
                       self._batch_results_marker_exists(project_name, batch_id):
                        self.logger.info(
                            f"Marcador existente para batch {batch_id} en proyecto {project_name}; omitiendo de pendientes"
                        )
                        continue

                    # Solo incluir batches que están pendientes o completados sin marcador
                    if current_status in ['validating', 'in_progress', 'finalizing', 'completed']:
                        batch_info['current_status'] = current_status
                        batch_info['blob_name'] = blob_info['name']
                        if project_name:
                            batch_info['project_name'] = project_name
                        pending_batches.append(batch_info)
                        
                        self.logger.info(f"Batch {batch_id} encontrado con estado: {current_status}")
                    
                except Exception as file_error:
                    self.logger.log_error(
                        message=f"Error procesando archivo batch_info {blob_info.get('name', 'unknown')}: {str(file_error)}",
                        operation_id=self.operation_id,
                        error_code="BATCH_INFO_FILE_ERROR"
                    )
                    continue
            
            # Buscar batches completados en openai_logs que no tengan carpeta de resultados por batch_id (marcador)
            orphaned_batches = self._find_orphaned_completed_batches()

            # Desduplicar por batch_id, fusionando info de huérfanos
            merged: Dict[str, Dict[str, Any]] = {}
            for entry in pending_batches:
                bid = entry.get('batch_id')
                if not bid:
                    continue
                merged[bid] = dict(entry)
            for orphan in orphaned_batches:
                bid = orphan.get('batch_id')
                if not bid:
                    continue
                if bid in merged:
                    # Conservar current_status del entry original, marcar orphaned si aplica
                    merged[bid]['is_orphaned'] = True
                    # Preservar project_name y rutas si no estaban
                    for k in ('project_name', 'openai_log_path', 'blob_name'):
                        if k not in merged[bid] and k in orphan:
                            merged[bid][k] = orphan[k]
                else:
                    merged[bid] = dict(orphan)

            final_list = list(merged.values())
            self.logger.info(f"Total de batches pendientes encontrados: {len(final_list)}")
            return final_list
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error obteniendo batches pendientes: {str(e)}",
                operation_id=self.operation_id,
                error_code="GET_PENDING_BATCHES_ERROR"
            )
            return []
    
    def _find_orphaned_completed_batches(self) -> List[Dict[str, Any]]:
        """
        Busca batches completados en openai_logs que no tengan carpeta de resultados
        
        Returns:
            Lista de batches huérfanos que necesitan procesamiento
        """
        try:
            orphaned_batches = []
            
            # Buscar archivos en openai_logs usando la estructura correcta
            # Primero obtener lista de proyectos
            project_prefixes = self.blob_client.list_blobs_with_prefix(
                prefix="basedocuments/"
            )
            
            # Extraer nombres de proyectos únicos
            projects = set()
            for blob_info in project_prefixes:
                path_parts = blob_info['name'].split('/')
                if len(path_parts) >= 2:
                    project_name = path_parts[1]
                    projects.add(project_name)
            
            # Buscar archivos en openai_logs de cada proyecto
            openai_log_files = []
            for project in projects:
                openai_logs_prefix = f"basedocuments/{project}/processed/openai_logs/"
                project_logs = self.blob_client.list_blobs_with_prefix(
                    prefix=openai_logs_prefix
                )
                openai_log_files.extend(project_logs)
            
            self.logger.info(f"Encontrados {len(openai_log_files)} archivos en openai_logs")
            
            for log_file in openai_log_files:
                try:
                    # Extraer información del path del archivo
                    # Formato esperado: basedocuments/{project}/processed/openai_logs/batch_info_xxx.json
                    path_parts = log_file['name'].split('/')
                    if len(path_parts) < 5 or 'openai_logs' not in path_parts:
                        continue
                    
                    project_name = path_parts[1]  # basedocuments/{project}/...
                    batch_filename = path_parts[-1]  # batch_info_xxx.json
                    
                    # Filtrar archivos que contengan "batch_info_" y terminen en ".json"
                    if not (batch_filename.startswith('batch_info_') and batch_filename.endswith('.json')):
                        continue
                    
                    # Descargar y parsear el archivo batch_info para extraer batch_id del contenido
                    batch_info_content = self.blob_client.download_blob(
                        container_name=None,
                        blob_name=log_file['name']
                    )
                    
                    batch_info = json.loads(batch_info_content)
                    batch_id = batch_info.get('batch_id')
                    
                    if not batch_id:
                        self.logger.warning(f"No se encontró batch_id en archivo {batch_filename}")
                        continue
                    
                    # Nuevo criterio: verificar marcador por batch_id bajo results/batches/{batch_id}/processed.json
                    has_marker = self._batch_results_marker_exists(project_name, batch_id)

                    self.logger.info(
                        f"Verificando marcador para batch {batch_id}: project={project_name}, exists={has_marker}"
                    )

                    if not has_marker:
                        # Verificar estado del batch en OpenAI
                        current_status = self.check_batch_status(batch_id)

                        if current_status == 'completed':
                            orphaned_batch = {
                                'batch_id': batch_id,
                                'current_status': current_status,
                                'project_name': project_name,
                                'openai_log_path': log_file['name'],
                                'is_orphaned': True,
                                'batch_info': batch_info
                            }

                            orphaned_batches.append(orphaned_batch)

                            self.logger.info(
                                f"Batch huérfano encontrado (sin marcador): {batch_id} para proyecto {project_name}"
                            )
                    
                except Exception as file_error:
                    self.logger.log_error(
                        message=f"Error procesando archivo openai_logs {log_file.get('name', 'unknown')}: {str(file_error)}",
                        operation_id=self.operation_id,
                        error_code="ORPHANED_BATCH_FILE_ERROR"
                    )
                    continue
            
            self.logger.info(f"Total de batches huérfanos encontrados: {len(orphaned_batches)}")
            return orphaned_batches
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error buscando batches huérfanos: {str(e)}",
                operation_id=self.operation_id,
                error_code="FIND_ORPHANED_BATCHES_ERROR"
            )
            return []
    
    def _check_results_folder_exists(self, results_path: str) -> bool:
        """
        Verifica si existe una carpeta de resultados con archivos JSON
        
        Args:
            results_path: Path de la carpeta de resultados
            
        Returns:
            True si existe la carpeta con archivos JSON, False en caso contrario
        """
        try:
            # Buscar archivos JSON en la carpeta de resultados
            # Nota: results_path ya incluye 'basedocuments/...'. No pasar container_name para evitar duplicar prefijo.
            result_files = self.blob_client.list_blobs_with_prefix(
                prefix=results_path
            )
            
            # Verificar si hay archivos JSON (auditoria, desembolsos, productos)
            json_files = [f for f in result_files if f['name'].endswith('.json')]
            
            # Debe tener al menos los 3 archivos principales
            required_files = ['auditoria.json', 'desembolsos.json', 'productos.json']
            found_files = [f['name'].split('/')[-1] for f in json_files]
            
            has_all_required = all(req_file in found_files for req_file in required_files)
            
            return has_all_required
            
        except Exception as e:
            self.logger.log_error(
                message=f"Error verificando carpeta de resultados {results_path}: {str(e)}",
                operation_id=self.operation_id,
                error_code="CHECK_RESULTS_FOLDER_ERROR"
            )
            return False

    def _batch_results_marker_exists(self, project_name: str, batch_id: str) -> bool:
        """
        Verifica si existe el marcador de resultados para un batch específico.
        El marcador se guarda en: basedocuments/{project}/results/batches/{batch_id}/processed.json

        Args:
            project_name: Proyecto
            batch_id: ID del batch

        Returns:
            True si existe el marcador, False en caso contrario
        """
        try:
            marker_path = f"basedocuments/{project_name}/results/batches/{batch_id}/processed.json"
            files = self.blob_client.list_blobs_with_prefix(prefix=marker_path)
            for f in files:
                if f.get('name') == marker_path:
                    return True
            return False
        except Exception as e:
            self.logger.log_error(
                message=f"Error verificando marcador de batch {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code="CHECK_BATCH_MARKER_ERROR",
                batch_id=batch_id
            )
            return False
    
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
            is_orphaned = batch_info.get('is_orphaned', False)
            
            if is_orphaned:
                self.logger.info(f"Procesando batch huérfano {batch_id}")
                # Para batches huérfanos, descargar desde OpenAI ya que no tenemos los resultados guardados
                batch = self.client.batches.retrieve(batch_id)
                
                if not batch.output_file_id:
                    self.logger.warning(f"Batch huérfano {batch_id} completado pero sin archivo de salida")
                    return None
                
                # Descargar archivo de resultados desde OpenAI
                result_file_response = self.client.files.content(batch.output_file_id)
                result_content = result_file_response.content
                
                # Procesar contenido del archivo
                results = self._process_batch_results(result_content.decode('utf-8'), batch_id)
                
                # Guardar resultados procesados
                self._save_processed_results(results, batch_id, batch_info)
                # Guardar marcador por batch
                self._save_batch_processed_marker(batch_id, batch_info, results)
                
                self.logger.info(f"Batch huérfano {batch_id} procesado exitosamente")
                return results
            else:
                # Procesamiento normal para batches no huérfanos
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
                # Guardar marcador por batch
                self._save_batch_processed_marker(batch_id, batch_info, results)
                
                return results
            
        except Exception as e:
            error_type = "PROCESS_ORPHANED_BATCH_ERROR" if batch_info.get('is_orphaned', False) else "PROCESS_COMPLETED_BATCH_ERROR"
            self.logger.log_error(
                message=f"Error procesando batch {'huérfano' if batch_info.get('is_orphaned', False) else 'completado'} {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code=error_type,
                batch_id=batch_id
            )
            return None

    def _save_batch_processed_marker(self, batch_id: str, batch_info: Dict[str, Any], results: Dict[str, Any]) -> None:
        """
        Guarda un marcador de procesamiento por batch bajo results/batches/{batch_id}/processed.json
        con un resumen mínimo y referencias a archivos generados a nivel de proyecto.
        """
        try:
            project_name = batch_info.get('project_name') or batch_info.get('batch_info', {}).get('project_name')
            if not project_name:
                # Intentar deducir desde blob_name u openai_log_path si existe
                blob_name = batch_info.get('blob_name') or batch_info.get('openai_log_path', '')
                parts = blob_name.split('/')
                if len(parts) >= 2:
                    project_name = parts[1]
            if not project_name:
                self.logger.warning(f"No se pudo determinar project_name para guardar marcador de batch {batch_id}")
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            marker_content = {
                "batch_id": batch_id,
                "project_name": project_name,
                "processed_at": timestamp,
                "statistics": {
                    "total_processed": results.get('total_processed', 0),
                    "successful_responses": results.get('successful_responses', 0),
                    "failed_responses": results.get('failed_responses', 0),
                    "success_rate": results.get('success_rate', 0)
                }
            }

            # Guardar bajo results/batches/{batch_id}/processed.json
            result_name = f"batches/{batch_id}/processed.json"
            self.blob_client.save_result(
                project_name=project_name,
                result_name=result_name,
                content=marker_content
            )
            self.logger.info(f"Marcador de batch guardado: basedocuments/{project_name}/results/{result_name}")

            # Best-effort: actualizar Cosmos para apagar el pendiente
            try:
                sharepoint_folder = os.environ.get("SHAREPOINT_FOLDER")
                container_folder = os.environ.get("COSMOS_CONTAINER_FOLDER")
                if sharepoint_folder and container_folder:
                    doc_id = f"{sharepoint_folder}|{project_name}"
                    cdb = CosmosDBClient()
                    doc = cdb.read_item(doc_id, doc_id, container_folder)
                    if doc is not None:
                        doc["isBatchPending"] = False
                        doc["lastProcessedBatchId"] = batch_id
                        doc["processedAt"] = timestamp
                        stats = results.get('total_processed'), results.get('successful_responses'), results.get('failed_responses')
                        doc["lastStats"] = {
                            "total_processed": results.get('total_processed', 0),
                            "successful_responses": results.get('successful_responses', 0),
                            "failed_responses": results.get('failed_responses', 0),
                            "success_rate": results.get('success_rate', 0),
                        }
                        cdb.upsert_item(doc, container_folder)
                        self.logger.info(f"CosmosDB folder marked processed: {doc_id}")
                else:
                    self.logger.info("Cosmos env not set; skipping folder processed mark")
            except Exception as e:
                self.logger.warning(f"Could not update Cosmos folder processed mark: {str(e)}")
        except Exception as e:
            self.logger.log_error(
                message=f"Error guardando marcador de batch {batch_id}: {str(e)}",
                operation_id=self.operation_id,
                error_code="SAVE_BATCH_MARKER_ERROR",
                batch_id=batch_id
            )
    
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
                
                custom_id = result.get('custom_id', '')
                response = result.get('response', {})
                
                if response.get('status_code') == 200:
                    # Procesar y contabilizar cada objeto individual extraído
                    added = self._process_successful_response(result, results_by_document, results_by_prompt)
                    successful_responses += int(added)
                    total_processed += int(added)
                else:
                    failed_responses += 1
                    total_processed += 1
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
                total_processed += 1
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
    
    def _process_successful_response(self, result: Dict[str, Any], results_by_document: Dict, results_by_prompt: Dict) -> int:
        """
        Procesa una respuesta exitosa y la organiza en las estructuras de datos.
        
        Args:
            result: Resultado individual del batch
            results_by_document: Dict para organizar por documento
            results_by_prompt: Dict para organizar por prompt
        """
        try:
            import re
            custom_id = result.get('custom_id', '')
            response = result.get('response', {})
            body = response.get('body', {})
            
            # Extraer información del custom_id
            # Patrones soportados:
            #  - {project}_{document}_{prompt_type}[_chunk_{num}]
            #  - {project}_{document}_prompt{n}[_chunk_{num}]  (n ∈ {1,2,3})
            parts = custom_id.split('_')
            if len(parts) < 2:
                self.logger.warning(f"Formato de custom_id inválido: {custom_id}")
                return
            project_name = parts[0]

            prompt_type = None
            document_name = None
            chunk_info = None

            # 1) Intentar con nombres explícitos de prompt
            if 'auditoria' in custom_id:
                prompt_type = 'auditoria'
                document_name = custom_id.replace(f"{project_name}_", "").replace("_auditoria", "")
            elif 'desembolsos' in custom_id:
                prompt_type = 'desembolsos'
                document_name = custom_id.replace(f"{project_name}_", "").replace("_desembolsos", "")
            elif 'productos' in custom_id:
                prompt_type = 'productos'
                document_name = custom_id.replace(f"{project_name}_", "").replace("_productos", "")
            else:
                # 2) Soportar patrón _prompt{n}
                m = re.search(r"_prompt(\d+)", custom_id)
                if m:
                    n = m.group(1)
                    mapping = {'1': 'auditoria', '2': 'desembolsos', '3': 'productos'}
                    prompt_type = mapping.get(n)
                    # document_name = entre '{project}_' y '_prompt{n}' (respetando posibles '_chunk_...')
                    try:
                        suffix = f"_prompt{n}"
                        before_suffix = custom_id[: custom_id.rfind(suffix)]
                        # remove leading '{project}_'
                        if before_suffix.startswith(f"{project_name}_"):
                            document_name = before_suffix[len(project_name) + 1 :]
                        else:
                            # fallback: quitar hasta el primer '_'
                            first_us = before_suffix.find('_')
                            document_name = before_suffix[first_us + 1 :] if first_us >= 0 else before_suffix
                    except Exception:
                        document_name = None

            # Extraer información de chunk si existe (proteger None)
            # Importante: conservar document_name intacto para poder usarlo como nombre final de archivo
            if document_name and '_chunk_' in document_name:
                parts = document_name.split('_chunk_')
                if len(parts) == 2:
                    # No modificar document_name; solo informar chunk_info
                    chunk_info = f"chunk_{parts[1]}"
            
            # Extraer contenido de la respuesta
            choices = body.get('choices', [])
            if not choices:
                self.logger.warning(f"No hay choices en la respuesta para {custom_id}")
                return
            
            raw_content = choices[0].get('message', {}).get('content', '')

            # Parsear múltiples objetos del contenido y normalizar por tipo de prompt
            parsed_list = self._parse_multiple_json_objects(raw_content)
            normalized_list = self._normalize_by_prompt(prompt_type, parsed_list)

            added = 0
            for idx, obj in enumerate(normalized_list or []):
                # Construir estructura de resultado por objeto
                this_custom_id = custom_id if len(normalized_list) == 1 else f"{custom_id}_part_{idx+1:03d}"
                result_data = {
                    "custom_id": this_custom_id,
                    "document_name": document_name,
                    "prompt_type": prompt_type,
                    "chunk_info": chunk_info,
                    "content": obj,  # Guardamos el objeto ya parseado
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

                added += 1

            # Si no se pudo parsear/normalizar nada, preservamos el texto crudo como un item
            if added == 0:
                fallback = {
                    "_raw_text": raw_content,
                    "_parse_error": None
                }
                if document_name not in results_by_document:
                    results_by_document[document_name] = {}
                if prompt_type not in results_by_document[document_name]:
                    results_by_document[document_name][prompt_type] = []
                results_by_document[document_name][prompt_type].append({
                    "custom_id": custom_id,
                    "document_name": document_name,
                    "prompt_type": prompt_type,
                    "chunk_info": chunk_info,
                    "content": fallback,
                    "usage": body.get('usage', {}),
                    "processed_at": datetime.now().isoformat()
                })
                if prompt_type in results_by_prompt:
                    results_by_prompt[prompt_type].append(results_by_document[document_name][prompt_type][-1])
                added = 1

            return added
        
        except Exception as e:
            self.logger.error(f"Error procesando respuesta exitosa {result.get('custom_id', 'unknown')}: {str(e)}")
            return 0

    def _parse_multiple_json_objects(self, content: str) -> List[Dict[str, Any]]:
        """
        Extrae 0..N objetos JSON desde un string que puede venir con fences ```json, listas, o
        múltiples objetos concatenados. Aplica reparaciones leves si es posible.
        """
        if not content or not isinstance(content, str):
            return []

        text = content.strip()
        # Remover fences de código
        if text.startswith('```json'):
            # quitar la primera línea ```json y el cierre ``` si existe
            text = text[7:] if text.startswith('```json') else text
            text = text.lstrip('\n')
            if text.endswith('```'):
                text = text[:-3]

        text = text.strip()

        def try_json_loads(s: str) -> Optional[Any]:
            try:
                return json.loads(s)
            except Exception:
                return None

        # Caso lista JSON
        if text.startswith('['):
            data = try_json_loads(text)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, (dict, list))]
            elif isinstance(data, dict):
                return [data]

        # Intentar separar múltiples objetos `{...}{...}`
        objs: List[Dict[str, Any]] = []
        buf = ''
        brace = 0
        in_str = False
        esc = False
        for ch in text:
            if esc:
                buf += ch
                esc = False
                continue
            if ch == '\\' and in_str:
                buf += ch
                esc = True
                continue
            if ch == '"':
                buf += ch
                in_str = not in_str
                continue
            if not in_str and ch == '{':
                # Inicio de un objeto; si no estábamos dentro de otro, reiniciar buffer
                if brace == 0:
                    buf = ''
                brace += 1
                buf += ch
                continue
            if not in_str and ch == '}':
                buf += ch
                brace -= 1
                if brace == 0:
                    candidate = buf.strip()
                    data = try_json_loads(candidate)
                    if isinstance(data, dict):
                        objs.append(data)
                        buf = ''
                continue
            # Caracter normal
            buf += ch

        # Si no se separó nada, intentar reparaciones leves sobre todo el texto
        if not objs:
            repaired = text.replace(',}', '}').replace(',]', ']')
            # recortar hasta el último '}' si parece truncado
            last = repaired.rfind('}')
            if last > 0:
                candidate = repaired[: last + 1]
                data = try_json_loads(candidate)
                if isinstance(data, dict):
                    return [data]
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, (dict, list))]
        return objs

    def _normalize_by_prompt(self, prompt_type: Optional[str], objs: List[Any]) -> List[Dict[str, Any]]:
        """Normaliza listas de objetos según el tipo de prompt. Aplana estructuras conocidas.
        - desembolsos: aplanar {desembolsos:{proyectados,realizados}, metadata}
        - productos: pasar tal cual (cada dict es un producto)
        - auditoria: pasar tal cual
        """
        norm: List[Dict[str, Any]] = []
        if not objs:
            return norm

        if prompt_type == 'desembolsos':
            for item in objs:
                if isinstance(item, dict) and isinstance(item.get('desembolsos'), dict):
                    meta = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
                    for k in ('proyectados', 'realizados'):
                        arr = item['desembolsos'].get(k)
                        if isinstance(arr, list):
                            for row in arr:
                                if isinstance(row, dict):
                                    rec = dict(row)
                                    rec['tipo_registro_norm'] = 'realizado' if k == 'realizados' else 'proyectado'
                                    # mezclar metadata útil
                                    for mk, mv in meta.items():
                                        rec.setdefault(mk, mv)
                                    norm.append(rec)
                elif isinstance(item, dict):
                    norm.append(item)
        else:
            # productos / auditoria / otros: pasar dicts tal cual
            for item in objs:
                if isinstance(item, dict):
                    norm.append(item)
        return norm

    def _materialize_content_for_file(self, prompt_type: Optional[str], content: Any) -> Any:
        """
        Garantiza que el contenido a guardar en cada archivo por documento sea JSON parseado:
        - Si viene con wrapper {'_raw_text': '<json>'}, parsea ese JSON y devuelve el objeto/array.
        - Si es string JSON, lo parsea.
        - Si ya es dict/list, lo retorna tal cual.
        - Si falla el parseo, devuelve un contenido sin los campos de wrapper cuando sea posible.
        """
        try:
            # Caso wrapper con _raw_text
            if isinstance(content, dict) and '_raw_text' in content:
                raw = content.get('_raw_text')
                # Intentar parsear si es string
                if isinstance(raw, str):
                    # Primero: extraer JSON de posibles fences o texto
                    extracted = self._extract_json_content(raw)
                    if isinstance(extracted, (dict, list)):
                        return extracted
                    # Segundo: intentar múltiples objetos concatenados o lista
                    many = self._parse_multiple_json_objects(raw)
                    if many:
                        # Si hay un único objeto, devolverlo; si varios, devolver lista
                        return many if len(many) > 1 else many[0]
                # Si ya viene como dict/list en _raw_text
                if isinstance(raw, (dict, list)):
                    return raw
                # Fallback: eliminar campos de wrapper y devolver el resto
                cleaned = dict(content)
                cleaned.pop('_raw_text', None)
                cleaned.pop('_parse_error', None)
                return cleaned if cleaned else raw

            # Caso string JSON directo
            if isinstance(content, str):
                extracted = self._extract_json_content(content)
                if isinstance(extracted, (dict, list)):
                    return extracted
                # Intentar múltiples objetos
                many = self._parse_multiple_json_objects(content)
                if many:
                    return many if len(many) > 1 else many[0]
                return content

            # dict/list ya parseado
            return content
        except Exception:
            # Si algo falla, devolver el contenido original para no perder datos
            return content
    
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
            # Extraer información del proyecto desde la metadata del batch o directamente del batch_info
            metadata = batch_info.get('metadata', {})
            project_name = (
                batch_info.get('project_name') or  # Para batches huérfanos
                metadata.get('project') or 
                metadata.get('project_name')
            )
            document_name = metadata.get('document') or metadata.get('document_name')
            
            if not project_name:
                self.logger.warning(f"No se encontró project_name en metadata del batch {batch_id}. Metadata disponible: {metadata}")
                raise ValueError(f"Información de proyecto faltante en metadata del batch {batch_id}")
            
            # Usar nombres deterministas por batch para evitar duplicados por timestamps
            # Alinear con convención usada en LLM_output: results_by_document_batch_<batch_id>.json
            results_by_document_filename = f"results_by_document_batch_{batch_id}.json"
            self.blob_client.save_result(
                project_name=project_name,
                result_name=results_by_document_filename,
                content=results.get('results_by_document', {})
            )
            
            # Guardar resultados organizados por prompt
            # Alinear nombre con convención por batch
            results_by_prompt_filename = f"results_by_prompt_batch_{batch_id}.json"
            self.blob_client.save_result(
                project_name=project_name,
                result_name=results_by_prompt_filename,
                content=results.get('results_by_prompt', {})
            )
            
            # Crear archivos separados por tipo de prompt concatenando los JSON individuales como JSONL
            prompt_files_saved = []
            folder_map = {
                'auditoria': 'Auditoria',
                'desembolsos': 'Desembolsos',
                'productos': 'Productos'
            }
            for prompt_type, folder in folder_map.items():
                prefix = f"basedocuments/{project_name}/results/{folder}/"
                try:
                    entries = self.blob_client.list_blobs_with_prefix(prefix=prefix)
                except Exception as e:
                    self.logger.warning(f"No se pudo listar carpeta {folder}: {str(e)}")
                    entries = []

                lines: List[str] = []
                count = 0
                for entry in entries:
                    name = entry.get('name') if isinstance(entry, dict) else None
                    if not name or not name.endswith('.json'):
                        continue
                    try:
                        data_bytes = self.blob_client.download_blob(None, name)
                        obj = json.loads(data_bytes)
                        # Escribir cada JSON como una línea
                        lines.append(json.dumps(obj, ensure_ascii=False))
                        count += 1
                    except Exception as e:
                        self.logger.warning(f"No se pudo agregar {name} a {prompt_type}.json: {str(e)}")

                # Fallback: si no se pudo leer nada desde storage, construir JSONL desde la estructura en memoria
                if not lines:
                    by_doc = results.get('results_by_document', {}) or {}
                    for doc_name, sections in by_doc.items():
                        if not isinstance(sections, dict):
                            continue
                        items = sections.get(prompt_type) or []
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            content = item.get('content')
                            if content is None:
                                continue
                            materialized = self._materialize_content_for_file(prompt_type, content)
                            try:
                                lines.append(json.dumps(materialized, ensure_ascii=False))
                            except Exception:
                                # Como último recurso, guardar string del contenido
                                if isinstance(materialized, str):
                                    lines.append(materialized)
                    count = len(lines)

                # Convertir líneas JSONL a arreglo JSON válido de objetos
                array_items: List[Dict[str, Any]] = []
                for _ln in lines:
                    try:
                        parsed = json.loads(_ln)
                        if isinstance(parsed, dict):
                            array_items.append(parsed)
                        elif isinstance(parsed, list):
                            for it in parsed:
                                if isinstance(it, dict):
                                    array_items.append(it)
                    except Exception:
                        # Omitir entradas inválidas
                        pass

                self.blob_client.save_result(
                    project_name=project_name,
                    result_name=f"{prompt_type}.json",
                    content=array_items
                )
                prompt_files_saved.append(f"{prompt_type}.json ({count} elementos)")
                self.logger.info(f"Archivo {prompt_type}.json guardado: {count} elementos")
            
            # Guardar archivos individuales por documento y por tipo (estructura LLM_output)
            # Estructura esperada:
            #  - results/Productos/<documento>_producto_XXX.json
            #  - results/Desembolsos/<documento>_desembolso_XXX.json
            #  - results/Auditoria/<documento>_chunk_XXX_auditoria.json
            by_doc = results.get('results_by_document', {}) or {}
            folder_map = {
                'productos': 'Productos',
                'desembolsos': 'Desembolsos',
                'auditoria': 'Auditoria'
            }

            for doc_name, sections in by_doc.items():
                if not isinstance(sections, dict):
                    continue
                for prompt_type, items in sections.items():
                    if not items:
                        continue
                    folder = folder_map.get(prompt_type, prompt_type.capitalize())
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        content = item.get('content')
                        if content is None:
                            continue
                        # Materializar contenido: parsear _raw_text o strings JSON
                        content = self._materialize_content_for_file(prompt_type, content)
                        # Nombre exacto: usar document_name del item (sin alterar)
                        filename = item.get('document_name') or doc_name
                        # Asegurar extensión .json
                        filename = filename if filename.lower().endswith('.json') else f"{filename}.json"

                        result_path = f"{folder}/{filename}"
                        try:
                            self.blob_client.save_result(
                                project_name=project_name,
                                result_name=result_path,
                                content=content
                            )
                        except Exception as e:
                            self.logger.warning(f"No se pudo guardar archivo por documento {result_path}: {str(e)}")

            # Guardar resumen del batch
            results_by_prompt = results.get('results_by_prompt', {}) or {}
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
                "prompts_results": {prompt_type: len(prompt_results) for prompt_type, prompt_results in results_by_prompt.items()}
            }
            
            summary_filename = f"batch_summary_{batch_id}.json"
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
