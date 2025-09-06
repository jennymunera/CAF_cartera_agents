#!/usr/bin/env python3
"""
Cliente para Azure Blob Storage que maneja la estructura de documentos en la nube.

Estructura esperada en el Storage Account 'asmvpcarteracr':
caf-documents/
├── basedocuments/CAF123/
│   ├── raw/                    # Equivalente a input_docs
│   │   ├── file_001.pdf
│   │   ├── file_002.docx
│   ├── processed/              # Equivalente a output_docs
│   │   ├── DI/                 # Document Intelligence results
│   │   ├── chunks/             # Chunked documents
│   └── results/                # Final results
"""

import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
from datetime import datetime
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from utils.app_insights_logger import get_logger

logger = get_logger('blob_storage_client')


class BlobStorageClient:
    """
    Cliente para manejar operaciones con Azure Blob Storage.
    """
    
    def __init__(self, storage_account_name: str = "asmvpcarteracr", 
                 container_name: str = "caf-documents"):
        """
        Inicializa el cliente de Blob Storage.
        
        Args:
            storage_account_name: Nombre del storage account
            container_name: Nombre del contenedor
        """
        self.storage_account_name = storage_account_name
        self.container_name = container_name
        
        # Obtener connection string desde variables de entorno
        connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING no encontrada en variables de entorno")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)
        
        logger.info(f"Cliente Blob Storage inicializado: {storage_account_name}/{container_name}")
    
    def _get_project_base_path(self, project_name: str) -> str:
        """
        Obtiene la ruta base del proyecto en el blob storage.
        
        Args:
            project_name: Nombre del proyecto (ej: CAF123)
            
        Returns:
            Ruta base del proyecto
        """
        return f"basedocuments/{project_name}"
    
    def _get_raw_documents_path(self, project_name: str) -> str:
        """
        Obtiene la ruta de documentos raw (equivalente a input_docs).
        """
        return f"{self._get_project_base_path(project_name)}/raw"
    
    def _get_processed_documents_path(self, project_name: str) -> str:
        """
        Obtiene la ruta de documentos procesados (equivalente a output_docs).
        """
        return f"{self._get_project_base_path(project_name)}/processed"
    
    def _get_results_path(self, project_name: str) -> str:
        """
        Obtiene la ruta de resultados finales.
        """
        return f"{self._get_project_base_path(project_name)}/results"
    
    def list_projects(self) -> List[str]:
        """
        Lista todos los proyectos disponibles en basedocuments/.
        
        Returns:
            Lista de nombres de proyectos
        """
        try:
            projects = set()
            blobs = self.container_client.list_blobs(name_starts_with="basedocuments/")
            
            for blob in blobs:
                # Extraer nombre del proyecto de la ruta: basedocuments/CAF123/...
                path_parts = blob.name.split('/')
                if len(path_parts) >= 2 and path_parts[0] == "basedocuments":
                    projects.add(path_parts[1])
            
            project_list = list(projects)
            logger.info(f"Proyectos encontrados: {project_list}")
            return project_list
            
        except Exception as e:
            logger.error(f"Error listando proyectos: {str(e)}")
            return []
    
    def list_raw_documents(self, project_name: str) -> List[str]:
        """
        Lista documentos raw de un proyecto (equivalente a input_docs).
        
        Args:
            project_name: Nombre del proyecto
            
        Returns:
            Lista de nombres de archivos en raw/
        """
        try:
            raw_path = self._get_raw_documents_path(project_name)
            blobs = self.container_client.list_blobs(name_starts_with=f"{raw_path}/")
            
            documents = []
            for blob in blobs:
                # Extraer solo el nombre del archivo
                file_name = blob.name.split('/')[-1]
                if file_name:  # Evitar carpetas vacías
                    documents.append(file_name)
            
            logger.info(f"Documentos raw en {project_name}: {documents}")
            return documents
            
        except Exception as e:
            logger.error(f"Error listando documentos raw para {project_name}: {str(e)}")
            return []
    
    def upload_raw_document(self, project_name: str, document_name: str, content: bytes) -> str:
        """
        Sube un documento raw a la carpeta raw/.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            content: Contenido del documento en bytes
            
        Returns:
            Ruta del blob guardado
        """
        try:
            blob_path = f"{self._get_raw_documents_path(project_name)}/{document_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Determinar content type basado en la extensión
            extension = Path(document_name).suffix.lower()
            content_type_map = {
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.doc': 'application/msword',
                '.txt': 'text/plain',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.xls': 'application/vnd.ms-excel'
            }
            content_type = content_type_map.get(extension, 'application/octet-stream')
            
            blob_client.upload_blob(content, overwrite=True, content_type=content_type)
            logger.info(f"Documento raw subido: {blob_path}")
            return blob_path
            
        except Exception as e:
            logger.error(f"Error subiendo documento raw {document_name}: {str(e)}")
            raise
    
    def download_raw_document(self, project_name: str, document_name: str) -> bytes:
        """
        Descarga un documento raw como bytes.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            
        Returns:
            Contenido del documento como bytes
        """
        try:
            blob_path = f"{self._get_raw_documents_path(project_name)}/{document_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            
            logger.info(f"Descargando documento: {blob_path}")
            return blob_client.download_blob().readall()
            
        except ResourceNotFoundError:
            logger.error(f"Documento no encontrado: {blob_path}")
            raise FileNotFoundError(f"Documento {document_name} no encontrado en proyecto {project_name}")
        except Exception as e:
            logger.error(f"Error descargando documento {document_name}: {str(e)}")
            raise
    
    def save_processed_document(self, project_name: str, subfolder: str, 
                              document_name: str, content: Any) -> str:
        """
        Guarda un documento procesado en la carpeta processed/.
        
        Args:
            project_name: Nombre del proyecto
            subfolder: Subcarpeta (ej: 'DI', 'chunks')
            document_name: Nombre del archivo
            content: Contenido a guardar (dict para JSON, str para texto, bytes para binario)
            
        Returns:
            Ruta del blob guardado
        """
        try:
            blob_path = f"{self._get_processed_documents_path(project_name)}/{subfolder}/{document_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Convertir contenido según el tipo
            if isinstance(content, dict):
                data = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
                content_type = 'application/json'
            elif isinstance(content, str):
                data = content.encode('utf-8')
                content_type = 'text/plain'
            elif isinstance(content, bytes):
                data = content
                content_type = 'application/octet-stream'
            else:
                raise ValueError(f"Tipo de contenido no soportado: {type(content)}")
            
            blob_client.upload_blob(data, overwrite=True, content_type=content_type)
            logger.info(f"Documento guardado: {blob_path}")
            return blob_path
            
        except Exception as e:
            logger.error(f"Error guardando documento procesado {document_name}: {str(e)}")
            raise
    
    def load_processed_document(self, project_name: str, subfolder: str, 
                              document_name: str) -> Any:
        """
        Carga un documento procesado desde processed/.
        
        Args:
            project_name: Nombre del proyecto
            subfolder: Subcarpeta (ej: 'DI', 'chunks')
            document_name: Nombre del archivo
            
        Returns:
            Contenido del documento (dict para JSON, str para texto)
        """
        try:
            blob_path = f"{self._get_processed_documents_path(project_name)}/{subfolder}/{document_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            
            data = blob_client.download_blob().readall()
            
            # Intentar decodificar como JSON primero
            try:
                return json.loads(data.decode('utf-8'))
            except json.JSONDecodeError:
                # Si no es JSON, devolver como string
                return data.decode('utf-8')
                
        except ResourceNotFoundError:
            logger.error(f"Documento procesado no encontrado: {blob_path}")
            raise FileNotFoundError(f"Documento procesado {document_name} no encontrado")
        except Exception as e:
            logger.error(f"Error cargando documento procesado {document_name}: {str(e)}")
            raise
    
    def save_result(self, project_name: str, result_name: str, content: Any) -> str:
        """
        Guarda un resultado final en la carpeta results/.
        
        Args:
            project_name: Nombre del proyecto
            result_name: Nombre del archivo de resultado
            content: Contenido a guardar
            
        Returns:
            Ruta del blob guardado
        """
        try:
            blob_path = f"{self._get_results_path(project_name)}/{result_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Convertir contenido según el tipo
            if isinstance(content, dict):
                data = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
                content_type = 'application/json'
            elif isinstance(content, str):
                data = content.encode('utf-8')
                content_type = 'text/plain'
            else:
                raise ValueError(f"Tipo de contenido no soportado: {type(content)}")
            
            blob_client.upload_blob(data, overwrite=True, content_type=content_type)
            logger.info(f"Resultado guardado: {blob_path}")
            return blob_path
            
        except Exception as e:
            logger.error(f"Error guardando resultado {result_name}: {str(e)}")
            raise
    
    def document_exists_in_processed(self, project_name: str, subfolder: str, 
                                   document_name: str) -> bool:
        """
        Verifica si un documento ya existe en processed/.
        
        Args:
            project_name: Nombre del proyecto
            subfolder: Subcarpeta (ej: 'DI', 'chunks')
            document_name: Nombre del documento
            
        Returns:
            True si el documento existe
        """
        try:
            blob_path = f"{self._get_processed_documents_path(project_name)}/{subfolder}/{document_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Error verificando existencia de documento {document_name}: {str(e)}")
            return False
    
    def create_temp_file_from_blob(self, project_name: str, document_name: str) -> str:
        """
        Crea un archivo temporal local desde un blob para procesamiento.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            
        Returns:
            Ruta del archivo temporal creado
        """
        try:
            # Descargar contenido del blob
            content = self.download_raw_document(project_name, document_name)
            
            # Crear archivo temporal
            suffix = Path(document_name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            logger.info(f"Archivo temporal creado: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error creando archivo temporal para {document_name}: {str(e)}")
            raise
    
    def cleanup_temp_file(self, temp_path: str) -> None:
        """
        Limpia un archivo temporal.
        
        Args:
            temp_path: Ruta del archivo temporal a eliminar
        """
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"Archivo temporal eliminado: {temp_path}")
        except Exception as e:
            logger.warning(f"Error eliminando archivo temporal {temp_path}: {str(e)}")