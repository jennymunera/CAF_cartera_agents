import re
import tiktoken
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
from utils.jsonl_handler import JSONLHandler
from schemas.validation_schemas import validate_corpus_chunk


class ChunkingProcessor:
    """Procesador de chunking para dividir documentos grandes en fragmentos manejables."""
    
    def __init__(self, max_tokens: int = 150000, overlap_tokens: int = 1000, model_name: str = "gpt-4", generate_jsonl: bool = True):
        """
        Inicializa el procesador de chunking.
        
        Args:
            max_tokens: Máximo número de tokens por chunk
            overlap_tokens: Tokens de solapamiento entre chunks
            model_name: Nombre del modelo para calcular tokens
            generate_jsonl: Si True, genera archivos JSONL además de chunks MD
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.model_name = model_name
        self.generate_jsonl = generate_jsonl
        self.jsonl_handler = JSONLHandler() if generate_jsonl else None
        
        # Inicializar el tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback para modelos no reconocidos
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Cuenta el número de tokens en un texto."""
        return len(self.tokenizer.encode(text))
    
    def split_by_sections(self, content: str) -> List[str]:
        """Divide el contenido por secciones usando separadores comunes."""
        # Patrones para identificar secciones
        section_patterns = [
            r'\n={50,}\n',  # Separadores de igual
            r'\n-{50,}\n',  # Separadores de guión
            r'\n--- DOCUMENT:.*?---\n',  # Separadores de documento
            r'\n\n#{1,3}\s+',  # Títulos markdown
            r'\n\n[A-Z][A-Z\s]{10,}\n',  # Títulos en mayúsculas
        ]
        
        sections = [content]
        
        for pattern in section_patterns:
            new_sections = []
            for section in sections:
                parts = re.split(pattern, section)
                if len(parts) > 1:
                    # Mantener el separador con la sección siguiente
                    for i, part in enumerate(parts):
                        if i > 0:
                            # Buscar el separador original
                            match = re.search(pattern, section)
                            if match:
                                part = match.group() + part
                        new_sections.append(part)
                else:
                    new_sections.append(section)
            sections = new_sections
        
        # Filtrar secciones vacías
        return [s.strip() for s in sections if s.strip()]
    
    def split_by_paragraphs(self, content: str) -> List[str]:
        """Divide el contenido por párrafos."""
        paragraphs = re.split(r'\n\s*\n', content)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def split_by_sentences(self, content: str) -> List[str]:
        """Divide el contenido por oraciones."""
        # Patrón para dividir por oraciones (mejorado para español)
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])'
        sentences = re.split(sentence_pattern, content)
        return [s.strip() for s in sentences if s.strip()]
    
    def create_chunks_with_overlap(self, sections: List[str]) -> List[Dict[str, Any]]:
        """Crea chunks con solapamiento manteniendo el contexto."""
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        for i, section in enumerate(sections):
            section_tokens = self.count_tokens(section)
            
            # Si la sección sola excede el límite, dividirla más
            if section_tokens > self.max_tokens:
                # Guardar chunk actual si tiene contenido
                if current_chunk.strip():
                    chunks.append({
                        'index': chunk_index,
                        'content': current_chunk.strip(),
                        'tokens': current_tokens,
                        'sections_range': f"Hasta sección {i}"
                    })
                    chunk_index += 1
                
                # Dividir la sección grande
                sub_chunks = self._split_large_section(section, chunk_index)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
                
                # Reiniciar chunk actual
                current_chunk = ""
                current_tokens = 0
                
            # Si agregar esta sección excede el límite
            elif current_tokens + section_tokens > self.max_tokens:
                # Guardar chunk actual
                if current_chunk.strip():
                    chunks.append({
                        'index': chunk_index,
                        'content': current_chunk.strip(),
                        'tokens': current_tokens,
                        'sections_range': f"Hasta sección {i-1}"
                    })
                    chunk_index += 1
                
                # Crear solapamiento con el chunk anterior
                overlap_content = self._create_overlap(current_chunk)
                current_chunk = overlap_content + "\n\n" + section
                current_tokens = self.count_tokens(current_chunk)
                
            else:
                # Agregar sección al chunk actual
                if current_chunk:
                    current_chunk += "\n\n" + section
                else:
                    current_chunk = section
                current_tokens += section_tokens
        
        # Agregar el último chunk si tiene contenido
        if current_chunk.strip():
            chunks.append({
                'index': chunk_index,
                'content': current_chunk.strip(),
                'tokens': current_tokens,
                'sections_range': f"Hasta sección {len(sections)-1}"
            })
        
        return chunks
    
    def _split_large_section(self, section: str, start_index: int) -> List[Dict[str, Any]]:
        """Divide una sección muy grande en chunks más pequeños."""
        chunks = []
        
        # Intentar dividir por párrafos primero
        paragraphs = self.split_by_paragraphs(section)
        
        if len(paragraphs) > 1:
            return self.create_chunks_with_overlap(paragraphs)
        
        # Si no hay párrafos, dividir por oraciones
        sentences = self.split_by_sentences(section)
        
        if len(sentences) > 1:
            return self.create_chunks_with_overlap(sentences)
        
        # Último recurso: dividir por caracteres
        chunk_size = self.max_tokens * 3  # Aproximación: 1 token ≈ 3-4 caracteres
        text_chunks = [section[i:i+chunk_size] for i in range(0, len(section), chunk_size)]
        
        for i, chunk_text in enumerate(text_chunks):
            chunks.append({
                'index': start_index + i,
                'content': chunk_text,
                'tokens': self.count_tokens(chunk_text),
                'sections_range': f"Fragmento {i+1} de sección grande"
            })
        
        return chunks
    
    def _create_overlap(self, content: str) -> str:
        """Crea contenido de solapamiento del final del chunk anterior."""
        tokens = self.tokenizer.encode(content)
        
        if len(tokens) <= self.overlap_tokens:
            return content
        
        # Tomar los últimos tokens para el solapamiento
        overlap_tokens = tokens[-self.overlap_tokens:]
        overlap_text = self.tokenizer.decode(overlap_tokens)
        
        return overlap_text
    
    def _create_jsonl_record(self, chunk: Dict[str, Any], project_name: str, chunk_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un registro JSONL a partir de un chunk."""
        return {
            'id_chunk': f"{project_name}_chunk_{chunk['index']:03d}",
            'proyecto': project_name,
            'contenido': chunk['content'],
            'tokens': chunk['tokens'],
            'indice_chunk': chunk['index'],
            'rango_secciones': chunk['sections_range'],
            'estrategia_chunking': chunk_metadata.get('chunking_strategy', 'sections_with_overlap'),
            'max_tokens_configurado': chunk_metadata.get('max_tokens_per_chunk', self.max_tokens),
            'overlap_tokens': chunk_metadata.get('overlap_tokens', self.overlap_tokens),
            'timestamp_procesamiento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'fuente': 'document_intelligence_chunking',
            'version_esquema': '1.0'
        }
    
    def process_document_content(self, content: str, project_name: str) -> Dict[str, Any]:
        """Procesa el contenido de un documento y lo divide en chunks."""
        print(f"\nIniciando chunking para proyecto: {project_name}")
        
        # Contar tokens totales
        total_tokens = self.count_tokens(content)
        print(f"Tokens totales en el documento: {total_tokens:,}")
        
        # Si el documento está dentro del límite, no hacer chunking
        if total_tokens <= self.max_tokens:
            print("El documento está dentro del límite de tokens. No se requiere chunking.")
            return {
                'project_name': project_name,
                'total_tokens': total_tokens,
                'requires_chunking': False,
                'chunks': [{
                    'index': 0,
                    'content': content,
                    'tokens': total_tokens,
                    'sections_range': 'Documento completo'
                }],
                'chunking_strategy': 'none'
            }
        
        print(f"El documento excede el límite de {self.max_tokens:,} tokens. Iniciando chunking...")
        
        # Dividir por secciones primero
        sections = self.split_by_sections(content)
        print(f"Documento dividido en {len(sections)} secciones")
        
        # Crear chunks con solapamiento
        chunks = self.create_chunks_with_overlap(sections)
        
        print(f"Creados {len(chunks)} chunks:")
        for chunk in chunks:
            print(f"  Chunk {chunk['index']}: {chunk['tokens']:,} tokens - {chunk['sections_range']}")
        
        return {
            'project_name': project_name,
            'total_tokens': total_tokens,
            'requires_chunking': True,
            'chunks': chunks,
            'chunking_strategy': 'sections_with_overlap',
            'max_tokens_per_chunk': self.max_tokens,
            'overlap_tokens': self.overlap_tokens
        }
    
    def save_chunks(self, chunking_result: Dict[str, Any], output_dir: str = "output_docs") -> List[str]:
        """Guarda los chunks en archivos separados y genera un archivo JSONL individual por cada chunk."""
        project_name = chunking_result['project_name']
        
        # Crear estructura de carpetas: output_docs/{project_name}/docs/ y agents_output/
        project_path = Path(output_dir) / project_name
        docs_path = project_path / "docs"
        agents_output_path = project_path / "agents_output"
        docs_path.mkdir(parents=True, exist_ok=True)
        agents_output_path.mkdir(parents=True, exist_ok=True)
        
        chunks = chunking_result['chunks']
        saved_files = []
        
        for chunk in chunks:
            # Guardar chunk como archivo MD
            chunk_filename = f"{project_name}_chunk_{chunk['index']:03d}.md"
            chunk_filepath = docs_path / chunk_filename
            
            # Crear contenido del chunk con metadatos
            chunk_content = f"""# Chunk {chunk['index']} - Proyecto {project_name}

**Tokens:** {chunk['tokens']:,}  
**Rango:** {chunk['sections_range']}  
**Estrategia:** {chunking_result.get('chunking_strategy', 'unknown')}  

---

{chunk['content']}
"""
            
            with open(chunk_filepath, 'w', encoding='utf-8') as f:
                f.write(chunk_content)
            
            saved_files.append(str(chunk_filepath))
            
            # Generar archivo JSONL individual para este chunk si está habilitado
            if self.generate_jsonl:
                jsonl_record = self._create_jsonl_record(chunk, project_name, chunking_result)
                
                # Crear archivo JSONL individual para este chunk
                chunk_jsonl_filename = f"corpus_chunk_{chunk['index']:03d}.jsonl"
                chunk_jsonl_path = agents_output_path / chunk_jsonl_filename
                
                # Validar y escribir registro JSONL individual
                success = self.jsonl_handler.write_jsonl(
                    [jsonl_record],  # Solo un registro por archivo
                    str(chunk_jsonl_path), 
                    validate_func=validate_corpus_chunk
                )
                
                if success:
                    saved_files.append(str(chunk_jsonl_path))
                    print(f"Chunk JSONL generado: {chunk_jsonl_path}")
                else:
                    print(f"Error generando chunk JSONL: {chunk_jsonl_path}")
        
        # También generar corpus JSONL completo para compatibilidad con documentos sin chunking
        if self.generate_jsonl and len(chunks) > 1:
            print(f"\nGenerando corpus JSONL completo para compatibilidad...")
            all_jsonl_records = []
            for chunk in chunks:
                jsonl_record = self._create_jsonl_record(chunk, project_name, chunking_result)
                all_jsonl_records.append(jsonl_record)
            
            corpus_jsonl_path = agents_output_path / f"corpus_document_intelligence.jsonl"
            success = self.jsonl_handler.write_jsonl(
                all_jsonl_records, 
                str(corpus_jsonl_path), 
                validate_func=validate_corpus_chunk
            )
            
            if success:
                saved_files.append(str(corpus_jsonl_path))
                print(f"Corpus JSONL completo generado: {corpus_jsonl_path}")
                print(f"Total registros JSONL: {len(all_jsonl_records)}")
        
        # Guardar metadatos del chunking en la carpeta docs
        metadata_file = docs_path / f"{project_name}_chunking_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(chunking_result, f, indent=2, ensure_ascii=False)
        
        saved_files.append(str(metadata_file))
        
        print(f"\nChunks guardados:")
        for file in saved_files:
            print(f"  {file}")
        
        return saved_files


def chunk_document_content(content: str, project_name: str, max_tokens: int = 150000, generate_jsonl: bool = True) -> Dict[str, Any]:
    """Función de conveniencia para hacer chunking de contenido con generación opcional de JSONL."""
    processor = ChunkingProcessor(max_tokens=max_tokens, generate_jsonl=generate_jsonl)
    return processor.process_document_content(content, project_name)


if __name__ == "__main__":
    # Ejemplo de uso
    print("Chunking Processor")
    print("="*40)
    
    # Cargar un documento de ejemplo
    example_file = "output_docs/CFA009660_concatenated.md"
    if Path(example_file).exists():
        with open(example_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = chunk_document_content(content, "CFA009660", max_tokens=200000)
        
        processor = ChunkingProcessor()
        processor.save_chunks(result)
    else:
        print(f"Archivo de ejemplo no encontrado: {example_file}")