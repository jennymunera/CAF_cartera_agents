import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from chunking_processor import ChunkingProcessor
from utils.app_insights_logger import get_logger

# Configure logging with Azure Application Insights
logger = get_logger('document_intelligence_processor')

class DocumentIntelligenceProcessor:
    """Document processor using Azure Document Intelligence to extract and concatenate content."""
    
    def __init__(self, endpoint: str, api_key: str, input_dir: str = "input_docs", 
                 output_dir: str = "output_docs", auto_chunk: bool = True, max_tokens: int = 100000):
        self.endpoint = endpoint
        self.api_key = api_key
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.auto_chunk = auto_chunk
        self.max_tokens = max_tokens
        
        # Ensure endpoint ends with /
        if not self.endpoint.endswith('/'):
            self.endpoint += '/'
            
        # API version for Document Intelligence
        self.api_version = "2024-02-29-preview"
        
        # Create directories if they don't exist
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize chunking processor if auto_chunk is enabled
        if self.auto_chunk:
            self.chunking_processor = ChunkingProcessor(max_tokens=self.max_tokens, generate_jsonl=True)
    
    def _is_document_already_chunked(self, file_path: Path, project_name: str) -> bool:
        """Check if a document has already been chunked by looking for chunk files in chunks folder.
        
        Args:
            file_path: Path to the document file
            project_name: Name of the project
            
        Returns:
            bool: True if document has already been chunked, False otherwise
        """
        try:
            # Check if chunk files exist in chunks folder
            doc_stem = file_path.stem  # filename without extension
            chunks_dir = self.output_dir / project_name / "chunks"
            
            if chunks_dir.exists():
                # Look for any chunk files that start with the document name
                chunk_pattern = f"{doc_stem}_chunk_*.json"
                chunk_files = list(chunks_dir.glob(chunk_pattern))
                
                if chunk_files:
                    # Verify at least one chunk file has valid content
                    for chunk_file in chunk_files:
                        try:
                            if chunk_file.stat().st_size > 50:  # At least 50 bytes
                                with open(chunk_file, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if data.get('chunk_content') or data.get('content'):
                                        logger.info(f"Document already chunked: {file_path.name} -> {len(chunk_files)} chunks found")
                                        return True
                        except (json.JSONDecodeError, KeyError, OSError):
                            continue
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking if document {file_path.name} was chunked: {str(e)}")
            return False  # If we can't check, assume it needs processing
    
    def _is_document_already_processed(self, file_path: Path, project_name: str) -> bool:
        """Check if a document has already been processed by looking for output files in DI folder or chunks folder.
        
        Args:
            file_path: Path to the document file
            project_name: Name of the project
            
        Returns:
            bool: True if document has already been processed or chunked, False otherwise
        """
        try:
            # First check if document has been processed (DI folder)
            doc_stem = file_path.stem  # filename without extension
            doc_json_file = self.output_dir / project_name / "DI" / f"{doc_stem}.json"
            
            if doc_json_file.exists():
                # Additional check: verify the file is not empty and has valid content
                if doc_json_file.stat().st_size > 100:  # At least 100 bytes
                    # Verify it's a valid JSON with content
                    try:
                        with open(doc_json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Check if it has content and wasn't an error
                            # processing_status is in metadata section
                            metadata = data.get('metadata', {})
                            if metadata.get('processing_status') == 'success' and data.get('content'):
                                logger.info(f"Document already processed (DI): {file_path.name} -> {doc_json_file.name}")
                                return True
                    except (json.JSONDecodeError, KeyError):
                        logger.warning(f"Invalid JSON file found, will reprocess: {doc_json_file}")
                        # Continue to check chunks
            
            # Also check if document has been chunked (chunks folder)
            if self._is_document_already_chunked(file_path, project_name):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking if document {file_path.name} was processed: {str(e)}")
            return False  # If we can't check, assume it needs processing
    
    def _make_rest_request(self, method: str, url: str, headers: Dict[str, str], data: Any = None, files: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make REST API request to Document Intelligence"""
        try:
            if method.upper() == 'POST':
                if files:
                    response = requests.post(url, headers=headers, files=files, timeout=300)
                else:
                    response = requests.post(url, headers=headers, json=data, timeout=300)
            elif method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=300)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"REST API request failed: {str(e)}")
            raise
    
    def process_single_document(self, file_path, model_id: str = "prebuilt-layout") -> Dict[str, Any]:
        """Processes a single document and extracts its content using REST API.
        
        Args:
            file_path: Path to the file to process (string or Path object)
            model_id: Document Intelligence model to use
            
        Returns:
            Dict with document data and metadata
        """
        try:
            # Convert to Path object if it's a string
            if isinstance(file_path, str):
                file_path = Path(file_path)
                
            logger.info(f"Processing document with Document Intelligence REST API: {file_path.name}")
            
            # Prepare headers
            headers = {
                'Ocp-Apim-Subscription-Key': self.api_key
            }
            
            # Determine output format based on file type
            output_format = "markdown" if file_path.suffix.lower() == '.docx' else "markdown"
            
            # Start analysis
            analyze_url = f"{self.endpoint}documentintelligence/documentModels/{model_id}:analyze"
            analyze_params = {
                'api-version': self.api_version,
                'outputContentFormat': output_format
            }
            
            # Add query parameters to URL
            analyze_url_with_params = f"{analyze_url}?" + "&".join([f"{k}={v}" for k, v in analyze_params.items()])
            
            # Read file and prepare for upload
            with open(file_path, 'rb') as f:
                document_bytes = f.read()
            
            # Prepare files for multipart upload
            files = {
                'file': (file_path.name, document_bytes, 'application/octet-stream')
            }
            
            # Start the analysis
            response = requests.post(
                analyze_url_with_params,
                headers=headers,
                files=files,
                timeout=300
            )
            response.raise_for_status()
            
            # Get operation location from response headers
            operation_location = response.headers.get('Operation-Location')
            if not operation_location:
                raise ValueError("No operation location returned from analysis request")
            
            # Poll for results
            max_attempts = 60  # 5 minutes with 5-second intervals
            attempt = 0
            
            while attempt < max_attempts:
                result_response = requests.get(operation_location, headers={'Ocp-Apim-Subscription-Key': self.api_key})
                result_response.raise_for_status()
                result_data = result_response.json()
                
                status = result_data.get('status')
                if status == 'succeeded':
                    break
                elif status == 'failed':
                    error_msg = result_data.get('error', {}).get('message', 'Analysis failed')
                    raise Exception(f"Document analysis failed: {error_msg}")
                
                time.sleep(5)
                attempt += 1
            
            if attempt >= max_attempts:
                raise Exception("Document analysis timed out")
            
            # Extract content from results
            analyze_result = result_data.get('analyzeResult', {})
            result = type('AnalyzeResult', (), analyze_result)()
            
            # Use direct markdown content from Document Intelligence
            markdown_content = result.content if result.content else self._convert_to_markdown(result)
            
            # Extract metadata from Document Intelligence response
            metadata = {
                "filename": file_path.name,
                "file_size": file_path.stat().st_size,
                "content_length": len(markdown_content),
                "processing_status": "success",
                "pages": len(result.pages) if result.pages else 0,
                "tables_found": len(result.tables) if result.tables else 0,
                "images_found": len(result.figures) if result.figures else 0,
                "confidence_score": self._calculate_average_confidence(result)
            }
            
            logger.info(f"Document processed successfully: {file_path.name}")
            logger.info(f"Content length: {len(markdown_content)} characters")
            logger.info(f"Pages: {metadata['pages']}")
            logger.info(f"Tables found: {metadata['tables_found']}")
            logger.info(f"Images found: {metadata['images_found']}")
            
            return {
                "filename": file_path.name,
                "content": markdown_content,
                "json_data": self._extract_structured_data(result),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {str(e)}")
            logger.error(f"File extension: {file_path.suffix}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
            return {
                "filename": file_path.name if hasattr(file_path, 'name') else str(file_path),
                "content": "",
                "json_data": {},
                "metadata": {
                    "filename": file_path.name if hasattr(file_path, 'name') else str(file_path),
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
        """Processes all documents from a specific project.
        
        Args:
            project_name: Project name (folder inside input_docs)
            model_id: Document Intelligence model to use
            
        Returns:
            Dict with all processed and concatenated documents
        """
        project_path = self.input_dir / project_name
        
        if not project_path.exists():
            logger.warning(f"Project folder '{project_name}' does not exist in {self.input_dir}")
            return {
                "project_name": project_name,
                "documents": [],
                "concatenated_content": "",
                "metadata": {
                    "total_documents": 0,
                    "successful_documents": 0,
                    "failed_documents": 0,
                    "processing_status": "project_not_found"
                }
            }
        
        logger.info(f"Starting project processing with Document Intelligence: {project_name}")
        
        # Search for supported document files in the project folder
        # Based on Azure Document Intelligence v4.0 Layout model supported formats
        supported_extensions = ['*.pdf', '*.docx', '*.xlsx', '*.pptx', '*.html', '*.csv', '*.png', '*.jpeg', '*.jpg', '*.tiff', '*.bmp', '*.heif']
        all_document_files = []
        for ext in supported_extensions:
            all_document_files.extend(project_path.glob(ext))
        
        # Filter documents by required prefixes (INI, IXP, DEC, ROP, IFS)
        required_prefixes = ['INI', 'IXP', 'DEC', 'ROP', 'IFS']
        document_files = []
        filtered_out_files = []
        
        for file_path in all_document_files:
            filename = file_path.name.upper()  # Convert to uppercase for comparison
            if any(filename.startswith(prefix) for prefix in required_prefixes):
                document_files.append(file_path)
            else:
                filtered_out_files.append(file_path)
        
        logger.info(f"Found {len(all_document_files)} total document files")
        logger.info(f"Filtered to {len(document_files)} files with required prefixes (INI, IXP, DEC, ROP, IFS)")
        if filtered_out_files:
            logger.info(f"Excluded {len(filtered_out_files)} files without required prefixes:")
            for excluded_file in filtered_out_files[:5]:  # Show first 5 excluded files
                logger.info(f"   - {excluded_file.name}")
            if len(filtered_out_files) > 5:
                logger.info(f"   ... and {len(filtered_out_files) - 5} more files")
        
        if not document_files:
            logger.warning(f"No document files found with required prefixes (INI, IXP, DEC, ROP, IFS) in {project_path}")
            logger.info(f"Supported extensions: {', '.join(supported_extensions)}")
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
        
        for document_file in document_files:
            # Check if document was already processed
            if self._is_document_already_processed(document_file, project_name):
                skipped_count += 1
                # Create a mock successful result for already processed documents
                doc_data = {
                    "filename": document_file.name,
                    "content": "[Document already processed - content available in output files]",
                    "json_data": {},
                    "metadata": {
                        "filename": document_file.name,
                        "file_size": document_file.stat().st_size,
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
            doc_data = self.process_single_document(document_file, model_id)
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
        """Saves processed project data to output directory.
        
        Args:
            project_data: Dictionary containing project processing results
        """
        project_name = project_data["project_name"]
        
        # Create project folder structure
        project_dir = self.output_dir / project_name
        docs_dir = project_dir / "docs"
        agents_output_dir = project_dir / "agents_output"
        
        # Create directories if they don't exist
        project_dir.mkdir(exist_ok=True)
        docs_dir.mkdir(exist_ok=True)
        agents_output_dir.mkdir(exist_ok=True)
        
        # Save individual document markdown files in docs folder
        for doc in project_data["documents"]:
            if doc["metadata"]["processing_status"] == "success":
                doc_md_file = docs_dir / f"{Path(doc['filename']).stem}.md"
                with open(doc_md_file, 'w', encoding='utf-8') as f:
                    f.write(f"# {doc['filename']}\n\n")
                    f.write(doc["content"])
                logger.info(f"Individual document saved: {doc_md_file}")
        
        # Save concatenated content as markdown in docs folder
        markdown_file = docs_dir / f"{project_name}_concatenated.md"
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(project_data["concatenated_content"])
        
        # Save metadata as JSON in docs folder
        json_file = docs_dir / f"{project_name}_metadata.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "project_name": project_name,
                "processor_type": "Azure Document Intelligence",
                "metadata": project_data["metadata"],
                "documents": [{
                    "filename": doc["filename"],
                    "metadata": doc["metadata"]
                } for doc in project_data["documents"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save individual document JSON data in docs folder
        for doc in project_data["documents"]:
            if doc["json_data"]:
                doc_json_file = docs_dir / f"{Path(doc['filename']).stem}_document_intelligence.json"
                with open(doc_json_file, 'w', encoding='utf-8') as f:
                    json.dump(doc["json_data"], f, indent=2, ensure_ascii=False)
        
        logger.info(f"Files saved in organized structure:")
        logger.info(f"   Project dir: {project_dir}")
        logger.info(f"   Content: {markdown_file}")
        logger.info(f"   Metadata: {json_file}")
        logger.info(f"   Individual docs: {len([d for d in project_data['documents'] if d['metadata']['processing_status'] == 'success'])} files")
        
        # Apply chunking if enabled
        if self.auto_chunk and self.chunking_processor:
            logger.info(f"Applying automatic chunking to {project_name}...")
            chunking_result = self.chunking_processor.process_document_content(
                project_data["concatenated_content"], 
                project_name
            )
            
            if chunking_result['requires_chunking']:
                logger.info(f"Document requires chunking. Creating {len(chunking_result['chunks'])} chunks...")
                saved_files = self.chunking_processor.save_chunks(chunking_result, str(self.output_dir))
                project_data["chunking_result"] = chunking_result
                project_data["chunking_result"]["saved_files"] = saved_files
                logger.info(f"Chunks saved: {len(saved_files)} files")
            else:
                logger.info("Document within token limit. No chunking required.")
                project_data["chunking_result"] = chunking_result
        
        logger.info(f"Project data saved to: {project_dir}")


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