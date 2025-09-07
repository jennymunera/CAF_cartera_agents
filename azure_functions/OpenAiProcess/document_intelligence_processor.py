import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from chunking_processor import ChunkingProcessor
from utils.blob_storage_client import BlobStorageClient
from utils.app_insights_logger import get_logger

# Configure logging with Azure Application Insights
logger = get_logger('document_intelligence_processor')

class DocumentIntelligenceProcessor:
    """Document processor using Azure Document Intelligence to extract and concatenate content."""
    
    def __init__(self, endpoint: str, api_key: str, auto_chunk: bool = True, max_tokens: int = 100000):
        self.endpoint = endpoint
        self.api_key = api_key
        self.auto_chunk = auto_chunk
        self.max_tokens = max_tokens
        
        # Initialize Document Intelligence client
        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
        
        # Initialize blob storage client
        self.blob_client = BlobStorageClient()
        
        # Initialize chunking processor if auto_chunk is enabled
        if self.auto_chunk:
            self.chunking_processor = ChunkingProcessor(max_tokens=self.max_tokens, generate_jsonl=True)
    
    def _is_document_already_chunked(self, document_name: str, project_name: str) -> bool:
        """Check if a document has already been chunked by looking for chunk files in chunks folder.
        
        Args:
            document_name: Name of the document file
            project_name: Name of the project
            
        Returns:
            bool: True if document has already been chunked, False otherwise
        """
        try:
            # Check if chunk files exist in processed/chunks folder
            doc_stem = Path(document_name).stem  # filename without extension
            
            # Try to find any chunk file for this document
            chunk_filename = f"{doc_stem}_chunk_1.json"  # Check for first chunk
            
            if self.blob_client.document_exists_in_processed(project_name, "chunks", chunk_filename):
                logger.info(f"Document already chunked: {document_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking if document {document_name} was chunked: {str(e)}")
            return False  # If we can't check, assume it needs processing
    
    def _is_document_already_processed(self, document_name: str, project_name: str) -> bool:
        """Check if a document has already been processed by looking for output files in DI folder or chunks folder.
        
        Args:
            document_name: Name of the document file
            project_name: Name of the project
            
        Returns:
            bool: True if document has already been processed or chunked, False otherwise
        """
        try:
            # First check if document has been processed (DI folder)
            doc_stem = Path(document_name).stem  # filename without extension
            doc_json_filename = f"{doc_stem}.json"
            
            if self.blob_client.document_exists_in_processed(project_name, "DI", doc_json_filename):
                # Verify it's a valid JSON with content
                try:
                    data = self.blob_client.load_processed_document(project_name, "DI", doc_json_filename)
                    # Check if it has content and wasn't an error
                    metadata = data.get('metadata', {})
                    if metadata.get('processing_status') == 'success' and data.get('content'):
                        logger.info(f"Document already processed (DI): {document_name}")
                        return True
                except (json.JSONDecodeError, KeyError, FileNotFoundError):
                    logger.warning(f"Invalid JSON file found, will reprocess: {doc_json_filename}")
                    # Continue to check chunks
            
            # Also check if document has been chunked (chunks folder)
            if self._is_document_already_chunked(document_name, project_name):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking if document {document_name} was processed: {str(e)}")
            return False  # If we can't check, assume it needs processing
    
    def process_single_document(self, project_name: str, document_name: str, model_id: str = "prebuilt-layout") -> Dict[str, Any]:
        """Processes a single document and extracts its content.
        
        Args:
            project_name: Name of the project
            document_name: Name of the document to process
            model_id: Document Intelligence model to use
            
        Returns:
            Dict with document data and metadata
        """
        try:
            logger.info(f"Processing document with Document Intelligence: {document_name}")
            
            # Download document from blob storage
            document_bytes = self.blob_client.download_raw_document(project_name, document_name)
            
            # Analyze document - using recommended approach for v4.0 with direct markdown output
            # For .docx files, don't specify content_type for automatic detection
            if Path(document_name).suffix.lower() == '.docx':
                poller = self.client.begin_analyze_document(
                    model_id=model_id,
                    body=document_bytes,
                    output_content_format="markdown"
                )
            else:
                poller = self.client.begin_analyze_document(
                    model_id=model_id,
                    body=document_bytes,
                    content_type="application/octet-stream",
                    output_content_format="markdown"
                )
            
            result = poller.result()
            
            # Use direct markdown content from Document Intelligence
            markdown_content = result.content if result.content else self._convert_to_markdown(result)
            
            # Extract metadata from Document Intelligence response
            metadata = {
                "filename": document_name,
                "file_size": len(document_bytes),
                "content_length": len(markdown_content),
                "processing_status": "success",
                "pages": len(result.pages) if result.pages else 0,
                "tables_found": len(result.tables) if result.tables else 0,
                "images_found": len(result.figures) if result.figures else 0,
                "confidence_score": self._calculate_average_confidence(result)
            }
            
            logger.info(f"Document processed successfully: {document_name}")
            logger.info(f"Content length: {len(markdown_content)} characters")
            logger.info(f"Pages: {metadata['pages']}")
            logger.info(f"Tables found: {metadata['tables_found']}")
            logger.info(f"Images found: {metadata['images_found']}")
            
            return {
                "filename": document_name,
                "content": markdown_content,
                "json_data": self._extract_structured_data(result),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing {document_name}: {str(e)}")
            logger.error(f"File extension: {Path(document_name).suffix}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
            return {
                "filename": document_name,
                "content": "",
                "json_data": {},
                "metadata": {
                    "filename": document_name,
                    "file_size": 0,
                    "content_length": 0,
                    "processing_status": "error",
                    "error_message": str(e),
                    "pages": 0,
                    "tables_found": 0,
                    "images_found": 0
                }
            }
    
    def _convert_to_markdown(self, result) -> str:
        """Convert Document Intelligence result to markdown format."""
        markdown_content = ""
        
        # Add main text content
        if result.content:
            markdown_content += result.content + "\n\n"
        
        # Add tables in markdown format
        if result.tables:
            for i, table in enumerate(result.tables):
                markdown_content += f"\n## Table {i+1}\n\n"
                
                # Create markdown table
                if table.cells:
                    # Group cells by row
                    rows = {}
                    max_col = 0
                    for cell in table.cells:
                        row_idx = cell.row_index
                        col_idx = cell.column_index
                        if row_idx not in rows:
                            rows[row_idx] = {}
                        rows[row_idx][col_idx] = cell.content
                        max_col = max(max_col, col_idx)
                    
                    # Generate markdown table
                    for row_idx in sorted(rows.keys()):
                        row_cells = []
                        for col_idx in range(max_col + 1):
                            cell_content = rows[row_idx].get(col_idx, "")
                            row_cells.append(cell_content)
                        markdown_content += "| " + " | ".join(row_cells) + " |\n"
                        
                        # Add header separator for first row
                        if row_idx == 0:
                            markdown_content += "| " + " | ".join(["---"] * (max_col + 1)) + " |\n"
                
                markdown_content += "\n"
        
        # Add key-value pairs
        if result.key_value_pairs:
            markdown_content += "\n## Key-Value Pairs\n\n"
            for pair in result.key_value_pairs:
                key = pair.key.content if pair.key else ""
                value = pair.value.content if pair.value else ""
                markdown_content += f"**{key}**: {value}\n\n"
        
        return markdown_content
    
    def _extract_structured_data(self, result) -> Dict[str, Any]:
        """Extract structured data similar to Docling's JSON format."""
        return {
            'content': result.content if result.content else "",
            'tables': self._extract_tables(result),
            'images': self._extract_images(result),
            'key_value_pairs': self._extract_key_value_pairs(result),
            'paragraphs': self._extract_paragraphs(result)
        }
    
    def _extract_text(self, result) -> str:
        if result.content:
            return result.content
        return ""
    
    def _extract_tables(self, result) -> List[Dict[str, Any]]:
        tables = []
        if not result.tables:
            return tables
        
        for i, table in enumerate(result.tables):
            table_data = {
                'table_id': i,
                'row_count': table.row_count,
                'column_count': table.column_count,
                'cells': [],
                'confidence': getattr(table, 'confidence', None)
            }
            
            if table.cells:
                for cell in table.cells:
                    cell_data = {
                        'content': cell.content,
                        'row_index': cell.row_index,
                        'column_index': cell.column_index,
                        'row_span': getattr(cell, 'row_span', 1),
                        'column_span': getattr(cell, 'column_span', 1),
                        'confidence': getattr(cell, 'confidence', None),
                        'kind': getattr(cell, 'kind', None)
                    }
                    table_data['cells'].append(cell_data)
            
            tables.append(table_data)
        
        return tables
    
    def _extract_images(self, result) -> List[Dict[str, Any]]:
        images = []
        if not result.figures:
            return images
        
        for i, figure in enumerate(result.figures):
            # Extract caption safely - convert DocumentCaption to string
            caption = getattr(figure, 'caption', '')
            if hasattr(caption, 'content'):
                caption_text = caption.content
            else:
                caption_text = str(caption) if caption else ''
            
            image_data = {
                'figure_id': i,
                'caption': caption_text,
                'bounding_regions': [],
                'confidence': getattr(figure, 'confidence', None)
            }
            
            if hasattr(figure, 'bounding_regions') and figure.bounding_regions:
                for region in figure.bounding_regions:
                    region_data = {
                        'page_number': region.page_number,
                        'polygon': self._extract_polygon_points(region.polygon) if region.polygon else []
                    }
                    image_data['bounding_regions'].append(region_data)
            
            images.append(image_data)
        
        return images
    
    def _extract_key_value_pairs(self, result) -> List[Dict[str, Any]]:
        pairs = []
        if not result.key_value_pairs:
            return pairs
        
        for pair in result.key_value_pairs:
            pair_data = {
                'key': pair.key.content if pair.key else '',
                'value': pair.value.content if pair.value else '',
                'confidence': pair.confidence if hasattr(pair, 'confidence') else None
            }
            pairs.append(pair_data)
        
        return pairs
    
    def _extract_paragraphs(self, result) -> List[Dict[str, Any]]:
        paragraphs = []
        if not result.paragraphs:
            return paragraphs
        
        for i, paragraph in enumerate(result.paragraphs):
            paragraph_data = {
                'paragraph_id': i,
                'content': paragraph.content,
                'role': getattr(paragraph, 'role', None),
                'confidence': getattr(paragraph, 'confidence', None)
            }
            paragraphs.append(paragraph_data)
        
        return paragraphs
    
    def _calculate_average_confidence(self, result) -> Optional[float]:
        confidences = []
        
        # Recopilar scores de confianza de diferentes elementos
        if result.tables:
            for table in result.tables:
                if hasattr(table, 'confidence') and table.confidence:
                    confidences.append(table.confidence)
        
        if result.paragraphs:
            for paragraph in result.paragraphs:
                if hasattr(paragraph, 'confidence') and paragraph.confidence:
                    confidences.append(paragraph.confidence)
        
        if result.key_value_pairs:
            for pair in result.key_value_pairs:
                if hasattr(pair, 'confidence') and pair.confidence:
                    confidences.append(pair.confidence)
        
        return sum(confidences) / len(confidences) if confidences else None
    
    def _extract_polygon_points(self, polygon) -> List[Dict[str, float]]:
        """Extract polygon points handling different data formats."""
        points = []
        if not polygon:
            return points
            
        for point in polygon:
            try:
                # If point has x and y attributes
                if hasattr(point, 'x') and hasattr(point, 'y'):
                    points.append({'x': float(point.x), 'y': float(point.y)})
                # If point is a dict with x and y keys
                elif isinstance(point, dict) and 'x' in point and 'y' in point:
                    points.append({'x': float(point['x']), 'y': float(point['y'])})
                # If point is a list or tuple with 2 elements
                elif isinstance(point, (list, tuple)) and len(point) >= 2:
                    points.append({'x': float(point[0]), 'y': float(point[1])})
                # If point is just a number (shouldn't happen but handle gracefully)
                elif isinstance(point, (int, float)):
                    # Skip invalid points
                    continue
                else:
                    logger.warning(f"Unknown point format: {type(point)} - {point}")
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error processing polygon point {point}: {e}")
                continue
                
        return points
    
    def _save_result(self, data: Dict[str, Any]):
        filename = f"document_intelligence_{data['file_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Result saved to: {output_path}")
    
    def process_project_documents(self, project_name: str, model_id: str = "prebuilt-layout") -> Dict[str, Any]:
        """Processes all documents from a specific project using blob storage.
        
        Args:
            project_name: Project name
            model_id: Document Intelligence model to use
            
        Returns:
            Dict with all processed and concatenated documents
        """
        logger.info(f"Starting project processing with Document Intelligence: {project_name}")
        
        # Get list of raw documents from blob storage (documents/basedocuments/{project}/raw/)
        try:
            raw_documents = self.blob_client.list_raw_documents(project_name)
        except Exception as e:
            logger.error(f"Error listing raw documents for project {project_name}: {str(e)}")
            return {
                "project_name": project_name,
                "documents": [],
                "concatenated_content": "",
                "metadata": {
                    "total_documents": 0,
                    "successful_documents": 0,
                    "failed_documents": 0,
                    "processing_status": "error_listing_documents"
                }
            }
        
        if not raw_documents:
            logger.warning(f"No raw documents found for project {project_name}")
            return {
                "project_name": project_name,
                "documents": [],
                "concatenated_content": "",
                "metadata": {
                    "total_documents": 0,
                    "successful_documents": 0,
                    "failed_documents": 0,
                    "processing_status": "no_documents_found"
                }
            }
        
        # Filter documents by required prefixes (INI, IXP, DEC, ROP, IFS)
        required_prefixes = ['INI', 'IXP', 'DEC', 'ROP', 'IFS']
        document_files = []
        filtered_out_files = []
        
        for document_name in raw_documents:
            filename_upper = document_name.upper()  # Convert to uppercase for comparison
            if any(filename_upper.startswith(prefix) for prefix in required_prefixes):
                document_files.append(document_name)
            else:
                filtered_out_files.append(document_name)
        
        logger.info(f"Found {len(raw_documents)} total document files")
        logger.info(f"Filtered to {len(document_files)} files with required prefixes (INI, IXP, DEC, ROP, IFS)")
        if filtered_out_files:
            logger.info(f"Excluded {len(filtered_out_files)} files without required prefixes:")
            for excluded_file in filtered_out_files[:5]:  # Show first 5 excluded files
                logger.info(f"   - {excluded_file}")
            if len(filtered_out_files) > 5:
                logger.info(f"   ... and {len(filtered_out_files) - 5} more files")
        
        if not document_files:
            logger.warning(f"No document files found with required prefixes (INI, IXP, DEC, ROP, IFS) for project {project_name}")
            return {
                "project_name": project_name,
                "documents": [],
                "concatenated_content": "",
                "metadata": {
                    "total_documents": 0,
                    "successful_documents": 0,
                    "failed_documents": 0,
                    "processing_status": "no_documents_with_required_prefixes"
                }
            }
        
        logger.info(f"Processing {len(document_files)} document files with required prefixes")
        
        # Process each document (skip already processed ones)
        processed_documents = []
        successful_count = 0
        failed_count = 0
        skipped_count = 0
        
        for document_name in document_files:
            # Check if document was already processed
            if self._is_document_already_processed(document_name, project_name):
                skipped_count += 1
                # Create a mock successful result for already processed documents
                doc_data = {
                    "filename": document_name,
                    "content": "[Document already processed - content available in output files]",
                    "json_data": {},
                    "metadata": {
                        "filename": document_name,
                        "file_size": 0,  # Size will be determined from blob storage if needed
                        "content_length": 0,
                        "processing_status": "skipped_already_processed",
                        "pages": 0,
                        "tables_found": 0,
                        "images_found": 0,
                        "confidence_score": 1.0
                    }
                }
                processed_documents.append(doc_data)
                continue
            
            # Process new document
            doc_data = self.process_single_document(project_name, document_name, model_id)
            processed_documents.append(doc_data)
            
            if doc_data["metadata"]["processing_status"] == "success":
                successful_count += 1
            else:
                failed_count += 1
        
        # Concatenate content from successful documents (exclude skipped ones from content)
        concatenated_content = "\n\n" + "="*80 + "\n\n"
        concatenated_content += f"PROJECT: {project_name.upper()}\n"
        concatenated_content += f"PROCESSED DOCUMENTS: {successful_count}/{len(document_files)}\n"
        concatenated_content += f"SKIPPED DOCUMENTS: {skipped_count}\n"
        concatenated_content += f"PROCESSOR: Azure Document Intelligence\n"
        concatenated_content += "="*80 + "\n\n"
        
        for doc in processed_documents:
            if doc["metadata"]["processing_status"] == "success":
                concatenated_content += f"\n\n--- DOCUMENT: {doc['filename']} ---\n\n"
                concatenated_content += doc["content"]
                concatenated_content += "\n\n" + "-"*50 + "\n\n"
        
        # Create final result
        result = {
            "project_name": project_name,
            "documents": processed_documents,
            "concatenated_content": concatenated_content,
            "metadata": {
                "total_documents": len(document_files),
                "successful_documents": successful_count,
                "failed_documents": failed_count,
                "skipped_documents": skipped_count,
                "processing_status": "completed"
            }
        }
        
        # Save result in output_docs
        self.save_processed_project(result)
        
        logger.info(f"Processing completed for {project_name}:")
        logger.info(f"   Successful: {successful_count}")
        logger.info(f"   Failed: {failed_count}")
        logger.info(f"   Skipped (already processed): {skipped_count}")
        logger.info(f"   Total documents: {len(document_files)}")
        
        return result
    
    def process_multiple_documents(self, file_paths: List[str], model_id: str = "prebuilt-layout") -> List[Dict[str, Any]]:
        results = []
        for file_path in file_paths:
            logger.info(f"Processing with Document Intelligence: {file_path}")
            result = self.process_single_document(file_path, model_id)
            results.append(result)
        
        return results
    
    def save_processed_project(self, project_data: Dict[str, Any]) -> None:
        """Saves processed project data to blob storage.
        
        Args:
            project_data: Dictionary containing project processing results
        """
        project_name = project_data["project_name"]
        
        try:
            # Save individual document results to caf-documents/basedocuments/{project}/processed/DI/
            for doc in project_data["documents"]:
                if doc["metadata"]["processing_status"] == "success":
                    # Save processed document content and metadata
                    # Create combined content with metadata
                    combined_content = {
                        "content": doc["content"],
                        "metadata": doc["metadata"],
                        "json_data": doc["json_data"]
                    }
                    
                    # Save as JSON file
                    json_filename = doc["filename"].replace(".pdf", ".json").replace(".docx", ".json")
                    self.blob_client.save_processed_document(
                        project_name=project_name,
                        subfolder="DI",
                        document_name=json_filename,
                        content=combined_content
                    )
                    logger.info(f"Individual document saved to blob storage: {doc['filename']}")
            
            # Save project metadata
            metadata_content = json.dumps({
                "project_name": project_name,
                "processor_type": "Azure Document Intelligence",
                "metadata": project_data["metadata"],
                "documents": [{
                    "filename": doc["filename"],
                    "metadata": doc["metadata"]
                } for doc in project_data["documents"]]
            }, indent=2, ensure_ascii=False)
            
            # Upload project metadata to blob storage
            metadata_blob_path = f"caf-documents/basedocuments/{project_name}/processed/DI/{project_name}_metadata.json"
            self.blob_client.upload_blob(metadata_blob_path, metadata_content, "application/json")
            
            logger.info(f"Project data saved to blob storage:")
            logger.info(f"   Project: {project_name}")
            logger.info(f"   Location: caf-documents/basedocuments/{project_name}/processed/DI/")
            logger.info(f"   Individual docs: {len([d for d in project_data['documents'] if d['metadata']['processing_status'] == 'success'])} files")
            
        except Exception as e:
            logger.error(f"Error saving processed project data to blob storage: {str(e)}")
            raise
        
        # Apply chunking if enabled
        if self.auto_chunk and self.chunking_processor:
            logger.info(f"Applying automatic chunking to {project_name}...")
            chunking_result = self.chunking_processor.process_document_content(
                project_data["concatenated_content"], 
                project_name
            )
            
            if chunking_result['requires_chunking']:
                logger.info(f"Document requires chunking. Creating {len(chunking_result['chunks'])} chunks...")
                # Save chunks to blob storage instead of local directory
                saved_files = self.chunking_processor.save_chunks_to_blob(chunking_result, project_name)
                project_data["chunking_result"] = chunking_result
                project_data["chunking_result"]["saved_files"] = saved_files
                logger.info(f"Chunks saved to blob storage: {len(saved_files)} files")
            else:
                logger.info("Document within token limit. No chunking required.")
                project_data["chunking_result"] = chunking_result
        
        logger.info(f"Project data saved to blob storage for project: {project_name}")


def list_available_projects(input_docs_path: str = "input_docs") -> List[str]:
    """Lists all available project folders in the input_docs directory.
    
    Args:
        input_docs_path: Path to the input documents directory
        
    Returns:
        List of project folder names
    """
    input_path = Path(input_docs_path)
    if not input_path.exists():
        logger.warning(f"Input directory '{input_docs_path}' does not exist")
        return []
    
    projects = [d.name for d in input_path.iterdir() if d.is_dir()]
    return sorted(projects)


def process_documents(project_name: str, 
                     processor_type: str = "document_intelligence",
                     auto_chunk: bool = False,
                     input_docs_path: str = "input_docs",
                     output_docs_path: str = "output_docs") -> Dict[str, Any]:
    """Process documents using the specified processor.
    
    Args:
        project_name: Name of the project folder to process
        processor_type: Type of processor to use (only 'document_intelligence' is supported)
        auto_chunk: Whether to enable automatic chunking
        input_docs_path: Path to input documents directory
        output_docs_path: Path to output documents directory
        
    Returns:
        Dictionary with processing results
    """
    if processor_type.lower() == "document_intelligence":
        processor = DocumentIntelligenceProcessor(
            auto_chunk=auto_chunk,
            input_docs_path=input_docs_path,
            output_docs_path=output_docs_path
        )
        return processor.process_project_documents(project_name)


if __name__ == "__main__":
    # Example usage
    processor = DocumentIntelligenceProcessor(
        auto_chunk=True,
        input_docs_path="input_docs",
        output_docs_path="output_docs"
    )
    
    # List available projects
    projects = list_available_projects()
    logger.info(f"Available projects: {projects}")
    
    # Process a specific project
    if projects:
        project_name = projects[0]  # Process first available project
        logger.info(f"\nProcessing project: {project_name}")
        result = processor.process_project_documents(project_name)
        logger.info(f"Processing completed. Status: {result['metadata']['processing_status']}")
        logger.info(f"Documents processed: {result['metadata']['successful_documents']}/{result['metadata']['total_documents']}")
    else:
        logger.warning("No projects found in input_docs directory")