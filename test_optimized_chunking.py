#!/usr/bin/env python3
"""
Script de prueba para verificar la optimizacion del proceso de chunkeo.
Este script prueba que el chunkeo se realice automaticamente durante el procesamiento de Docling.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docling_processor import DoclingProcessor

def test_optimized_chunking():
    """Prueba el nuevo flujo optimizado de chunkeo automatico."""
    print("=" * 60)
    print("PRUEBA DE CHUNKEO OPTIMIZADO")
    print("=" * 60)
    
    project_name = "CFA009660"
    
    print(f"\n1. Probando procesamiento CON chunkeo automatico:")
    print("-" * 50)
    
    # Test with auto chunking enabled
    processor_with_chunking = DoclingProcessor(auto_chunk=True, max_tokens=50000)  # Lower limit to force chunking
    result_with_chunking = processor_with_chunking.process_project_documents(project_name)
    
    if result_with_chunking:
        print(f"Procesamiento exitoso")
        print(f"   Documentos procesados: {result_with_chunking['metadata']['successful_documents']}")
        
        if 'chunking_result' in result_with_chunking:
            chunking_info = result_with_chunking['chunking_result']
            print(f"   Chunkeo automatico: {'SI' if chunking_info['requires_chunking'] else 'NO'}")
            if chunking_info['requires_chunking']:
                print(f"   Numero de chunks: {len(chunking_info['chunks'])}")
                print(f"   Archivos de chunks guardados: {len(chunking_info.get('saved_files', []))}")
        else:
            print("   No se encontro informacion de chunkeo")
    else:
        print("Error en el procesamiento")
    
    print(f"\n2. Probando procesamiento SIN chunkeo automatico:")
    print("-" * 50)
    
    # Test with auto chunking disabled
    processor_without_chunking = DoclingProcessor(auto_chunk=False)
    result_without_chunking = processor_without_chunking.process_project_documents(project_name)
    
    if result_without_chunking:
        print(f"Procesamiento exitoso")
        print(f"   Documentos procesados: {result_without_chunking['metadata']['successful_documents']}")
        
        if 'chunking_result' in result_without_chunking:
            print("   Se encontro informacion de chunkeo (no deberia estar presente)")
        else:
            print("   No hay informacion de chunkeo (correcto)")
    else:
        print("Error en el procesamiento")
    
    print(f"\n3. Verificando archivos generados:")
    print("-" * 50)
    
    # Check generated files
    output_dir = Path("output_docs") / project_name / "docs"
    
    if output_dir.exists():
        files = list(output_dir.glob("*"))
        print(f"   Archivos en {output_dir}:")
        for file in files:
            print(f"     - {file.name} ({file.stat().st_size} bytes)")
        
        # Check for chunk files
        chunk_files = list(output_dir.glob("*_chunk_*.md"))
        if chunk_files:
            print(f"   Se encontraron {len(chunk_files)} archivos de chunks")
        else:
            print(f"   No se encontraron archivos de chunks")
    else:
        print(f"   Directorio de salida no existe: {output_dir}")
    
    print(f"\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)

if __name__ == "__main__":
    test_optimized_chunking()