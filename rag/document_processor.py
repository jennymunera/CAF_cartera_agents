"""Document Processing Module for RAG System.

Integrates Azure Document Intelligence with advanced semantic chunking.
Handles document extraction, preprocessing, and intelligent segmentation.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

from .config import RAGConfig, AzureDocumentIntelligenceConfig, ChunkingConfig


@dataclass
class DocumentChunk:
    """Represents a semantic chunk of a document."""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    document_id: str
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    section_title: Optional[str] = None
    chunk_type: str = "text"  # text, table, key_value, header
    language: Optional[str] = None
    token_count: Optional[int] = None
    
    def __post_init__(self):
        """Generate chunk ID if not provided."""
        if not self.chunk_id:
            import time
            import uuid
            content_hash = hashlib.md5(self.content.encode()).hexdigest()[:8]
            unique_suffix = str(uuid.uuid4())[:8]
            self.chunk_id = f"{self.document_id}_{content_hash}_{unique_suffix}"


@dataclass
class ProcessedDocument:
    """Represents a fully processed document."""
    document_id: str
    file_path: str
    chunks: List[DocumentChunk]
    metadata: Dict[str, Any]
    processing_stats: Dict[str, Any]
    

class SemanticChunker:
    """Advanced semantic chunking with respect for document structure."""
    
    def __init__(self, config: ChunkingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Sentence boundary patterns (Spanish and English)
        self.sentence_patterns = [
            r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])',  # Spanish sentence boundaries
            r'(?<=[.!?])\s+(?=[A-Z])',        # English sentence boundaries
            r'(?<=\.)\s+(?=\d+\.)',           # Numbered lists
        ]
        
        # Section boundary patterns
        self.section_patterns = [
            r'^\d+\.\s+[A-ZÁÉÍÓÚÑ]',         # Numbered sections (Spanish)
            r'^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+:',  # Title sections
            r'^#{1,6}\s+',                    # Markdown headers
            r'^[IVX]+\.\s+',                 # Roman numerals
        ]
        
        # Paragraph boundary patterns
        self.paragraph_patterns = [
            r'\n\s*\n',  # Double newlines
            r'\n\s*[-•*]\s+',  # List items
        ]
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimation: 1 token ≈ 4 characters for Spanish/English
        return len(text) // 4
    
    def detect_language(self, text: str) -> str:
        """Simple language detection based on common words."""
        if not self.config.detect_language:
            return self.config.default_language
        
        spanish_indicators = ['el', 'la', 'de', 'que', 'y', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del']
        english_indicators = ['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at']
        
        text_lower = text.lower()
        spanish_count = sum(1 for word in spanish_indicators if f' {word} ' in text_lower)
        english_count = sum(1 for word in english_indicators if f' {word} ' in text_lower)
        
        return 'es' if spanish_count > english_count else 'en'
    
    def find_boundaries(self, text: str, patterns: List[str]) -> List[int]:
        """Find text boundaries using regex patterns."""
        boundaries = set([0])  # Always include start
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                boundaries.add(match.start())
        
        boundaries.add(len(text))  # Always include end
        return sorted(list(boundaries))
    
    def split_by_boundaries(self, text: str, boundaries: List[int]) -> List[str]:
        """Split text by boundary positions."""
        segments = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)
        return segments
    
    def merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """Merge chunks that are too small."""
        if not chunks:
            return chunks
        
        merged_chunks = []
        current_chunk = chunks[0]
        
        for i in range(1, len(chunks)):
            current_tokens = self.estimate_tokens(current_chunk)
            next_chunk = chunks[i]
            next_tokens = self.estimate_tokens(next_chunk)
            
            # If current chunk is too small and merging won't exceed max_tokens
            if (current_tokens < self.config.min_tokens and 
                current_tokens + next_tokens <= self.config.max_tokens):
                current_chunk += "\n\n" + next_chunk
            else:
                merged_chunks.append(current_chunk)
                current_chunk = next_chunk
        
        merged_chunks.append(current_chunk)
        return merged_chunks
    
    def split_large_chunks(self, chunks: List[str]) -> List[str]:
        """Split chunks that are too large."""
        split_chunks = []
        
        for chunk in chunks:
            tokens = self.estimate_tokens(chunk)
            
            if tokens <= self.config.max_tokens:
                split_chunks.append(chunk)
                continue
            
            # Split by sentences if chunk is too large
            sentence_boundaries = self.find_boundaries(chunk, self.sentence_patterns)
            sentences = self.split_by_boundaries(chunk, sentence_boundaries)
            
            current_chunk = ""
            for sentence in sentences:
                test_chunk = current_chunk + ("\n" if current_chunk else "") + sentence
                test_tokens = self.estimate_tokens(test_chunk)
                
                if test_tokens <= self.config.max_tokens:
                    current_chunk = test_chunk
                else:
                    if current_chunk:
                        split_chunks.append(current_chunk)
                    current_chunk = sentence
            
            if current_chunk:
                split_chunks.append(current_chunk)
        
        return split_chunks
    
    def add_overlap(self, chunks: List[str]) -> List[str]:
        """Add overlap between consecutive chunks."""
        if len(chunks) <= 1 or self.config.overlap_tokens <= 0:
            return chunks
        
        overlapped_chunks = [chunks[0]]  # First chunk unchanged
        
        for i in range(1, len(chunks)):
            current_chunk = chunks[i]
            previous_chunk = chunks[i - 1]
            
            # Extract overlap from previous chunk (last N tokens)
            prev_words = previous_chunk.split()
            overlap_words = prev_words[-self.config.overlap_tokens//4:]  # Rough token estimation
            overlap_text = " ".join(overlap_words)
            
            # Add overlap to current chunk
            overlapped_chunk = overlap_text + "\n\n" + current_chunk
            overlapped_chunks.append(overlapped_chunk)
        
        return overlapped_chunks
    
    def chunk_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[DocumentChunk]:
        """Perform semantic chunking on text."""
        if not text.strip():
            return []
        
        metadata = metadata or {}
        language = self.detect_language(text)
        
        # Step 1: Split by sections if enabled
        if self.config.respect_sections:
            section_boundaries = self.find_boundaries(text, self.section_patterns)
            sections = self.split_by_boundaries(text, section_boundaries)
        else:
            sections = [text]
        
        all_chunks = []
        
        for section_idx, section in enumerate(sections):
            # Step 2: Split by paragraphs if enabled
            if self.config.respect_paragraphs:
                paragraph_boundaries = self.find_boundaries(section, self.paragraph_patterns)
                paragraphs = self.split_by_boundaries(section, paragraph_boundaries)
            else:
                paragraphs = [section]
            
            # Step 3: Process paragraphs into target-sized chunks
            section_chunks = []
            current_chunk = ""
            
            for paragraph in paragraphs:
                test_chunk = current_chunk + ("\n\n" if current_chunk else "") + paragraph
                test_tokens = self.estimate_tokens(test_chunk)
                
                if test_tokens <= self.config.target_tokens:
                    current_chunk = test_chunk
                else:
                    if current_chunk:
                        section_chunks.append(current_chunk)
                    current_chunk = paragraph
            
            if current_chunk:
                section_chunks.append(current_chunk)
            
            # Step 4: Merge small chunks and split large ones
            section_chunks = self.merge_small_chunks(section_chunks)
            section_chunks = self.split_large_chunks(section_chunks)
            
            # Step 5: Add overlap
            section_chunks = self.add_overlap(section_chunks)
            
            # Convert to DocumentChunk objects
            for chunk_idx, chunk_text in enumerate(section_chunks):
                chunk_metadata = {
                    **metadata,
                    "section_index": section_idx,
                    "chunk_index": chunk_idx,
                    "language": language,
                    "token_count": self.estimate_tokens(chunk_text),
                }
                
                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata=chunk_metadata,
                    chunk_id="",  # Will be auto-generated
                    document_id=document_id,
                    language=language,
                    token_count=self.estimate_tokens(chunk_text),
                    chunk_type="text"
                )
                all_chunks.append(chunk)
        
        return all_chunks


class AzureDocumentProcessor:
    """Azure Document Intelligence processor with advanced extraction."""
    
    def __init__(self, config: AzureDocumentIntelligenceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize Azure client
        self.client = DocumentIntelligenceClient(
            endpoint=config.endpoint,
            credential=AzureKeyCredential(config.api_key)
        )
    
    def extract_document_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from document using Azure Document Intelligence."""
        try:
            with open(file_path, "rb") as f:
                document_bytes = f.read()
            
            # Analyze document
            poller = self.client.begin_analyze_document(
                model_id=self.config.model_id,
                body=AnalyzeDocumentRequest(bytes_source=document_bytes),
            )
            
            result = poller.result()
            
            # Extract different content types
            extracted_content = {
                "text": self._extract_text(result),
                "tables": self._extract_tables(result) if self.config.extract_tables else [],
                "key_value_pairs": self._extract_key_value_pairs(result) if self.config.extract_key_value_pairs else [],
                "paragraphs": self._extract_paragraphs(result) if self.config.extract_paragraphs else [],
                "sections": self._extract_sections(result) if self.config.extract_sections else [],
                "metadata": self._extract_metadata(result, file_path),
            }
            
            return extracted_content
            
        except Exception as e:
            self.logger.error(f"Error processing document {file_path}: {str(e)}")
            raise
    
    def _extract_text(self, result) -> str:
        """Extract main text content."""
        if hasattr(result, 'content') and result.content:
            return result.content
        return ""
    
    def _extract_tables(self, result) -> List[Dict[str, Any]]:
        """Extract table data."""
        tables = []
        if hasattr(result, 'tables') and result.tables:
            for table_idx, table in enumerate(result.tables):
                table_data = {
                    "table_id": f"table_{table_idx}",
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": [],
                }
                
                if hasattr(table, 'cells') and table.cells:
                    for cell in table.cells:
                        cell_data = {
                            "content": cell.content if hasattr(cell, 'content') else "",
                            "row_index": cell.row_index if hasattr(cell, 'row_index') else 0,
                            "column_index": cell.column_index if hasattr(cell, 'column_index') else 0,
                            "row_span": getattr(cell, 'row_span', 1),
                            "column_span": getattr(cell, 'column_span', 1),
                        }
                        table_data["cells"].append(cell_data)
                
                tables.append(table_data)
        
        return tables
    
    def _extract_key_value_pairs(self, result) -> List[Dict[str, str]]:
        """Extract key-value pairs."""
        pairs = []
        if hasattr(result, 'key_value_pairs') and result.key_value_pairs:
            for pair in result.key_value_pairs:
                # Safely extract key content
                key_content = ""
                if hasattr(pair, 'key') and pair.key and hasattr(pair.key, 'content'):
                    key_content = pair.key.content or ""
                
                # Safely extract value content
                value_content = ""
                if hasattr(pair, 'value') and pair.value and hasattr(pair.value, 'content'):
                    value_content = pair.value.content or ""
                
                pair_data = {
                    "key": key_content,
                    "value": value_content,
                }
                pairs.append(pair_data)
        
        return pairs
    
    def _extract_paragraphs(self, result) -> List[Dict[str, Any]]:
        """Extract paragraph information."""
        paragraphs = []
        if hasattr(result, 'paragraphs') and result.paragraphs:
            for para_idx, paragraph in enumerate(result.paragraphs):
                para_data = {
                    "paragraph_id": f"para_{para_idx}",
                    "content": paragraph.content if hasattr(paragraph, 'content') else "",
                    "role": getattr(paragraph, 'role', None),
                }
                paragraphs.append(para_data)
        
        return paragraphs
    
    def _extract_sections(self, result) -> List[Dict[str, Any]]:
        """Extract section information."""
        sections = []
        if hasattr(result, 'sections') and result.sections:
            for section_idx, section in enumerate(result.sections):
                section_data = {
                    "section_id": f"section_{section_idx}",
                    "content": section.content if hasattr(section, 'content') else "",
                }
                sections.append(section_data)
        
        return sections
    
    def _extract_metadata(self, result, file_path: str) -> Dict[str, Any]:
        """Extract document metadata."""
        metadata = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_extension": Path(file_path).suffix,
        }
        
        # Add language detection if available
        if self.config.detect_language and hasattr(result, 'languages') and result.languages:
            metadata["detected_languages"] = [
                {"language": lang.locale, "confidence": getattr(lang, 'confidence', 0.0)}
                for lang in result.languages
            ]
        
        # Add page count if available
        if hasattr(result, 'pages') and result.pages:
            metadata["page_count"] = len(result.pages)
        
        return metadata


