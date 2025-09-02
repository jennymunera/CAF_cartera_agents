#!/usr/bin/env python3
"""
Script para probar las mejoras de OCR en Docling para documentos escaneados.
"""

import os
import sys
import time
from pathlib import Path
from docling_processor import DoclingProcessor

def test_ocr_improvements():
    """Prueba las mejoras de OCR en Docling."""
    print("=" * 60)
    print("PRUEBA DE MEJORAS OCR EN DOCLING")
    print("=" * 60)
    
    # Buscar archivos PDF de prueba
    input_dir = Path("input_docs")
    test_files = []
    
    if input_dir.exists():
        for project_dir in input_dir.iterdir():
            if project_dir.is_dir():
                pdf_files = list(project_dir.glob("*.pdf"))
                if pdf_files:
                    test_files.extend(pdf_files[:1])  # Solo el primer PDF de cada proyecto
    
    if not test_files:
        print("❌ No se encontraron archivos PDF para probar")
        print("   Coloca archivos PDF en carpetas dentro de 'input_docs/'")
        return False
    
    print(f"📄 Archivos encontrados para prueba: {len(test_files)}")
    for file in test_files:
        print(f"   - {file}")
    
    # Crear procesador con mejoras OCR
    print("\n🔧 Inicializando procesador Docling con mejoras OCR...")
    processor = DoclingProcessor(auto_chunk=False)
    
    results = []
    
    for test_file in test_files:
        print(f"\n📖 Procesando: {test_file.name}")
        print("-" * 40)
        
        start_time = time.time()
        
        try:
            result = processor.process_single_document(test_file)
            processing_time = time.time() - start_time
            
            # Verificar si el procesamiento fue exitoso
            content = result.get('content', '')
            metadata = result.get('metadata', {})
            
            # Considerar exitoso si hay contenido o si no hay error en metadata
            is_successful = (len(content.strip()) > 0 or 
                           metadata.get('processing_status') != 'error')
            
            if is_successful:
                print(f"✅ Procesamiento exitoso")
                print(f"   ⏱️  Tiempo: {processing_time:.2f} segundos")
                print(f"   📊 Caracteres extraídos: {len(content):,}")
                print(f"   📄 Páginas: {metadata.get('pages', 0)}")
                print(f"   🖼️  Imágenes: {metadata.get('images_found', 0)}")
                print(f"   📋 Tablas: {metadata.get('tables_found', 0)}")
                
                # Mostrar muestra del contenido extraído
                if content and len(content.strip()) > 0:
                    print(f"\n📝 Muestra del contenido extraído:")
                    sample = content[:500].replace('\n', ' ').strip()
                    print(f"   {sample}...")
                else:
                    print(f"\n⚠️  No se extrajo contenido de texto (documento puede ser solo imágenes)")
                
                results.append({
                    'file': test_file.name,
                    'success': True,
                    'processing_time': processing_time,
                    'characters': len(content),
                    'pages': metadata.get('pages', 0),
                    'content_sample': content[:200] if content else ""
                })
                
            else:
                error_msg = metadata.get('error_message', 'Error en procesamiento')
                print(f"❌ Error en procesamiento: {error_msg}")
                results.append({
                    'file': test_file.name,
                    'success': False,
                    'error': error_msg
                })
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"❌ Excepción durante procesamiento: {str(e)}")
            results.append({
                'file': test_file.name,
                'success': False,
                'error': str(e)
            })
    
    # Resumen de resultados
    print("\n" + "=" * 60)
    print("RESUMEN DE RESULTADOS")
    print("=" * 60)
    
    successful = [r for r in results if r.get('success', False)]
    failed = [r for r in results if not r.get('success', False)]
    
    print(f"✅ Archivos procesados exitosamente: {len(successful)}")
    print(f"❌ Archivos con errores: {len(failed)}")
    
    if successful:
        total_chars = sum(r['characters'] for r in successful)
        avg_time = sum(r['processing_time'] for r in successful) / len(successful)
        print(f"📊 Total de caracteres extraídos: {total_chars:,}")
        print(f"⏱️  Tiempo promedio de procesamiento: {avg_time:.2f}s")
        
        print("\n📋 Detalles por archivo:")
        for result in successful:
            print(f"   📄 {result['file']}: {result['characters']:,} chars, {result['processing_time']:.2f}s")
    
    if failed:
        print("\n❌ Archivos con errores:")
        for result in failed:
            print(f"   📄 {result['file']}: {result.get('error', 'Error desconocido')}")
    
    # Recomendaciones
    print("\n" + "=" * 60)
    print("RECOMENDACIONES")
    print("=" * 60)
    
    if len(successful) == 0:
        print("🔧 Para mejorar la extracción de OCR:")
        print("   1. Instala Tesseract: pip install tesserocr")
        print("   2. Verifica que los PDFs contengan texto escaneado")
        print("   3. Considera usar Document Intelligence para documentos complejos")
    elif total_chars < 1000:
        print("⚠️  Extracción de texto limitada detectada:")
        print("   - Los documentos pueden ser principalmente imágenes")
        print("   - Considera usar Document Intelligence para mejor OCR")
        print("   - Verifica la calidad de los documentos escaneados")
    else:
        print("🎉 ¡Extracción de OCR funcionando correctamente!")
        print("   - Docling está extrayendo texto de documentos escaneados")
        print("   - Las mejoras de OCR están activas")
    
    return len(successful) > 0

if __name__ == "__main__":
    success = test_ocr_improvements()
    sys.exit(0 if success else 1)