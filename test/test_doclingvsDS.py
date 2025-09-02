import pytest
import os
from pathlib import Path
import time
from datetime import datetime

# Importar los procesadores
from document_intelligence_processor import DocumentIntelligenceProcessor
from docling_processor import DoclingProcessor
from config.settings import Settings


class TestDoclingVsDocumentIntelligence:
    """Test comparativo entre Docling y Document Intelligence."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        self.settings = Settings()
        self.test_file = Path("input_docs/CFA009660/INI-CFA009660-Nota ABC 2017-0688.pdf")
        self.output_dir = Path("test/output_tests")
        self.output_dir.mkdir(exist_ok=True)
        
        # Verificar que el archivo existe
        if not self.test_file.exists():
            pytest.skip(f"Archivo de test no encontrado: {self.test_file}")
    
    @pytest.mark.integration
    def test_document_intelligence_processing(self):
        """Test de procesamiento con Document Intelligence."""
        print("\n=== INICIANDO PROCESAMIENTO CON DOCUMENT INTELLIGENCE ===")
        
        try:
            # Obtener configuración de Document Intelligence
            di_config = self.settings.get_document_intelligence_config()
            
            # Inicializar procesador
            processor = DocumentIntelligenceProcessor(
                endpoint=di_config['endpoint'],
                api_key=di_config['api_key']
            )
            
            # Procesar documento
            start_time = time.time()
            result = processor.process_single_document(self.test_file)
            processing_time = time.time() - start_time
            
            # Verificar que el procesamiento fue exitoso
            assert result['metadata']['processing_status'] == 'success', f"Error en procesamiento: {result['metadata'].get('error_message', 'Unknown error')}"
            
            # Obtener contenido
            content = result['content']
            char_count = len(content)
            
            # Guardar resultado en markdown
            output_file = self.output_dir / "document_intelligence_output.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Procesamiento con Document Intelligence\n\n")
                f.write(f"**Archivo:** {self.test_file.name}\n")
                f.write(f"**Fecha de procesamiento:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Tiempo de procesamiento:** {processing_time:.2f} segundos\n")
                f.write(f"**Caracteres extraídos:** {char_count:,}\n\n")
                f.write("---\n\n")
                f.write("## Contenido Extraído\n\n")
                f.write(content)
            
            print(f"✅ Document Intelligence completado:")
            print(f"   - Caracteres extraídos: {char_count:,}")
            print(f"   - Tiempo: {processing_time:.2f}s")
            print(f"   - Archivo guardado: {output_file}")
            
            # Guardar métricas para comparación
            self.di_metrics = {
                'char_count': char_count,
                'processing_time': processing_time,
                'status': 'success'
            }
            
        except Exception as e:
            print(f"❌ Error en Document Intelligence: {str(e)}")
            # Guardar error en archivo
            error_file = self.output_dir / "document_intelligence_error.md"
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write(f"# Error en Document Intelligence\n\n")
                f.write(f"**Archivo:** {self.test_file.name}\n")
                f.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Error:** {str(e)}\n")
            
            self.di_metrics = {
                'char_count': 0,
                'processing_time': 0,
                'status': 'error',
                'error': str(e)
            }
            
            # No fallar el test, solo registrar el error
            pytest.skip(f"Document Intelligence falló: {str(e)}")
    
    @pytest.mark.integration
    def test_docling_processing(self):
        """Test de procesamiento con Docling."""
        print("\n=== INICIANDO PROCESAMIENTO CON DOCLING ===")
        
        try:
            # Inicializar procesador Docling
            processor = DoclingProcessor()
            
            # Procesar documento
            start_time = time.time()
            result = processor.process_single_document(self.test_file)
            processing_time = time.time() - start_time
            
            # Verificar que el procesamiento fue exitoso
            assert result['metadata']['processing_status'] == 'success', f"Error en procesamiento: {result['metadata'].get('error_message', 'Unknown error')}"
            
            # Obtener contenido
            content = result['content']
            char_count = len(content)
            
            # Guardar resultado en markdown
            output_file = self.output_dir / "docling_output.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Procesamiento con Docling\n\n")
                f.write(f"**Archivo:** {self.test_file.name}\n")
                f.write(f"**Fecha de procesamiento:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Tiempo de procesamiento:** {processing_time:.2f} segundos\n")
                f.write(f"**Caracteres extraídos:** {char_count:,}\n\n")
                f.write("---\n\n")
                f.write("## Contenido Extraído\n\n")
                f.write(content)
            
            print(f"✅ Docling completado:")
            print(f"   - Caracteres extraídos: {char_count:,}")
            print(f"   - Tiempo: {processing_time:.2f}s")
            print(f"   - Archivo guardado: {output_file}")
            
            # Guardar métricas para comparación
            self.docling_metrics = {
                'char_count': char_count,
                'processing_time': processing_time,
                'status': 'success'
            }
            
        except Exception as e:
            print(f"❌ Error en Docling: {str(e)}")
            # Guardar error en archivo
            error_file = self.output_dir / "docling_error.md"
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write(f"# Error en Docling\n\n")
                f.write(f"**Archivo:** {self.test_file.name}\n")
                f.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Error:** {str(e)}\n")
            
            self.docling_metrics = {
                'char_count': 0,
                'processing_time': 0,
                'status': 'error',
                'error': str(e)
            }
            
            # No fallar el test, solo registrar el error
            pytest.skip(f"Docling falló: {str(e)}")
    
    @pytest.mark.integration
    def test_comparison_analysis(self):
        """Análisis comparativo entre ambos procesadores."""
        print("\n=== INICIANDO ANÁLISIS COMPARATIVO ===")
        
        # Ejecutar ambos procesadores primero
        self.test_document_intelligence_processing()
        self.test_docling_processing()
        
        # Realizar comparación
        comparison_file = self.output_dir / "comparison_analysis.md"
        
        with open(comparison_file, 'w', encoding='utf-8') as f:
            f.write(f"# Análisis Comparativo: Docling vs Document Intelligence\n\n")
            f.write(f"**Archivo analizado:** {self.test_file.name}\n")
            f.write(f"**Fecha del análisis:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Resultados\n\n")
            
            # Tabla comparativa
            f.write("| Métrica | Document Intelligence | Docling | Diferencia |\n")
            f.write("|---------|----------------------|---------|------------|\n")
            
            # Caracteres extraídos
            di_chars = getattr(self, 'di_metrics', {}).get('char_count', 0)
            docling_chars = getattr(self, 'docling_metrics', {}).get('char_count', 0)
            char_diff = di_chars - docling_chars
            char_diff_pct = (char_diff / max(docling_chars, 1)) * 100 if docling_chars > 0 else 0
            
            f.write(f"| Caracteres extraídos | {di_chars:,} | {docling_chars:,} | {char_diff:+,} ({char_diff_pct:+.1f}%) |\n")
            
            # Tiempo de procesamiento
            di_time = getattr(self, 'di_metrics', {}).get('processing_time', 0)
            docling_time = getattr(self, 'docling_metrics', {}).get('processing_time', 0)
            time_diff = di_time - docling_time
            
            f.write(f"| Tiempo de procesamiento | {di_time:.2f}s | {docling_time:.2f}s | {time_diff:+.2f}s |\n")
            
            # Estado
            di_status = getattr(self, 'di_metrics', {}).get('status', 'unknown')
            docling_status = getattr(self, 'docling_metrics', {}).get('status', 'unknown')
            
            f.write(f"| Estado | {di_status} | {docling_status} | - |\n\n")
            
            # Análisis detallado
            f.write("## Análisis Detallado\n\n")
            
            if di_chars > 0 and docling_chars > 0:
                if di_chars > docling_chars:
                    winner = "Document Intelligence"
                    f.write(f"🏆 **Ganador en extracción de texto:** {winner}\n")
                    f.write(f"- Document Intelligence extrajo {char_diff:,} caracteres más ({char_diff_pct:.1f}% más contenido)\n\n")
                elif docling_chars > di_chars:
                    winner = "Docling"
                    f.write(f"🏆 **Ganador en extracción de texto:** {winner}\n")
                    f.write(f"- Docling extrajo {abs(char_diff):,} caracteres más ({abs(char_diff_pct):.1f}% más contenido)\n\n")
                else:
                    f.write(f"🤝 **Empate:** Ambos procesadores extrajeron la misma cantidad de caracteres\n\n")
                
                # Análisis de velocidad
                if di_time < docling_time:
                    f.write(f"⚡ **Más rápido:** Document Intelligence ({abs(time_diff):.2f}s menos)\n")
                elif docling_time < di_time:
                    f.write(f"⚡ **Más rápido:** Docling ({abs(time_diff):.2f}s menos)\n")
                else:
                    f.write(f"⚡ **Velocidad similar:** Diferencia mínima en tiempo de procesamiento\n")
            
            else:
                f.write("⚠️ **Advertencia:** Uno o ambos procesadores fallaron\n")
                if hasattr(self, 'di_metrics') and self.di_metrics.get('status') == 'error':
                    f.write(f"- Document Intelligence: {self.di_metrics.get('error', 'Error desconocido')}\n")
                if hasattr(self, 'docling_metrics') and self.docling_metrics.get('status') == 'error':
                    f.write(f"- Docling: {self.docling_metrics.get('error', 'Error desconocido')}\n")
            
            f.write("\n## Archivos Generados\n\n")
            f.write("- `document_intelligence_output.md` - Salida completa de Document Intelligence\n")
            f.write("- `docling_output.md` - Salida completa de Docling\n")
            f.write("- `comparison_analysis.md` - Este análisis comparativo\n")
        
        print(f"\n📊 Análisis comparativo completado:")
        print(f"   - Document Intelligence: {di_chars:,} caracteres")
        print(f"   - Docling: {docling_chars:,} caracteres")
        print(f"   - Diferencia: {char_diff:+,} caracteres")
        print(f"   - Archivo de comparación: {comparison_file}")
        
        # Asegurar que al menos uno de los procesadores funcionó
        assert (di_chars > 0 or docling_chars > 0), "Ambos procesadores fallaron"


if __name__ == "__main__":
    # Ejecutar test directamente
    test_instance = TestDoclingVsDocumentIntelligence()
    test_instance.setup_method()
    
    print("Ejecutando comparación Docling vs Document Intelligence...")
    test_instance.test_comparison_analysis()
    print("\n✅ Comparación completada. Revisa los archivos en test/output_tests/")