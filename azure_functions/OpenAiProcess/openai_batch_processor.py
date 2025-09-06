import os
import json
import logging
import re
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from utils.app_insights_logger import get_logger

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
        """Configura el cliente REST de Azure OpenAI usando variables de entorno."""
        try:
            # Obtener configuración del .env
            self.api_key = os.getenv('AZURE_OPENAI_API_KEY')
            self.endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://OpenAI-Tech2.openai.azure.com/')
            self.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
            self.deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'o4-mini-dadmi-batch')
            
            if not self.api_key:
                raise ValueError("AZURE_OPENAI_API_KEY no encontrada en variables de entorno")
            
            # Ensure endpoint ends with /
            if not self.endpoint.endswith('/'):
                self.endpoint += '/'
            
            self.logger.info(f"Cliente Azure OpenAI REST configurado exitosamente")
            self.logger.info(f"Endpoint: {self.endpoint}")
            self.logger.info(f"Deployment: {self.deployment_name}")
            
        except Exception as e:
            self.logger.error(f"Error configurando cliente Azure OpenAI: {str(e)}")
            raise
    
    def _make_rest_request(self, method: str, url: str, headers: Dict[str, str], data: Any = None, files: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make REST API request to Azure OpenAI"""
        try:
            if method.upper() == 'POST':
                if files:
                    response = requests.post(url, headers=headers, files=files, timeout=300)
                else:
                    response = requests.post(url, headers=headers, json=data, timeout=300)
            elif method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=300)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"REST API request failed: {str(e)}")
            raise
    
    def _upload_file_rest(self, file_path: str) -> Dict[str, Any]:
        """Upload file to Azure OpenAI using REST API"""
        headers = {
            'api-key': self.api_key
        }
        
        files = {
            'purpose': (None, 'batch'),
            'file': (os.path.basename(file_path), open(file_path, 'rb'), 'application/jsonl')
        }
        
        url = f"{self.endpoint}openai/files?api-version={self.api_version}"
        
        try:
            response = requests.post(url, headers=headers, files=files, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"File upload failed: {str(e)}")
            raise
        finally:
            files['file'][1].close()
    
    def _create_batch_rest(self, input_file_id: str, endpoint: str, completion_window: str, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Create batch job using REST API"""
        headers = {
            'api-key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        data = {
            'input_file_id': input_file_id,
            'endpoint': endpoint,
            'completion_window': completion_window,
            'metadata': metadata
        }
        
        url = f"{self.endpoint}openai/batches?api-version={self.api_version}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Batch creation failed: {str(e)}")
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
        elif prompt_number == 2:  # Desembolsos
            allowed_prefixes = ['ROP', 'INI', 'DEC', 'IFS']
        elif prompt_number == 3:  # Productos
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
        Crea un batch job para procesar todos los documentos de un proyecto.
        
        Args:
            project_name: Nombre del proyecto (ej: CFA009660)
            
        Returns:
            Dict con información del batch job creado
        """
        project_path = os.path.join("output_docs", project_name)
        self.logger.info(f"🚀 Creando batch job para proyecto: {project_name}")
        
        batch_requests = []
        documents_info = []
        
        try:
            # Procesar documentos DI
            di_path = os.path.join(project_path, 'DI')
            if os.path.exists(di_path):
                for filename in os.listdir(di_path):
                    if filename.endswith('.json'):
                        doc_path = os.path.join(di_path, filename)
                        self._add_document_to_batch(doc_path, project_name, batch_requests, documents_info)
            
            # Procesar chunks
            chunks_path = os.path.join(project_path, 'chunks')
            if os.path.exists(chunks_path):
                for filename in os.listdir(chunks_path):
                    if filename.endswith('.json'):
                        chunk_path = os.path.join(chunks_path, filename)
                        self._add_document_to_batch(chunk_path, project_name, batch_requests, documents_info)
            
            if not batch_requests:
                raise ValueError(f"No se encontraron documentos para procesar en {project_path}")
            
            # Crear directorio para logs de OpenAI
            openai_logs_dir = os.path.join("output_docs", project_name, "openai_logs")
            os.makedirs(openai_logs_dir, exist_ok=True)
            
            # Crear archivo JSONL (formato requerido por Azure Batch API)
            batch_input_file = os.path.join(openai_logs_dir, f"batch_input_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
            
            with open(batch_input_file, 'w', encoding='utf-8') as f:
                for request in batch_requests:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
            
            self.logger.info(f"📄 Archivo batch creado: {batch_input_file} ({len(batch_requests)} requests)")
            
            # Subir archivo a Azure usando REST API
            uploaded = self._upload_file_rest(batch_input_file)
            
            # Crear batch job usando REST API
            batch = self._create_batch_rest(
                input_file_id=uploaded['id'],
                endpoint="/chat/completions",
                completion_window="24h",
                metadata={"project": project_name}
            )
            
            batch_info = {
                "batch_id": batch['id'],
                "project_name": project_name,
                "input_file_id": uploaded['id'],
                "input_file_name": batch_input_file,
                "created_at": datetime.now().isoformat(),
                "status": batch.status,
                "total_requests": len(batch_requests),
                "documents_info": documents_info
            }
            
            # Guardar información del batch
            batch_info_file = os.path.join(openai_logs_dir, f"batch_info_{project_name}_{batch.id}.json")
            with open(batch_info_file, 'w', encoding='utf-8') as f:
                json.dump(batch_info, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Batch job creado exitosamente:")
            self.logger.info(f"   📋 Batch ID: {batch.id}")
            self.logger.info(f"   📊 Total requests: {len(batch_requests)}")
            self.logger.info(f"   📁 Info guardada en: {batch_info_file}")
            
            return batch_info
            
        except Exception as e:
            self.logger.error(f"Error creando batch job: {str(e)}")
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