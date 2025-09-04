#!/usr/bin/env python3
"""
Prueba directa del chunkeo usando archivo concatenado existente
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.document_processor import DocumentProcessor

def test_direct_chunking():
    """Prueba directa del chunkeo usando contenido existente."""
    print("=" * 50)
    print("PRUEBA DIRECTA DE CHUNKEO")
    print("=" * 50)
    
    project_name = "CFA009660"
    
    # Leer el archivo concatenado existente
    concatenated_file = Path("output_docs") / project_name / "docs" / f"{project_name}_concatenated.md"
    
    if not concatenated_file.exists():
        print(f"ERROR: No se encontro el archivo concatenado: {concatenated_file}")
        return
    
    print(f"Leyendo archivo concatenado: {concatenated_file}")
    with open(concatenated_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Contenido leido: {len(content)} caracteres")
    
    # Crear procesador de documentos
    print(f"\nCreando DocumentProcessor...")
    from rag.config import RAGConfig
    config = RAGConfig()
    document_processor = DocumentProcessor(config)
    
    # Procesar contenido
    print(f"Procesando contenido para chunkeo...")
    chunking_result = document_processor.process_document_content(content, project_name)
    
    print(f"\nResultado del chunkeo:")
    print(f"  - Requiere chunkeo: {chunking_result['requires_chunking']}")
    print(f"  - Tokens totales: {chunking_result['total_tokens']}")
    print(f"  - Limite configurado: {config.max_tokens} tokens")
    
    if chunking_result['requires_chunking']:
        print(f"  - Numero de chunks: {len(chunking_result['chunks'])}")
        print(f"  - Estrategia: {chunking_result['chunking_strategy']}")
        
        # Guardar chunks
        print(f"\nGuardando chunks...")
        saved_files = document_processor.save_chunks(chunking_result, "output_docs")
        
        print(f"Archivos guardados:")
        for file in saved_files:
            print(f"  * {file}")
            
        # Verificar que los archivos existen
        print(f"\nVerificando archivos:")
        for file in saved_files:
            if Path(file).exists():
                size = Path(file).stat().st_size
                print(f"  ✓ {file} ({size} bytes)")
            else:
                print(f"  ✗ {file} (NO EXISTE)")
    else:
        print(f"  - No se requiere chunkeo (documento pequeno)")
    
    print(f"\n" + "=" * 50)
    print("PRUEBA COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    test_direct_chunking()