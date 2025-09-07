import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('../.env')

# Agregar el directorio actual al path
sys.path.append('.')

from OpenAiProcess.utils.blob_storage_client import BlobStorageClient

def check_documents():
    try:
        # Inicializar cliente
        blob_client = BlobStorageClient()
        
        # Listar documentos del proyecto
        project_name = "CFA009660"
        documents = blob_client.list_raw_documents(project_name)
        
        print(f"\n📋 Total de documentos encontrados: {len(documents)}")
        print("\n📄 Lista completa de documentos:")
        for i, doc in enumerate(documents, 1):
            print(f"{i:2d}. {doc}")
        
        # Definir prefijos permitidos
        allowed_prefixes = {
            'Prompt 1 (Auditoria)': ['IXP'],
            'Prompt 2 (Productos)': ['ROP', 'INI', 'DEC', 'IFS'],
            'Prompt 3 (Desembolsos)': ['ROP', 'INI', 'DEC']
        }
        
        print("\n🔍 Análisis por prefijos permitidos:")
        
        for prompt_name, prefixes in allowed_prefixes.items():
            print(f"\n{prompt_name}: {prefixes}")
            matching_docs = []
            for doc in documents:
                doc_prefix = doc.split('-')[0].upper() if '-' in doc else doc[:3].upper()
                if doc_prefix in prefixes:
                    matching_docs.append(doc)
            
            print(f"  ✅ Documentos que coinciden ({len(matching_docs)}):")
            for doc in matching_docs:
                print(f"    - {doc}")
        
        # Documentos que NO coinciden con ningún prefijo
        print("\n❌ Documentos que NO coinciden con ningún prefijo permitido:")
        all_allowed_prefixes = set()
        for prefixes in allowed_prefixes.values():
            all_allowed_prefixes.update(prefixes)
        
        non_matching_docs = []
        for doc in documents:
            doc_prefix = doc.split('-')[0].upper() if '-' in doc else doc[:3].upper()
            if doc_prefix not in all_allowed_prefixes:
                non_matching_docs.append((doc, doc_prefix))
        
        for doc, prefix in non_matching_docs:
            print(f"  - {doc} (prefijo: {prefix})")
        
        print(f"\n📊 Resumen:")
        total_matching = sum(len([doc for doc in documents if (doc.split('-')[0].upper() if '-' in doc else doc[:3].upper()) in prefixes]) for prefixes in allowed_prefixes.values())
        print(f"  - Total documentos: {len(documents)}")
        print(f"  - Con prefijos permitidos: {len(documents) - len(non_matching_docs)}")
        print(f"  - Sin prefijos permitidos: {len(non_matching_docs)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_documents()