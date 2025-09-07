#!/usr/bin/env python3
"""
Script para descargar y mostrar el contenido de un archivo batch_info específico
"""

import os
import json
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

def download_batch_info(blob_path):
    """Descarga y muestra el contenido de un archivo batch_info"""
    
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
        
        # Obtener cliente del contenedor
        container_client = blob_service_client.get_container_client('caf-documents')
        
        # Descargar el blob
        blob_client = container_client.get_blob_client(blob_path)
        
        print(f"📥 Descargando: {blob_path}")
        
        # Leer el contenido
        blob_data = blob_client.download_blob().readall()
        content = blob_data.decode('utf-8')
        
        # Parsear JSON
        batch_info = json.loads(content)
        
        print(f"\n📋 Contenido del batch_info:")
        print(json.dumps(batch_info, indent=2, ensure_ascii=False))
        
        # Verificar si contiene documents_info
        if 'documents_info' in batch_info:
            print(f"\n✅ Campo 'documents_info' encontrado con {len(batch_info['documents_info'])} documentos")
            
            # Verificar si los documentos tienen prompts_applied
            for i, doc in enumerate(batch_info['documents_info']):
                if 'prompts_applied' in doc:
                    print(f"  📄 Documento {i+1}: {doc.get('document_name', 'N/A')} - prompts_applied: {doc['prompts_applied']}")
                else:
                    print(f"  ❌ Documento {i+1}: {doc.get('document_name', 'N/A')} - SIN campo prompts_applied")
        else:
            print("❌ Campo 'documents_info' no encontrado")
            
    except Exception as e:
        print(f"❌ Error descargando el archivo: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python download_batch_info.py <blob_path>")
        print("Ejemplo: python download_batch_info.py CFA009660/processed/openai_logs/batch_info_CFA009660_batch_xxx.json")
        sys.exit(1)
    
    blob_path = sys.argv[1]
    download_batch_info(blob_path)