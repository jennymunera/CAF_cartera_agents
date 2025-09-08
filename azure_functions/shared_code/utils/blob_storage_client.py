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
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
from datetime import datetime
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from shared_code.utils.app_insights_logger import get_logger

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
    
    def _normalize_filename(self, filename: str) -> str:
        """
        Normaliza un nombre de archivo para manejar caracteres especiales.
        
        Args:
            filename: Nombre del archivo original
            
        Returns:
            Nombre del archivo normalizado
        """
        # Normalizar usando NFD (Canonical Decomposition)
        return unicodedata.normalize('NFD', filename)
    
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
    
    def list_processed_documents(self, project_name: str) -> List[str]:
        """
        Lista documentos procesados por Document Intelligence de un proyecto.
        
        Args:
            project_name: Nombre del proyecto
            
        Returns:
            Lista de nombres de archivos en processed/DI/
        """
        try:
            processed_path = f"{self._get_processed_documents_path(project_name)}/DI"
            blobs = self.container_client.list_blobs(name_starts_with=f"{processed_path}/")
            
            documents = []
            for blob in blobs:
                # Extraer solo el nombre del archivo
                file_name = blob.name.split('/')[-1]
                if file_name:  # Evitar carpetas vacías
                    documents.append(file_name)
            
            logger.info(f"Documentos procesados DI en {project_name}: {documents}")
            return documents
            
        except Exception as e:
            logger.error(f"Error listando documentos procesados para {project_name}: {str(e)}")
            return []
    
    def list_chunks(self, project_name: str) -> List[str]:
        """
        Lista chunks de documentos de un proyecto.
        
        Args:
            project_name: Nombre del proyecto
            
        Returns:
            Lista de nombres de archivos en processed/chunks/
        """
        try:
            chunks_path = f"{self._get_processed_documents_path(project_name)}/chunks"
            blobs = self.container_client.list_blobs(name_starts_with=f"{chunks_path}/")
            
            chunks = []
            for blob in blobs:
                # Extraer solo el nombre del archivo
                file_name = blob.name.split('/')[-1]
                if file_name:  # Evitar carpetas vacías
                    chunks.append(file_name)
            
            logger.info(f"Chunks en {project_name}: {chunks}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error listando chunks para {project_name}: {str(e)}")
            return []
    
    def download_raw_document(self, project_name: str, document_name: str) -> bytes:
        """
        Descarga un documento raw como bytes.
        Intenta diferentes normalizaciones Unicode para encontrar el archivo.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            
        Returns:
            Contenido del documento como bytes
        """
        try:
            # Intentar con diferentes normalizaciones
            name_variations = [
                document_name,  # Original
                unicodedata.normalize('NFD', document_name),  # NFD
                unicodedata.normalize('NFC', document_name),  # NFC
                unicodedata.normalize('NFKD', document_name), # NFKD
                unicodedata.normalize('NFKC', document_name)  # NFKC
            ]
            
            # Eliminar duplicados manteniendo el orden
            unique_variations = []
            for name in name_variations:
                if name not in unique_variations:
                    unique_variations.append(name)
            
            # Probar cada variación
            for name_variant in unique_variations:
                try:
                    blob_path = f"{self._get_raw_documents_path(project_name)}/{name_variant}"
                    blob_client = self.container_client.get_blob_client(blob_path)
                    
                    if blob_client.exists():
                        logger.info(f"Descargando documento: {blob_path}")
                        return blob_client.download_blob().readall()
                        
                except ResourceNotFoundError:
                    continue
                except Exception as e:
                    logger.warning(f"Error probando variación {name_variant}: {str(e)}")
                    continue
            
            # Si llegamos aquí, no se encontró el archivo
            raise FileNotFoundError(f"Documento {document_name} no encontrado en proyecto {project_name}")
            
        except Exception as e:
            logger.error(f"Error descargando documento {document_name}: {str(e)}")
            raise
    
    def upload_raw_document(self, project_name: str, document_name: str, content: bytes) -> str:
        """
        Sube un documento raw al blob storage.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            content: Contenido del documento como bytes
            
        Returns:
            Ruta del blob creado
        """
        try:
            blob_path = f"{self._get_raw_documents_path(project_name)}/{document_name}"
            blob_client = self.container_client.get_blob_client(blob_path)
            
            logger.info(f"Subiendo documento: {blob_path}")
            blob_client.upload_blob(content, overwrite=True)
            
            return blob_path
            
        except Exception as e:
            logger.error(f"Error subiendo documento {document_name}: {str(e)}")
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
    
    def document_exists(self, project_name: str, document_name: str) -> bool:
        """
        Verifica si un documento existe en la carpeta raw del proyecto.
        Intenta diferentes normalizaciones Unicode para manejar caracteres especiales.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            
        Returns:
            bool: True si el documento existe, False en caso contrario
        """
        try:
            # Lista de variaciones del nombre a probar
            name_variations = [
                document_name,  # Original
                unicodedata.normalize('NFD', document_name),  # NFD
                unicodedata.normalize('NFC', document_name),  # NFC
                unicodedata.normalize('NFKD', document_name), # NFKD
                unicodedata.normalize('NFKC', document_name)  # NFKC
            ]
            
            # Eliminar duplicados manteniendo el orden
            unique_variations = []
            for name in name_variations:
                if name not in unique_variations:
                    unique_variations.append(name)
            
            # Probar cada variación
            for name_variant in unique_variations:
                blob_path = f"{self._get_raw_documents_path(project_name)}/{name_variant}"
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name, 
                    blob=blob_path
                )
                
                if blob_client.exists():
                    if name_variant != document_name:
                        logger.info(f"Documento encontrado con normalización diferente: {name_variant}")
                    return True
            
            # Si no se encuentra con ninguna variación, listar archivos similares
            logger.warning(f"Documento {document_name} no encontrado. Listando archivos similares...")
            self._list_similar_files(project_name, document_name)
            return False
            
        except Exception as e:
            logger.error(f"Error verificando existencia del documento {document_name}: {str(e)}")
            return False
    
    def _list_similar_files(self, project_name: str, target_name: str) -> None:
        """
        Lista archivos similares para ayudar en el diagnóstico.
        """
        try:
            raw_docs = self.list_raw_documents(project_name)
            logger.info(f"Archivos disponibles en {project_name}:")
            for doc in raw_docs[:10]:  # Limitar a 10 para no saturar logs
                logger.info(f"  - {doc}")
                
            # Buscar archivos que contengan parte del nombre
            base_name = target_name.split('.')[0] if '.' in target_name else target_name
            similar = [doc for doc in raw_docs if base_name.lower() in doc.lower()]
            if similar:
                logger.info(f"Archivos similares encontrados:")
                for doc in similar:
                    logger.info(f"  * {doc}")
        except Exception as e:
            logger.error(f"Error listando archivos similares: {str(e)}")

    def document_exists_in_processed(self, project_name: str, subfolder: str, 
                                   document_name: str) -> bool:
        """
        Verifica si un documento existe en la carpeta processed.
        
        Args:
            project_name: Nombre del proyecto
            subfolder: Subcarpeta dentro de processed (ej: 'DI', 'chunks')
            document_name: Nombre del documento
            
        Returns:
            bool: True si el documento existe, False en caso contrario
        """
        try:
            blob_path = f"{self._get_processed_documents_path(project_name)}/{subfolder}/{document_name}"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_path
            )
            return blob_client.exists()
        except Exception as e:
            logger.error(f"Error verificando existencia del documento {document_name}: {str(e)}")
            return False
    
    def create_temp_file_from_blob(self, project_name: str, document_name: str) -> str:
        """
        Crea un archivo temporal desde un blob del storage.
        Intenta diferentes normalizaciones Unicode para encontrar el archivo.
        
        Args:
            project_name: Nombre del proyecto
            document_name: Nombre del documento
            
        Returns:
            Ruta del archivo temporal creado
        """
        try:
            # Intentar descargar con diferentes normalizaciones
            document_content = None
            actual_name = document_name
            
            name_variations = [
                document_name,  # Original
                unicodedata.normalize('NFD', document_name),  # NFD
                unicodedata.normalize('NFC', document_name),  # NFC
                unicodedata.normalize('NFKD', document_name), # NFKD
                unicodedata.normalize('NFKC', document_name)  # NFKC
            ]
            
            # Eliminar duplicados manteniendo el orden
            unique_variations = []
            for name in name_variations:
                if name not in unique_variations:
                    unique_variations.append(name)
            
            # Probar cada variación
            for name_variant in unique_variations:
                try:
                    blob_path = f"{self._get_raw_documents_path(project_name)}/{name_variant}"
                    blob_client = self.container_client.get_blob_client(blob_path)
                    
                    if blob_client.exists():
                        logger.info(f"Descargando documento: {blob_path}")
                        document_content = blob_client.download_blob().readall()
                        actual_name = name_variant
                        break
                        
                except ResourceNotFoundError:
                    continue
                except Exception as e:
                    logger.warning(f"Error probando variación {name_variant}: {str(e)}")
                    continue
            
            if document_content is None:
                raise FileNotFoundError(f"Documento {document_name} no encontrado en proyecto {project_name}")
            
            # Crear archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(document_name).suffix)
            temp_file.write(document_content)
            temp_file.close()
            
            logger.info(f"Archivo temporal creado: {temp_file.name} (desde {actual_name})")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Error creando archivo temporal para {document_name}: {str(e)}")
            raise
    
    def upload_blob(self, blob_path: str, content: bytes, content_type: str = None) -> str:
        """
        Sube contenido a un blob específico.
        
        Args:
            blob_path: Ruta completa del blob
            content: Contenido como bytes
            content_type: Tipo de contenido MIME
            
        Returns:
            Ruta del blob creado
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_path)
            blob_client.upload_blob(content, overwrite=True, content_type=content_type)
            logger.info(f"Blob subido: {blob_path}")
            return blob_path
        except Exception as e:
            logger.error(f"Error subiendo blob {blob_path}: {str(e)}")
            raise
    
    def cleanup_temp_file(self, temp_path: str) -> None:
        """
        Elimina un archivo temporal.
        
        Args:
            temp_path: Ruta del archivo temporal a eliminar
        """
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"Archivo temporal eliminado: {temp_path}")
        except Exception as e:
            logger.warning(f"Error eliminando archivo temporal {temp_path}: {str(e)}")
    
    def list_blobs_with_prefix(self, prefix: str) -> List[str]:
        """
        Lista todos los blobs que comienzan con el prefijo especificado.
        
        Args:
            prefix: Prefijo para filtrar los blobs
            
        Returns:
            Lista de nombres de blobs que coinciden con el prefijo
        """
        try:
            blob_list = []
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            for blob in blobs:
                blob_list.append(blob.name)
            
            logger.info(f"Encontrados {len(blob_list)} blobs con prefijo '{prefix}'")
            return blob_list
            
        except Exception as e:
            logger.error(f"Error listando blobs con prefijo '{prefix}': {str(e)}")
            return []