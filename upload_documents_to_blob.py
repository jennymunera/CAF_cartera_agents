#!/usr/bin/env python3
"""
Script para subir documentos desde input_docs al Azure Blob Storage
siguiendo la estructura definida: basedocuments/{project}/raw/
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Agregar el directorio utils al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from blob_storage_client import BlobStorageClient

def upload_documents_to_blob():
    """Sube documentos desde input_docs al Blob Storage"""
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Verificar variables de entorno
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    container_name = os.getenv('AZURE_STORAGE_CONTAINER_NAME')
    
    if not connection_string or not container_name:
        print("Error: Variables de entorno AZURE_STORAGE_CONNECTION_STRING y AZURE_STORAGE_CONTAINER_NAME requeridas")
        return False
    
    # Inicializar cliente de Blob Storage
    try:
        blob_client = BlobStorageClient(connection_string, container_name)
        print(f"✅ Conectado al contenedor: {container_name}")
    except Exception as e:
        print(f"❌ Error conectando al Blob Storage: {e}")
        return False
    
    # Directorio de documentos locales
    input_docs_dir = Path("input_docs")
    
    if not input_docs_dir.exists():
        print(f"❌ Directorio {input_docs_dir} no existe")
        return False
    
    # Buscar documentos por proyecto
    uploaded_count = 0
    
    for project_dir in input_docs_dir.iterdir():
        if not project_dir.is_dir():
            continue
            
        project_name = project_dir.name
        print(f"\n📁 Procesando proyecto: {project_name}")
        
        # Buscar documentos en el directorio del proyecto
        for doc_file in project_dir.iterdir():
            if doc_file.is_file() and doc_file.suffix.lower() in ['.pdf', '.docx', '.doc', '.txt']:
                try:
                    # Ruta en el blob: basedocuments/{project}/raw/{filename}
                    blob_path = f"basedocuments/{project_name}/raw/{doc_file.name}"
                    
                    # Subir documento
                    with open(doc_file, 'rb') as file_data:
                        blob_client.upload_raw_document(project_name, doc_file.name, file_data.read())
                    
                    print(f"  ✅ Subido: {doc_file.name} → {blob_path}")
                    uploaded_count += 1
                    
                except Exception as e:
                    print(f"  ❌ Error subiendo {doc_file.name}: {e}")
    
    print(f"\n🎉 Proceso completado. {uploaded_count} documentos subidos al Blob Storage.")
    return uploaded_count > 0

def create_sample_documents():
    """Crea documentos de ejemplo para demostrar la funcionalidad"""
    
    input_docs_dir = Path("input_docs")
    input_docs_dir.mkdir(exist_ok=True)
    
    # Crear proyecto de ejemplo
    project_dir = input_docs_dir / "CAF123"
    project_dir.mkdir(exist_ok=True)
    
    # Crear documentos de ejemplo
    sample_docs = {
        "auditoria_documento.txt": "Este es un documento de auditoría de ejemplo para el proyecto CAF123.\n\nContenido:\n- Revisión de procesos\n- Análisis de riesgos\n- Recomendaciones",
        "desembolso_informe.txt": "Informe de desembolso para el proyecto CAF123.\n\nDetalles:\n- Monto: $100,000\n- Fecha: 2024-01-15\n- Beneficiario: Empresa XYZ",
        "producto_especificacion.txt": "Especificación del producto para CAF123.\n\nCaracterísticas:\n- Tipo: Software\n- Versión: 1.0\n- Funcionalidades principales"
    }
    
    created_count = 0
    for filename, content in sample_docs.items():
        doc_path = project_dir / filename
        if not doc_path.exists():
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Creado documento de ejemplo: {doc_path}")
            created_count += 1
    
    return created_count

if __name__ == "__main__":
    print("🚀 Iniciando subida de documentos al Azure Blob Storage...")
    
    # Crear documentos de ejemplo si no existen
    sample_count = create_sample_documents()
    if sample_count > 0:
        print(f"\n📝 Creados {sample_count} documentos de ejemplo en input_docs/CAF123/")
    
    # Subir documentos al Blob Storage
    success = upload_documents_to_blob()
    
    if success:
        print("\n✅ Subida completada exitosamente!")
    else:
        print("\n❌ Error durante la subida")
        sys.exit(1)