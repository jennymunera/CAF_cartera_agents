#!/usr/bin/env python3
"""
Script para verificar el contenido del Azure Blob Storage
"""

import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

def check_blob_content():
    """Verifica el contenido del blob storage"""
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Obtener connection string
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    
    if not connection_string:
        print("❌ Variable AZURE_STORAGE_CONNECTION_STRING no encontrada")
        return
    
    try:
        # Crear cliente de blob service
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Listar contenedores
        print("📦 Contenedores disponibles:")
        containers = blob_service_client.list_containers()
        container_names = []
        
        for container in containers:
            container_names.append(container.name)
            print(f"  - {container.name}")
        
        # Verificar contenedor caf-documents
        if 'caf-documents' in container_names:
            print("\n📁 Contenido del contenedor 'caf-documents':")
            container_client = blob_service_client.get_container_client('caf-documents')
            
            # Listar blobs con prefijo basedocuments
            blobs = container_client.list_blobs(name_starts_with='basedocuments/')
            
            projects = set()
            document_count = 0
            
            for blob in blobs:
                document_count += 1
                # Extraer nombre del proyecto
                path_parts = blob.name.split('/')
                if len(path_parts) >= 2:
                    projects.add(path_parts[1])
                
                print(f"  📄 {blob.name} ({blob.size} bytes)")
                
                # Limitar salida para no saturar
                if document_count >= 20:
                    print("  ... (mostrando solo los primeros 20 documentos)")
                    break
            
            print(f"\n📊 Resumen:")
            print(f"  - Total documentos encontrados: {document_count}")
            print(f"  - Proyectos: {list(projects)}")
            
            if document_count == 0:
                print("  ⚠️  No se encontraron documentos en basedocuments/")
        else:
            print("❌ Contenedor 'caf-documents' no encontrado")
            
    except Exception as e:
        print(f"❌ Error accediendo al blob storage: {e}")

if __name__ == "__main__":
    check_blob_content()