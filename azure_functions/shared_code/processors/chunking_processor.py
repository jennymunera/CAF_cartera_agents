import re
import os
import tiktoken
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
from shared_code.utils.jsonl_handler import JSONLHandler
from shared_code.schemas.validation_schemas import validate_corpus_chunk
from shared_code.utils.app_insights_logger import get_logger
from shared_code.utils.blob_storage_client import BlobStorageClient

# Configure logging with Azure Application Insights
logger = get_logger('chunking_processor')


class ChunkingProcessor:
    """Procesador de chunking para dividir documentos grandes en fragmentos manejables."""
    
    def __init__(self, max_tokens: int = 100000, overlap_tokens: int = 512, model_name: str = "gpt-4", generate_jsonl: bool = True):
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
        self.blob_client = BlobStorageClient()
        # Control de guardado de metadatos de chunking (desactivado por defecto)
        self.save_chunk_metadata = str(os.getenv("SAVE_CHUNKING_METADATA", "false")).lower() in ("1", "true", "yes", "on")
        
        # Inicializar el tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback para modelos no reconocidos
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def is_document_already_chunked(self, document_name: str, project_name: str) -> bool:
        """
        Verifica si un documento ya fue chunkeado buscando archivos chunk en la carpeta processed/chunks.
        
        Args:
            document_name: Nombre del documento (con o sin extensión)
            project_name: Nombre del proyecto
            
        Returns:
            True si el documento ya fue chunkeado, False en caso contrario
        """
        try:
            # Obtener el nombre base del documento sin extensión
            doc_stem = Path(document_name).stem
            
            # Los chunks se guardan con formato {NOMBRE_COMPLETO_DOCUMENTO}_chunk_000.json
            # Buscar el primer chunk del documento
            chunk_filename = f"{doc_stem}_chunk_000.json"
            
            if self.blob_client.document_exists_in_processed(project_name, "chunks", chunk_filename):
                logger.info(f"Document already chunked: {document_name} (checked via {chunk_filename})")
                return True
            
            logger.info(f"Document not chunked yet: {document_name} (checked {chunk_filename})")
            return False
            
        except Exception as e:
            logger.warning(f"Error checking if document {document_name} was chunked: {str(e)}")
            return False  # Si no podemos verificar, asumimos que necesita procesamiento
    
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
        # Patrón mejorado para español: maneja ¿...?, comillas, números y minúsculas tras punto
        sentence_pattern = r'(?<=[.\?\!…])\s+(?=["\'""«»¿¡]*[A-ZÁÉÍÓÚÑ0-9])'
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
                
                # Verificar si el overlap + sección excede el límite
                allowed_overlap_tokens = max(0, self.max_tokens - section_tokens)
                if allowed_overlap_tokens < self.overlap_tokens:
                    # Recortar el solapamiento para que quepa
                    prev_tokens = self.tokenizer.encode(current_chunk)
                    overlap_slice = prev_tokens[-allowed_overlap_tokens:] if allowed_overlap_tokens > 0 else []
                    overlap_content = self.tokenizer.decode(overlap_slice) if overlap_slice else ""
                
                candidate = (overlap_content + "\n\n" + section) if overlap_content else section
                candidate_tokens = self.count_tokens(candidate)
                
                if candidate_tokens > self.max_tokens:
                    # Si aún excede, subdividir la sección
                    sub_chunks = self._split_large_section(section, chunk_index)
                    chunks.extend(sub_chunks)
                    chunk_index += len(sub_chunks)
                    current_chunk, current_tokens = "", 0
                else:
                    current_chunk = candidate
                    current_tokens = candidate_tokens
                
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
        logger.info(f"Starting chunking for project: {project_name}")
        
        # Contar tokens totales
        total_tokens = self.count_tokens(content)
        logger.info(f"Total tokens in document: {total_tokens:,}")
        
        # Si el documento está dentro del límite, no hacer chunking
        if total_tokens <= self.max_tokens:
            logger.info("Document is within token limit. No chunking required.")
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
        
        logger.info(f"Document exceeds limit of {self.max_tokens:,} tokens. Starting chunking...")
        
        # Dividir por secciones primero
        sections = self.split_by_sections(content)
        logger.info(f"Document divided into {len(sections)} sections")
        
        # Crear chunks con solapamiento
        chunks = self.create_chunks_with_overlap(sections)
        
        logger.info(f"Created {len(chunks)} chunks:")
        for chunk in chunks:
            logger.info(f"  Chunk {chunk['index']}: {chunk['tokens']:,} tokens - {chunk['sections_range']}")
        
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
                    logger.info(f"Chunk JSONL generated: {chunk_jsonl_path}")
                else:
                    logger.error(f"Error generating chunk JSONL: {chunk_jsonl_path}")
        
        # También generar corpus JSONL completo para compatibilidad con documentos sin chunking
        if self.generate_jsonl and len(chunks) > 1:
            logger.info(f"\nGenerating complete corpus JSONL for compatibility...")
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
                logger.info(f"Complete corpus JSONL generated: {corpus_jsonl_path}")
            logger.info(f"Total JSONL records: {len(all_jsonl_records)}")
        
        # Guardar metadatos del chunking en la carpeta docs (opcional)
        if self.save_chunk_metadata:
            metadata_file = docs_path / f"{project_name}_chunking_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(chunking_result, f, indent=2, ensure_ascii=False)
            saved_files.append(str(metadata_file))
        
        logger.info(f"\nChunks saved:")
        for file in saved_files:
            logger.info(f"  {file}")
        
        return saved_files

    def save_chunks_to_blob(self, chunking_result: Dict[str, Any], project_name: str) -> List[str]:
        """Guarda los chunks en blob storage como archivos JSON individuales, similar a la implementación local."""
        try:
            blob_client = BlobStorageClient()
            chunks = chunking_result['chunks']
            saved_files = []
            
            for chunk in chunks:
                # Crear datos del chunk en formato JSON (similar a la implementación local)
                chunk_data = {
                    'document_name': f"{project_name}_concatenated",
                    'chunk_index': chunk['index'],
                    'content': chunk['content'],
                    'tokens': chunk['tokens'],
                    'sections_range': chunk['sections_range'],
                    'metadata': {
                        'created_at': datetime.now().isoformat(),
                        'project_name': project_name,
                        'total_chunks': len(chunks),
                        'chunking_strategy': chunking_result.get('chunking_strategy', 'unknown')
                    }
                }
                
                # Guardar chunk como archivo JSON en blob storage
                chunk_filename = f"{project_name}_chunk_{chunk['index']:03d}.json"
                chunk_blob_path = f"basedocuments/{project_name}/processed/chunks/{chunk_filename}"
                
                chunk_content = json.dumps(chunk_data, indent=2, ensure_ascii=False)
                blob_client.upload_blob(chunk_blob_path, chunk_content)
                saved_files.append(chunk_blob_path)
                logger.info(f"Chunk JSON saved to blob: {chunk_blob_path}")
            
            # Guardar metadatos del chunking (opcional)
            if self.save_chunk_metadata:
                metadata_filename = f"{project_name}_chunking_metadata.json"
                metadata_path = f"basedocuments/{project_name}/processed/chunks/{metadata_filename}"
                metadata_content = json.dumps(chunking_result, indent=2, ensure_ascii=False)
                blob_client.upload_blob(metadata_path, metadata_content)
                saved_files.append(metadata_path)
            
            logger.info(f"Chunks saved to blob storage:")
            for file in saved_files:
                logger.info(f"  {file}")
            
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving chunks to blob storage: {str(e)}")
            return []
    
    def save_chunks_to_blob_with_doc_name(self, chunking_result: Dict[str, Any], project_name: str, document_name: str) -> List[str]:
        """Guarda los chunks en blob storage con el nombre del documento original incluido."""
        try:
            blob_client = BlobStorageClient()
            chunks = chunking_result['chunks']
            saved_files = []
            
            # Extraer el nombre base del documento (sin extensión)
            doc_stem = Path(document_name).stem
            
            for chunk in chunks:
                # Crear datos del chunk en formato JSON con el nombre del documento original
                chunk_data = {
                    'document_name': document_name,
                    'chunk_index': chunk['index'],
                    'content': chunk['content'],
                    'tokens': chunk['tokens'],
                    'sections_range': chunk['sections_range'],
                    'metadata': {
                        'created_at': datetime.now().isoformat(),
                        'project_name': project_name,
                        'original_document': document_name,
                        'total_chunks': len(chunks),
                        'chunking_strategy': chunking_result.get('chunking_strategy', 'unknown')
                    }
                }
                
                # Crear nombre del chunk con el nombre completo del documento original (sin extensión)
                chunk_filename = f"{doc_stem}_chunk_{chunk['index']:03d}.json"
                chunk_blob_path = f"basedocuments/{project_name}/processed/chunks/{chunk_filename}"
                
                chunk_content = json.dumps(chunk_data, indent=2, ensure_ascii=False)
                blob_client.upload_blob(chunk_blob_path, chunk_content)
                saved_files.append(chunk_blob_path)
                logger.info(f"Chunk JSON saved to blob: {chunk_blob_path}")
            
            # Guardar metadatos del chunking específicos para este documento
            metadata_filename = f"{document_name}_chunking_metadata.json"
            metadata_path = f"basedocuments/{project_name}/processed/chunks/{metadata_filename}"
            
            # Agregar información del documento original a los metadatos
            enhanced_metadata = chunking_result.copy()
            enhanced_metadata['original_document'] = document_name
            enhanced_metadata['document_stem'] = doc_stem
            
            metadata_content = json.dumps(enhanced_metadata, indent=2, ensure_ascii=False)
            if self.save_chunk_metadata:
                blob_client.upload_blob(metadata_path, metadata_content)
            if self.save_chunk_metadata:
                saved_files.append(metadata_path)
            
            logger.info(f"Document {document_name} chunks saved to blob storage:")
            for file in saved_files:
                logger.info(f"  {file}")
            
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving chunks for document {document_name} to blob storage: {str(e)}")
            return []


def chunk_document_content(content: str, project_name: str, max_tokens: int = 100000, generate_jsonl: bool = True) -> Dict[str, Any]:
    """Función de conveniencia para hacer chunking de contenido con generación opcional de JSONL."""
    processor = ChunkingProcessor(max_tokens=max_tokens, generate_jsonl=generate_jsonl)
    return processor.process_document_content(content, project_name)


if __name__ == "__main__":
    # Ejemplo de uso
    logger.info("Chunking Processor")
    logger.info("="*40)
    
    # Cargar un documento de ejemplo
    example_file = "output_docs/CFA009660_concatenated.md"
    if Path(example_file).exists():
        with open(example_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = chunk_document_content(content, "CFA009660", max_tokens=100000)
        
        processor = ChunkingProcessor()
        processor.save_chunks(result)
    else:
        logger.warning(f"Example file not found: {example_file}")
