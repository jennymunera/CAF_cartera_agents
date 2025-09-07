import os
import json
import logging
import re
import time
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from openai import AzureOpenAI
from utils.app_insights_logger import get_logger
from utils.blob_storage_client import BlobStorageClient

# Configurar logging para reducir verbosidad de Azure
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)

class OpenAIBatchProcessor:
    """
    Procesador de Azure OpenAI Batch API para análisis de documentos.
    Genera batch jobs para procesar documentos y chunks usando 3 prompts específicos.
    """
    
    def __init__(self):
        self.logger = get_logger('openai_batch_processor')
        self._setup_client()
        self._load_prompts()
        
    def _setup_client(self):
        """Configura el cliente de Azure OpenAI usando variables de entorno."""
        try:
            # Obtener configuración del .env
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://oai-poc-idatafactory-cr.openai.azure.com/')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
            self.deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o-2')
            
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY no encontrada en variables de entorno")
            
            self.client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=endpoint,
                api_key=api_key
            )
            
            self.logger.info(f"Cliente Azure OpenAI Batch configurado exitosamente")
            self.logger.info(f"Endpoint: {endpoint}")
            self.logger.info(f"Deployment: {self.deployment_name}")
            
        except Exception as e:
            self.logger.error(f"Error configurando cliente Azure OpenAI: {str(e)}")
            raise
    
    def _load_prompts(self):
        """Carga los prompts desde archivos de texto"""
        prompts = {}
        prompt_files = {
            'auditoria': 'prompt Auditoria.txt',
            'desembolsos': 'prompt Desembolsos.txt',
            'productos': 'prompt Productos.txt'
        }
        
        for key, filename in prompt_files.items():
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    prompts[key] = file.read().strip()
                    self.logger.info(f"Prompt cargado exitosamente: {filename}")
            except FileNotFoundError:
                error_msg = f"Archivo de prompt no encontrado: {filename}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            except Exception as e:
                error_msg = f"Error al cargar prompt {filename}: {str(e)}"
                self.logger.error(error_msg)
                raise
        
        # Asignar prompts a atributos de instancia para compatibilidad
        self.prompt_auditoria = prompts['auditoria']
        self.prompt_desembolsos = prompts['desembolsos']
        self.prompt_productos = prompts['productos']
        
        # Crear diccionario de prompts para acceso por número
        self.prompts = {
            'prompt_1': prompts['productos'],
            'prompt_2': prompts['desembolsos'], 
            'prompt_3': prompts['auditoria']
        }
        
        self.logger.info("✅ Prompts definidos exitosamente")
    
    def _get_document_prefix(self, document_content: Dict[str, Any]) -> str:
        """
        Extrae el prefijo del documento basado en el nombre del archivo.
        
        Args:
            document_content: Contenido del documento
            
        Returns:
            Prefijo del documento en mayúsculas (ej: 'IXP', 'ROP', 'INI')
        """
        # Obtener nombre del documento
        document_name = document_content.get('document_name', document_content.get('filename', ''))
        
        # Si es un chunk, obtener el nombre base
        if '_chunk_' in document_name:
            document_name = document_name.split('_chunk_')[0]
        
        # Extraer prefijo (primeras 3 letras antes del primer guión)
        if '-' in document_name:
            prefix = document_name.split('-')[0].upper()
        else:
            # Si no hay guión, tomar las primeras 3 letras
            prefix = document_name[:3].upper()
        
        return prefix
    
    def _should_process_with_prompt(self, document_content: Dict[str, Any], prompt_number: int) -> bool:
        """
        Determina si un documento debe ser procesado con un prompt específico.
        
        Args:
            document_content: Contenido del documento
            prompt_number: Número del prompt (1, 2, 3)
            
        Returns:
            True si debe procesarse, False si no
        """
        document_prefix = self._get_document_prefix(document_content)
        
        # Filtros por prefijo según prompt
        if prompt_number == 1:  # Auditoría
            allowed_prefixes = ['IXP']
        elif prompt_number == 2:  # Productos
            allowed_prefixes = ['ROP', 'INI', 'DEC', 'IFS']
        elif prompt_number == 3:  # Desembolsos
            allowed_prefixes = ['ROP', 'INI', 'DEC']
        else:
            return False
        
        return document_prefix in allowed_prefixes
    
    def _create_batch_request(self, custom_id: str, prompt: str, content: str) -> Dict[str, Any]:
        """
        Crea una request individual para el batch job.
        
        Args:
            custom_id: ID único para identificar la request
            prompt: Prompt a usar
            content: Contenido del documento
            
        Returns:
            Dict con la estructura de request para batch
        """
        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/chat/completions",
            "body": {
                "model": self.deployment_name,
                "messages": [
                    {
                        "role": "system", 
                        "content": "Eres un Analista experto en documentos de auditoría. Tu tarea es extraer información específica siguiendo un formato estructurado y emitiendo conceptos normalizados para entregar en formato JSON lo solicitado."
                    },
                    {
                        "role": "user", 
                        "content": f"{prompt}\n\nDocumento:\n{content}"
                    }
                ],
                "max_completion_tokens": 1000,
                "temperature": 0.3
            }
        }
    
    def create_batch_job(self, project_name: str) -> Dict[str, Any]:
        """
        Crea un batch job para procesar todos los documentos de un proyecto usando BlobStorageClient.
        
        Args:
            project_name: Nombre del proyecto (ej: CFA009660)
            
        Returns:
            Dict con información del batch job creado
        """
        self.logger.info(f"🚀 Creando batch job para proyecto: {project_name}")
        
        batch_requests = []
        documents_info = []
        
        try:
            blob_client = BlobStorageClient()
            
            # Procesar documentos DI desde blob storage
            di_documents = blob_client.list_processed_documents(project_name)
            for doc_name in di_documents:
                if doc_name.endswith('.json'):
                    self._add_document_to_batch_from_blob(doc_name, project_name, batch_requests, documents_info, blob_client, 'DI')
            
            # Procesar chunks desde blob storage
            chunk_documents = blob_client.list_chunks(project_name)
            for chunk_name in chunk_documents:
                if chunk_name.endswith('.json'):
                    self._add_document_to_batch_from_blob(chunk_name, project_name, batch_requests, documents_info, blob_client, 'chunks')
            
            if not batch_requests:
                raise ValueError(f"No se encontraron documentos para procesar en proyecto {project_name}")
            
            # Crear archivo JSONL temporal (formato requerido por Azure Batch API)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
                for request in batch_requests:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
                batch_input_file = f.name
            
            self.logger.info(f"📄 Archivo batch temporal creado: {batch_input_file} ({len(batch_requests)} requests)")
            
            # Subir archivo a Azure
            uploaded = self.client.files.create(
                file=open(batch_input_file, "rb"),
                purpose="batch"
            )
            
            # Limpiar archivo temporal
            os.unlink(batch_input_file)
            
            # Crear batch job
            batch = self.client.batches.create(
                input_file_id=uploaded.id,
                endpoint="/chat/completions",
                completion_window="24h",
                metadata={"project": project_name}
            )
            
            batch_info = {
                "batch_id": batch.id,
                "project_name": project_name,
                "input_file_id": uploaded.id,
                "created_at": datetime.now().isoformat(),
                "status": batch.status,
                "total_requests": len(batch_requests),
                "documents_info": documents_info
            }
            
            # Guardar información del batch en blob storage
            batch_info_content = json.dumps(batch_info, indent=2, ensure_ascii=False)
            batch_info_path = f"basedocuments/{project_name}/processed/openai_logs/batch_info_{project_name}_{batch.id}.json"
            blob_client.upload_blob(batch_info_path, batch_info_content)
            
            self.logger.info(f"✅ Batch job creado exitosamente:")
            self.logger.info(f"   📋 Batch ID: {batch.id}")
            self.logger.info(f"   📊 Total requests: {len(batch_requests)}")
            self.logger.info(f"   📁 Info guardada en blob: {batch_info_path}")
            
            return batch_info
            
        except Exception as e:
            self.logger.error(f"Error creando batch job: {str(e)}")
            raise
    
    def process_chunks(self, chunks: List[Dict], document_name: str, queue_type: str) -> Dict[str, Any]:
        """
        Procesa chunks directamente para crear un batch job.
        
        Args:
            chunks: Lista de chunks del documento
            document_name: Nombre del documento
            queue_type: Tipo de cola (no usado, mantenido por compatibilidad)
            
        Returns:
            Dict con información del batch job creado
        """
        try:
            self.logger.info(f"🚀 Procesando {len(chunks)} chunks para documento: {document_name}")
            
            batch_requests = []
            documents_info = []
            
            for i, chunk in enumerate(chunks):
                # Crear contenido del chunk con información del documento
                chunk_content = {
                    'content': chunk.get('content', ''),
                    'document_name': document_name,
                    'chunk_index': i
                }
                
                content_text = chunk_content.get('content', '')
                
                doc_info = {
                    "document_name": document_name,
                    "chunk_index": i,
                    "prefix": self._get_document_prefix(chunk_content),
                    "prompts_applied": []
                }
                
                # Verificar y agregar prompts aplicables
                prompts = [
                    (1, "auditoria", self.prompt_auditoria),
                    (2, "desembolsos", self.prompt_desembolsos),
                    (3, "productos", self.prompt_productos)
                ]
                
                for prompt_num, prompt_type, prompt_text in prompts:
                    if self._should_process_with_prompt(chunk_content, prompt_num):
                        custom_id = f"{document_name}_{prompt_type}_chunk_{i:03d}"
                        
                        request = self._create_batch_request(custom_id, prompt_text, content_text)
                        batch_requests.append(request)
                        doc_info["prompts_applied"].append(prompt_type)
                
                if doc_info["prompts_applied"]:
                    documents_info.append(doc_info)
                    self.logger.info(f"📄 Chunk {i} agregado al batch (prompts: {doc_info['prompts_applied']})")
            
            if not batch_requests:
                raise ValueError(f"No se generaron requests para el documento {document_name}")
            
            # Crear archivo JSONL temporal
            temp_batch_file = f"/tmp/batch_input_{document_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            
            with open(temp_batch_file, 'w', encoding='utf-8') as f:
                for request in batch_requests:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
            
            self.logger.info(f"📄 Archivo batch temporal creado: {temp_batch_file} ({len(batch_requests)} requests)")
            
            # Subir archivo a Azure
            uploaded = self.client.files.create(
                file=open(temp_batch_file, "rb"),
                purpose="batch"
            )
            
            # Crear batch job
            batch = self.client.batches.create(
                input_file_id=uploaded.id,
                endpoint="/chat/completions",
                completion_window="24h",
                metadata={"document": document_name}
            )
            
            batch_info = {
                "batch_id": batch.id,
                "document_name": document_name,
                "input_file_id": uploaded.id,
                "input_file_name": temp_batch_file,
                "created_at": datetime.now().isoformat(),
                "status": batch.status,
                "total_requests": len(batch_requests),
                "documents_info": documents_info
            }
            
            self.logger.info(f"✅ Batch job creado exitosamente:")
            self.logger.info(f"   📋 Batch ID: {batch.id}")
            self.logger.info(f"   📊 Total requests: {len(batch_requests)}")
            
            # Limpiar archivo temporal
            try:
                os.remove(temp_batch_file)
            except:
                pass
            
            return batch_info
            
        except Exception as e:
            self.logger.error(f"Error procesando chunks: {str(e)}")
            raise

    def _add_document_to_batch_from_blob(self, doc_name: str, project_name: str, batch_requests: List[Dict], documents_info: List[Dict], blob_client: BlobStorageClient, doc_type: str):
        """
        Añade un documento desde blob storage al batch job.
        
        Args:
            doc_name: Nombre del documento
            project_name: Nombre del proyecto
            batch_requests: Lista de requests del batch
            documents_info: Lista de información de documentos
            blob_client: Cliente de blob storage
            doc_type: Tipo de documento ('DI' o 'chunks')
        """
        try:
            # Determinar la subcarpeta según el tipo
            if doc_type == 'DI':
                subfolder = 'DI'
            else:  # chunks
                subfolder = 'chunks'
            
            # Descargar contenido del blob usando el método correcto
            doc_data = blob_client.load_processed_document(project_name, subfolder, doc_name)
            if not doc_data:
                self.logger.warning(f"No se pudo descargar el documento: {doc_name} desde {subfolder}")
                return
            
            # Asegurar que el nombre del documento esté en los datos
            if 'document_name' not in doc_data and 'filename' not in doc_data:
                doc_data['document_name'] = doc_name
            
            # Obtener prefijo del documento
            prefix = self._get_document_prefix(doc_data)
            self.logger.info(f"🔍 Documento: {doc_name}, Prefijo extraído: {prefix}")
            
            # Procesar con cada prompt según las reglas
            prompts_applied = []
            
            for prompt_num in [1, 2, 3]:
                should_process = self._should_process_with_prompt(doc_data, prompt_num)
                self.logger.info(f"📋 Prompt {prompt_num} para {doc_name}: {'✅ SÍ' if should_process else '❌ NO'}")
                if should_process:
                    custom_id = f"{project_name}_{Path(doc_name).stem}_prompt{prompt_num}"
                    prompt = self.prompts[f'prompt_{prompt_num}']
                    content = doc_data.get('content', '')
                    
                    batch_request = self._create_batch_request(custom_id, prompt, content)
                    batch_requests.append(batch_request)
                    
                    # Mapear número de prompt a tipo
                    prompt_types = {1: "auditoria", 2: "desembolsos", 3: "productos"}
                    prompts_applied.append(prompt_types[prompt_num])
                    
                    self.logger.info(f"📄 Añadido al batch: {custom_id} (Prefijo: {prefix})")
            
            # Añadir información del documento solo si se aplicaron prompts
            if prompts_applied:
                documents_info.append({
                    "document_name": doc_name,
                    "document_type": doc_type,
                    "subfolder": subfolder,
                    "prefix": prefix,
                    "prompts_applied": prompts_applied,
                    "processed_at": datetime.now().isoformat()
                })
                self.logger.info(f"📄 Documento agregado: {doc_name} (prompts: {prompts_applied})")
            else:
                self.logger.info(f"⏭️ Saltando documento: {doc_name} (no aplica ningún prompt)")
            
        except Exception as e:
            self.logger.error(f"Error procesando documento {doc_name}: {str(e)}")
            raise

    def _add_document_to_batch(self, doc_path: str, project_name: str, batch_requests: List[Dict], documents_info: List[Dict]):
        """
        Agrega un documento al batch con los prompts aplicables.
        
        Args:
            doc_path: Ruta al documento
            project_name: Nombre del proyecto
            batch_requests: Lista de requests del batch
            documents_info: Lista de información de documentos
        """
        try:
            # Cargar contenido del documento
            with open(doc_path, 'r', encoding='utf-8') as f:
                document_content = json.load(f)
            
            document_content['project_name'] = project_name
            content_text = document_content.get('content', '')
            
            # Extraer información del documento
            document_name = document_content.get('document_name', document_content.get('filename', Path(doc_path).stem))
            chunk_index = None
            if '_chunk_' in str(doc_path):
                chunk_match = re.search(r'_chunk_(\d+)', str(doc_path))
                if chunk_match:
                    chunk_index = int(chunk_match.group(1))
            
            doc_info = {
                "document_name": document_name,
                "file_path": doc_path,
                "chunk_index": chunk_index,
                "prefix": self._get_document_prefix(document_content),
                "prompts_applied": []
            }
            
            # Verificar y agregar prompts aplicables
            prompts = [
                (1, "auditoria", self.prompt_auditoria),
                (2, "desembolsos", self.prompt_desembolsos),
                (3, "productos", self.prompt_productos)
            ]
            
            for prompt_num, prompt_type, prompt_text in prompts:
                if self._should_process_with_prompt(document_content, prompt_num):
                    custom_id = f"{project_name}_{document_name}_{prompt_type}"
                    if chunk_index is not None:
                        custom_id += f"_chunk_{chunk_index:03d}"
                    
                    request = self._create_batch_request(custom_id, prompt_text, content_text)
                    batch_requests.append(request)
                    doc_info["prompts_applied"].append(prompt_type)
            
            if doc_info["prompts_applied"]:
                documents_info.append(doc_info)
                self.logger.info(f"📄 Agregado al batch: {document_name} (prompts: {doc_info['prompts_applied']})")
            else:
                self.logger.info(f"⏭️ Saltando documento: {document_name} (no aplica ningún prompt)")
                
        except Exception as e:
            self.logger.error(f"Error procesando documento {doc_path}: {str(e)}")
            raise