class DocumentProcessor:
    """Main document processor combining Azure DI and semantic chunking."""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.azure_processor = AzureDocumentProcessor(config.azure_di)
        self.chunker = SemanticChunker(config.chunking)
        
        # Processing cache
        self.processing_cache = {}
    
    def get_document_hash(self, file_path: str) -> str:
        """Generate hash for document to detect changes."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def process_document(self, file_path: str, force_reprocess: bool = False) -> ProcessedDocument:
        """Process a single document through the full pipeline."""
        file_path = str(Path(file_path).resolve())
        document_id = Path(file_path).stem
        
        # Check cache
        doc_hash = self.get_document_hash(file_path)
        cache_key = f"{file_path}_{doc_hash}"
        
        if not force_reprocess and cache_key in self.processing_cache:
            self.logger.info(f"Using cached result for {file_path}")
            return self.processing_cache[cache_key]
        
        self.logger.info(f"Processing document: {file_path}")
        
        try:
            # Step 1: Extract content with Azure Document Intelligence
            extracted_content = self.azure_processor.extract_document_content(file_path)
            
            # Step 2: Chunk the main text content
            text_chunks = self.chunker.chunk_text(
                text=extracted_content["text"],
                document_id=document_id,
                metadata=extracted_content["metadata"]
            )
            
            # Step 3: Process tables as separate chunks
            table_chunks = self._process_tables(
                tables=extracted_content["tables"],
                document_id=document_id,
                metadata=extracted_content["metadata"]
            )
            
            # Step 4: Process key-value pairs as separate chunks
            kv_chunks = self._process_key_value_pairs(
                pairs=extracted_content["key_value_pairs"],
                document_id=document_id,
                metadata=extracted_content["metadata"]
            )
            
            # Combine all chunks
            all_chunks = text_chunks + table_chunks + kv_chunks
            
            # Processing statistics
            processing_stats = {
                "total_chunks": len(all_chunks),
                "text_chunks": len(text_chunks),
                "table_chunks": len(table_chunks),
                "kv_chunks": len(kv_chunks),
                "total_tokens": sum(chunk.token_count or 0 for chunk in all_chunks),
                "document_hash": doc_hash,
            }
            
            # Create processed document
            processed_doc = ProcessedDocument(
                document_id=document_id,
                file_path=file_path,
                chunks=all_chunks,
                metadata=extracted_content["metadata"],
                processing_stats=processing_stats
            )
            
            # Cache result
            self.processing_cache[cache_key] = processed_doc
            
            self.logger.info(
                f"Document processed successfully: {len(all_chunks)} chunks, "
                f"{processing_stats['total_tokens']} tokens"
            )
            
            return processed_doc
            
        except Exception as e:
            self.logger.error(f"Error processing document {file_path}: {str(e)}")
            raise
    
    def _process_tables(self, tables: List[Dict[str, Any]], document_id: str, metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """Convert tables to document chunks."""
        table_chunks = []
        
        if not tables:
            return table_chunks
            
        for table in tables:
            if not table or not isinstance(table, dict):
                continue
                
            # Convert table to text representation
            table_text = self._table_to_text(table)
            
            if table_text.strip():
                chunk_metadata = {
                    **metadata,
                    "chunk_type": "table",
                    "table_id": table.get("table_id", "unknown"),
                    "row_count": table.get("row_count", 0),
                    "column_count": table.get("column_count", 0),
                }
                
                chunk = DocumentChunk(
                    content=table_text,
                    metadata=chunk_metadata,
                    chunk_id="",
                    document_id=document_id,
                    chunk_type="table",
                    token_count=self.chunker.estimate_tokens(table_text)
                )
                table_chunks.append(chunk)
        
        return table_chunks
    
    def _process_key_value_pairs(self, pairs: List[Dict[str, str]], document_id: str, metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """Convert key-value pairs to document chunks."""
        if not pairs:
            return []
        
        # Combine all key-value pairs into a single chunk
        kv_text = "\n".join([f"{pair['key']}: {pair['value']}" for pair in pairs if pair['key'] and pair['value']])
        
        if kv_text.strip():
            chunk_metadata = {
                **metadata,
                "chunk_type": "key_value",
                "pair_count": len(pairs),
            }
            
            chunk = DocumentChunk(
                content=kv_text,
                metadata=chunk_metadata,
                chunk_id="",
                document_id=document_id,
                chunk_type="key_value",
                token_count=self.chunker.estimate_tokens(kv_text)
            )
            return [chunk]
        
        return []
    
    def _table_to_text(self, table: Dict[str, Any]) -> str:
        """Convert table data to text representation."""
        if not table or not isinstance(table, dict) or not table.get("cells"):
            return ""
        
        # Create a grid representation
        rows = {}
        for cell in table["cells"]:
            if not cell or not isinstance(cell, dict):
                continue
                
            row_idx = cell.get("row_index", 0)
            col_idx = cell.get("column_index", 0)
            content = cell.get("content", "")
            
            if row_idx not in rows:
                rows[row_idx] = {}
            
            rows[row_idx][col_idx] = content
        
        # Convert to text
        text_lines = []
        for row_idx in sorted(rows.keys()):
            row = rows[row_idx]
            row_text = " | ".join([row.get(col_idx, "") for col_idx in sorted(row.keys())])
            text_lines.append(row_text)
        
        return "\n".join(text_lines)
    
    def process_multiple_documents(self, file_paths: List[str], force_reprocess: bool = False) -> List[ProcessedDocument]:
        """Process multiple documents."""
        processed_docs = []
        
        for file_path in file_paths:
            try:
                processed_doc = self.process_document(file_path, force_reprocess)
                processed_docs.append(processed_doc)
            except Exception as e:
                self.logger.error(f"Failed to process {file_path}: {str(e)}")
                continue
        
        return processed_docs