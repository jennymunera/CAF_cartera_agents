#!/usr/bin/env python3
"""
Prueba simple del chunkeo automatico
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docling_processor import DoclingProcessor

def test_simple_chunking():
    """Prueba simple del chunkeo automatico con limite muy bajo."""
    print("=" * 50)
    print("PRUEBA SIMPLE DE CHUNKEO AUTOMATICO")
    print("=" * 50)
    
    project_name = "CFA009660"
    
    # Usar un limite muy bajo para forzar el chunkeo
    print(f"\nCreando DoclingProcessor con auto_chunk=True y max_tokens=10000...")
    processor = DoclingProcessor(auto_chunk=True, max_tokens=10000)
    
    print(f"Procesando proyecto: {project_name}")
    result = processor.process_project_documents(project_name)
    
    if result:
        print(f"\nResultado del procesamiento:")
        print(f"  - Documentos procesados: {result['metadata']['successful_documents']}")
        
        if 'chunking_result' in result:
            chunking_info = result['chunking_result']
            print(f"  - Chunkeo requerido: {chunking_info['requires_chunking']}")
            if chunking_info['requires_chunking']:
                print(f"  - Numero de chunks: {len(chunking_info['chunks'])}")
                print(f"  - Archivos guardados: {len(chunking_info.get('saved_files', []))}")
                print(f"  - Archivos:")
                for file in chunking_info.get('saved_files', []):
                    print(f"    * {file}")
            else:
                print(f"  - No se requiere chunkeo (documento pequeno)")
        else:
            print(f"  - ERROR: No se encontro informacion de chunkeo")
    else:
        print(f"ERROR: Fallo el procesamiento")
    
    print(f"\n" + "=" * 50)
    print("PRUEBA COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    test_simple_chunking()