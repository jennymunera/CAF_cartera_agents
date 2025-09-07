import os
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv
from utils.app_insights_logger import get_logger

# Cargar variables de entorno
load_dotenv()

# Configurar logging con Azure Application Insights
logger = get_logger('batch_results_processor')

# Reducir verbosidad de Azure
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)

class BatchResultsProcessor:
    """
    Procesador de resultados de Azure OpenAI Batch API.
    Monitorea batch jobs y procesa los resultados cuando están listos.
    """
    
    def __init__(self):
        self.logger = logger
        self._setup_client()
        
    def _setup_client(self):
        """Configura el cliente de Azure OpenAI usando variables de entorno."""
        try:
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://oai-poc-idatafactory-cr.openai.azure.com/')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-03-01-preview')
            
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY no encontrada en variables de entorno")
            
            self.client = AzureOpenAI(
                api_version='2025-04-01-preview',
                azure_endpoint=endpoint,
                api_key=api_key
            )
            
            self.logger.info("Cliente Azure OpenAI configurado para procesamiento de resultados")
            
        except Exception as e:
            self.logger.error(f"Error configurando cliente Azure OpenAI: {str(e)}")
            raise
    
    def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Verifica el estado de un batch job.
        
        Args:
            batch_id: ID del batch job
            
        Returns:
            Dict con información del estado del batch
        """
        try:
            batch = self.client.batches.retrieve(batch_id)
            
            status_info = {
                "batch_id": batch.id,
                "status": batch.status,
                "created_at": batch.created_at,
                "completed_at": batch.completed_at,
                "failed_at": batch.failed_at,
                "request_counts": {
                    "total": batch.request_counts.total if batch.request_counts else 0,
                    "completed": batch.request_counts.completed if batch.request_counts else 0,
                    "failed": batch.request_counts.failed if batch.request_counts else 0
                },
                "output_file_id": batch.output_file_id,
                "error_file_id": batch.error_file_id
            }
            
            return status_info
            
        except Exception as e:
            self.logger.error(f"Error verificando estado del batch {batch_id}: {str(e)}")
            raise
    
    def wait_for_completion(self, batch_id: str, max_wait_minutes: int = 60, check_interval_seconds: int = 30) -> bool:
        """
        Espera a que un batch job se complete.
        
        Args:
            batch_id: ID del batch job
            max_wait_minutes: Tiempo máximo de espera en minutos
            check_interval_seconds: Intervalo entre verificaciones en segundos
            
        Returns:
            True si se completó exitosamente, False si falló o timeout
        """
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        
        self.logger.info(f"⏳ Esperando completación del batch {batch_id}...")
        self.logger.info(f"   ⏰ Tiempo máximo de espera: {max_wait_minutes} minutos")
        self.logger.info(f"   🔄 Verificando cada {check_interval_seconds} segundos")
        
        while True:
            try:
                status_info = self.check_batch_status(batch_id)
                status = status_info["status"]
                
                elapsed_minutes = (time.time() - start_time) / 60
                
                if status == "completed":
                    self.logger.info(f"✅ Batch completado exitosamente en {elapsed_minutes:.1f} minutos")
                    self._log_batch_summary(status_info)
                    return True
                elif status == "failed":
                    self.logger.error(f"❌ Batch falló después de {elapsed_minutes:.1f} minutos")
                    self._log_batch_summary(status_info)
                    return False
                elif status in ["validating", "in_progress", "finalizing"]:
                    completed = status_info["request_counts"]["completed"]
                    total = status_info["request_counts"]["total"]
                    progress = (completed / total * 100) if total > 0 else 0
                    
                    self.logger.info(f"🔄 Estado: {status} | Progreso: {completed}/{total} ({progress:.1f}%) | Tiempo: {elapsed_minutes:.1f}min")
                else:
                    self.logger.info(f"📋 Estado actual: {status} | Tiempo transcurrido: {elapsed_minutes:.1f}min")
                
                # Verificar timeout
                if time.time() - start_time > max_wait_seconds:
                    self.logger.warning(f"⏰ Timeout alcanzado ({max_wait_minutes} minutos). Estado final: {status}")
                    return False
                
                time.sleep(check_interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error durante la espera: {str(e)}")
                return False
    
    def _log_batch_summary(self, status_info: Dict[str, Any]):
        """Registra un resumen del estado del batch."""
        counts = status_info["request_counts"]
        self.logger.info(f"📊 Resumen del batch {status_info['batch_id']}:")
        self.logger.info(f"   📅 Estado: {status_info['status']}")
        self.logger.info(f"   📋 Total requests: {counts['total']}")
        self.logger.info(f"   ✅ Completadas: {counts['completed']}")
        self.logger.info(f"   ❌ Fallidas: {counts['failed']}")
        
        if status_info["completed_at"]:
            self.logger.info(f"   ✅ Completado en: {status_info['completed_at']}")
        if status_info["failed_at"]:
            self.logger.info(f"   ❌ Falló en: {status_info['failed_at']}")
        
        if status_info["output_file_id"]:
            self.logger.info(f"   📄 Archivo de salida: {status_info['output_file_id']}")
        else:
            self.logger.warning(f"   ⚠️ No hay archivo de salida disponible")
            
        if status_info["error_file_id"]:
            self.logger.info(f"   ⚠️ Archivo de errores: {status_info['error_file_id']}")
        else:
            self.logger.info(f"   ✅ No hay archivo de errores")
            
        # Mostrar información adicional para diagnóstico
        print(f"\n🔍 Información detallada del batch:")
        print(f"   - Total de requests: {status_info['request_counts']['total']}")
        print(f"   - Requests completados: {status_info['request_counts']['completed']}")
        print(f"   - Requests fallidos: {status_info['request_counts']['failed']}")
        print(f"   - Output file ID: {status_info['output_file_id'] or 'None'}")
        print(f"   - Error file ID: {status_info['error_file_id'] or 'None'}")
    
    def download_results(self, batch_id: str, project_name: str) -> Dict[str, Any]:
        """
        Descarga y procesa los resultados de un batch completado.
        
        Args:
            batch_id: ID del batch job
            project_name: Nombre del proyecto
            
        Returns:
            Dict con información de los resultados procesados
        """
        try:
            # Verificar estado del batch
            status_info = self.check_batch_status(batch_id)
            
            if status_info["status"] != "completed":
                raise ValueError(f"El batch {batch_id} no está completado. Estado actual: {status_info['status']}")
            
            if not status_info["output_file_id"]:
                raise ValueError(f"No hay archivo de salida disponible para el batch {batch_id}")
            
            # Descargar archivo de resultados
            output_file_id = status_info["output_file_id"]
            self.logger.info(f"📥 Descargando resultados del batch {batch_id}...")
            
            file_response = self.client.files.content(output_file_id)
            results_content = file_response.read().decode('utf-8')
            
            # Crear directorio para logs de OpenAI
            openai_logs_dir = os.path.join("local", "output_docs", project_name, "openai_logs")
            os.makedirs(openai_logs_dir, exist_ok=True)
            
            # Guardar archivo de resultados raw
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            raw_results_file = os.path.join(openai_logs_dir, f"batch_results_raw_{project_name}_{batch_id}_{timestamp}.jsonl")
            
            with open(raw_results_file, 'w', encoding='utf-8') as f:
                f.write(results_content)
            
            self.logger.info(f"💾 Resultados raw guardados en: {raw_results_file}")
            
            # Procesar resultados
            processed_results = self._process_batch_results(results_content, project_name, batch_id)
            
            # Descargar errores si existen
            if status_info["error_file_id"]:
                self._download_error_file(status_info["error_file_id"], project_name, batch_id)
            
            return {
                "batch_id": batch_id,
                "project_name": project_name,
                "raw_results_file": raw_results_file,
                "processed_results": processed_results,
                "status_info": status_info
            }
            
        except Exception as e:
            self.logger.error(f"Error descargando resultados del batch {batch_id}: {str(e)}")
            raise
    
    def _download_error_file(self, error_file_id: str, project_name: str, batch_id: str):
        """Descarga el archivo de errores si existe."""
        try:
            self.logger.info(f"⚠️ Descargando archivo de errores...")
            
            error_response = self.client.files.content(error_file_id)
            error_content = error_response.read().decode('utf-8')
            
            # Crear directorio para logs de OpenAI
            openai_logs_dir = os.path.join("local", "output_docs", project_name, "openai_logs")
            os.makedirs(openai_logs_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_file = os.path.join(openai_logs_dir, f"batch_errors_{project_name}_{batch_id}_{timestamp}.jsonl")
            
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write(error_content)
            
            self.logger.warning(f"⚠️ Errores guardados en: {error_file}")
            
            # Contar errores
            error_count = len([line for line in error_content.strip().split('\n') if line.strip()])
            self.logger.warning(f"⚠️ Total de errores encontrados: {error_count}")
            
        except Exception as e:
            self.logger.error(f"Error descargando archivo de errores: {str(e)}")
    
    def _process_batch_results(self, results_content: str, project_name: str, batch_id: str) -> Dict[str, Any]:
        """
        Procesa los resultados del batch y los organiza por documento y prompt.
        
        Args:
            results_content: Contenido JSONL de los resultados
            project_name: Nombre del proyecto
            batch_id: ID del batch
            
        Returns:
            Dict con resultados organizados
        """
        try:
            # Crear directorio para logs de OpenAI
            openai_logs_dir = os.path.join("local", "output_docs", project_name, "openai_logs")
            os.makedirs(openai_logs_dir, exist_ok=True)
            
            results_by_document = {}
            results_by_prompt = {"auditoria": [], "desembolsos": [], "productos": []}
            total_processed = 0
            successful_responses = 0
            failed_responses = 0
            
            # Procesar cada línea del JSONL
            for line in results_content.strip().split('\n'):
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
                        self.logger.warning(f"⚠️ Respuesta fallida para {custom_id}: {response.get('status_code')}")
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error parseando línea de resultado: {str(e)}")
                    failed_responses += 1
            
            # Generar archivos de salida organizados
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Guardar resultados por documento
            documents_file = os.path.join(openai_logs_dir, f"results_by_document_{project_name}_{timestamp}.json")
            with open(documents_file, 'w', encoding='utf-8') as f:
                json.dump(results_by_document, f, indent=2, ensure_ascii=False)
            
            # Guardar resultados por prompt
            prompts_file = os.path.join(openai_logs_dir, f"results_by_prompt_{project_name}_{timestamp}.json")
            with open(prompts_file, 'w', encoding='utf-8') as f:
                json.dump(results_by_prompt, f, indent=2, ensure_ascii=False)
            
            # Crear carpeta de salida para archivos separados por prompt
            output_dir = Path(f"local/output_docs/{project_name}/results")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Extraer y guardar contenido por tipo de prompt
            prompt_files = {}
            for prompt_type, results in results_by_prompt.items():
                if results:  # Solo procesar si hay resultados
                    # Extraer solo el contenido de cada resultado
                    content_list = []
                    for result in results:
                        if result.get('content'):
                            content = result['content']
                            parsed_content = self._extract_json_content(content)
                            content_list.append(parsed_content)
                    
                    # Guardar archivo separado por prompt
                    prompt_filename = f"{prompt_type}.json"
                    prompt_filepath = output_dir / prompt_filename
                    
                    with open(prompt_filepath, 'w', encoding='utf-8') as f:
                        json.dump(content_list, f, indent=2, ensure_ascii=False)
                    
                    prompt_files[prompt_type] = str(prompt_filepath)
                    self.logger.info(f"📄 Archivo {prompt_type}: {prompt_filepath} ({len(content_list)} elementos)")
            
            # Generar resumen
            summary = {
                "project_name": project_name,
                "batch_id": batch_id,
                "processed_at": datetime.now().isoformat(),
                "statistics": {
                    "total_processed": total_processed,
                    "successful_responses": successful_responses,
                    "failed_responses": failed_responses,
                    "success_rate": (successful_responses / total_processed * 100) if total_processed > 0 else 0
                },
                "output_files": {
                    "by_document": documents_file,
                    "by_prompt": prompts_file,
                    "separated_prompts": prompt_files
                },
                "documents_processed": len(results_by_document),
                "prompts_results": {
                    prompt_type: len(results) for prompt_type, results in results_by_prompt.items()
                }
            }
            
            # Guardar resumen
            summary_file = os.path.join(openai_logs_dir, f"batch_summary_{project_name}_{timestamp}.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            # Log resumen
            self.logger.info(f"📊 Procesamiento completado:")
            self.logger.info(f"   📄 Total procesadas: {total_processed}")
            self.logger.info(f"   ✅ Exitosas: {successful_responses}")
            self.logger.info(f"   ❌ Fallidas: {failed_responses}")
            self.logger.info(f"   📈 Tasa de éxito: {summary['statistics']['success_rate']:.1f}%")
            self.logger.info(f"   📁 Archivos generados:")
            self.logger.info(f"      📋 Por documento: {documents_file}")
            self.logger.info(f"      🎯 Por prompt: {prompts_file}")
            self.logger.info(f"      📊 Resumen: {summary_file}")
            if prompt_files:
                self.logger.info(f"      🗂️ Archivos separados por prompt:")
                for prompt_type, filepath in prompt_files.items():
                    self.logger.info(f"         {prompt_type}: {filepath}")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error procesando resultados del batch: {str(e)}")
            raise
    
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
        
        # Caso 3: Buscar JSON dentro del texto
        import re
        json_pattern = r'```json\s*\n([\s\S]*?)\n```'
        match = re.search(json_pattern, content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                self.logger.warning(f"No se pudo parsear JSON encontrado en el texto")
        
        # Si no se puede parsear de ninguna manera, devolver el contenido original
        return content

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
                self.logger.warning(f"⚠️ Formato de custom_id inválido: {custom_id}")
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
                self.logger.warning(f"⚠️ No hay choices en la respuesta para {custom_id}")
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

def main():
    """
    Función principal para procesar resultados de batch jobs.
    Uso: python results.py [batch_id] [project_name]
    """
    import sys
    
    if len(sys.argv) < 3:
        print("Uso: python results.py <batch_id> <project_name>")
        print("Ejemplo: python results.py batch_abc123 CFA009660")
        return
    
    batch_id = sys.argv[1]
    project_name = sys.argv[2]
    
    processor = BatchResultsProcessor()
    
    try:
        # Verificar estado
        print(f"🔍 Verificando estado del batch {batch_id}...")
        status_info = processor.check_batch_status(batch_id)
        print(f"📋 Estado actual: {status_info['status']}")
        
        # Mostrar información detallada del batch
        processor._log_batch_summary(status_info)
        
        if status_info['status'] == 'completed':
            # Verificar si hay archivo de salida antes de intentar descargarlo
            if status_info['output_file_id']:
                print(f"✅ Batch completado, procesando resultados...")
                results = processor.download_results(batch_id, project_name)
                print(f"🎉 Resultados procesados exitosamente")
            else:
                print(f"⚠️ El batch está completado pero no tiene archivo de salida.")
                print(f"💡 Posibles causas:")
                print(f"   - Todos los requests fallaron")
                print(f"   - Error en el procesamiento del batch")
                print(f"   - Problema con la configuración del batch")
                if status_info['error_file_id']:
                    print(f"📄 Hay un archivo de errores disponible: {status_info['error_file_id']}")
                    try:
                        processor._download_error_file(status_info['error_file_id'], project_name, batch_id)
                    except Exception as e:
                        print(f"❌ Error descargando archivo de errores: {e}")
                return 1  # Código de error
        elif status_info['status'] in ['validating', 'in_progress', 'finalizing']:
            # Esperar completación
            print(f"⏳ Esperando completación del batch...")
            if processor.wait_for_completion(batch_id, max_wait_minutes=60):
                results = processor.download_results(batch_id, project_name)
                print(f"🎉 Resultados procesados exitosamente")
            else:
                print(f"❌ El batch no se completó en el tiempo esperado")
        else:
            print(f"❌ El batch está en estado: {status_info['status']}")
            
    except Exception as e:
        print(f"❌ Error procesando batch: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())