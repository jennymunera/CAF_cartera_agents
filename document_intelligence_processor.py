import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from chunking_processor import ChunkingProcessor

class DocumentIntelligenceProcessor:
    """Document processor using Azure Document Intelligence to extract and concatenate content."""
    
    def __init__(self, endpoint: str, api_key: str, input_dir: str = "input_docs", 
                 output_dir: str = "output_docs", auto_chunk: bool = True, max_tokens: int = 200000):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.auto_chunk = auto_chunk
        self.max_tokens = max_tokens
        
        # Create directories if they don't exist
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize chunking processor if auto_chunk is enabled
        if self.auto_chunk:
            self.chunking_processor = ChunkingProcessor(max_tokens=self.max_tokens)
        
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
    
    def process_single_document(self, file_path, model_id: str = "prebuilt-layout") -> Dict[str, Any]:
        """Processes a single document and extracts its content.
        
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
                
            print(f"Processing document with Document Intelligence: {file_path.name}")
            
            # Read file
            with open(file_path, 'rb') as f:
                document_bytes = f.read()
            
            # Analyze document - using recommended approach for v4.0
            # For .docx files, don't specify content_type for automatic detection
            if file_path.suffix.lower() == '.docx':
                poller = self.client.begin_analyze_document(
                    model_id=model_id,
                    body=document_bytes
                )
            else:
                poller = self.client.begin_analyze_document(
                    model_id=model_id,
                    body=document_bytes,
                    content_type="application/octet-stream"
                )
            
            result = poller.result()
            
            # Extract content as markdown-like format
            markdown_content = self._convert_to_markdown(result)
            
            # Extract metadata similar to DoclingProcessor
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
            
            print(f"Document processed successfully: {file_path.name}")
            print(f"   Content length: {len(markdown_content)} characters")
            print(f"   Pages: {metadata['pages']}")
            print(f"   Tables found: {metadata['tables_found']}")
            print(f"   Images found: {metadata['images_found']}")
            
            return {
                "filename": file_path.name,
                "content": markdown_content,
                "json_data": self._extract_structured_data(result),
                "metadata": metadata
            }
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {str(e)}")
            print(f"File extension: {file_path.suffix}")
            print(f"Full error details: {type(e).__name__}: {str(e)}")
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
                    print(f"Warning: Unknown point format: {type(point)} - {point}")
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Error processing polygon point {point}: {e}")
                continue
                
        return points
    
    def _save_result(self, data: Dict[str, Any]):
        filename = f"document_intelligence_{data['file_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Resultado guardado en: {output_path}")
    
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
            print(f"Warning: Project folder '{project_name}' does not exist in {self.input_dir}")
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
        
        print(f"Starting project processing with Document Intelligence: {project_name}")
        
        # Search for supported document files in the project folder
        supported_extensions = ['*.pdf', '*.docx', '*.xlsx', '*.pptx', '*.html', '*.csv', '*.png', '*.jpeg', '*.jpg', '*.tiff', '*.bmp', '*.webp']
        document_files = []
        for ext in supported_extensions:
            document_files.extend(project_path.glob(ext))
        
        if not document_files:
            print(f"Warning: No supported document files found in {project_path}")
            print(f"Supported extensions: {', '.join(supported_extensions)}")
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
        
        print(f"Found {len(document_files)} document files to process")
        
        # Process each document
        processed_documents = []
        successful_count = 0
        failed_count = 0
        
        for document_file in document_files:
            doc_data = self.process_single_document(document_file, model_id)
            processed_documents.append(doc_data)
            
            if doc_data["metadata"]["processing_status"] == "success":
                successful_count += 1
            else:
                failed_count += 1
        
        # Concatenate content from successful documents
        concatenated_content = "\n\n" + "="*80 + "\n\n"
        concatenated_content += f"PROJECT: {project_name.upper()}\n"
        concatenated_content += f"PROCESSED DOCUMENTS: {successful_count}/{len(document_files)}\n"
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
                "processing_status": "completed"
            }
        }
        
        # Save result in output_docs
        self.save_processed_project(result)
        
        print(f"Processing completed for {project_name}:")
        print(f"   Successful: {successful_count}")
        print(f"   Failed: {failed_count}")
        
        return result
    
    def process_multiple_documents(self, file_paths: List[str], model_id: str = "prebuilt-layout") -> List[Dict[str, Any]]:
        results = []
        for file_path in file_paths:
            print(f"Processing with Document Intelligence: {file_path}")
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
                print(f"Individual document saved: {doc_md_file}")
        
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
        
        print(f"Files saved in organized structure:")
        print(f"   Project dir: {project_dir}")
        print(f"   Content: {markdown_file}")
        print(f"   Metadata: {json_file}")
        print(f"   Individual docs: {len([d for d in project_data['documents'] if d['metadata']['processing_status'] == 'success'])} files")
        
        # Apply chunking if enabled
        if self.auto_chunk and self.chunking_processor:
            print(f"Applying automatic chunking to {project_name}...")
            chunking_result = self.chunking_processor.process_document_content(
                project_data["concatenated_content"], 
                project_name
            )
            
            if chunking_result['requires_chunking']:
                print(f"Document requires chunking. Creating {len(chunking_result['chunks'])} chunks...")
                saved_files = self.chunking_processor.save_chunks(chunking_result, str(self.output_dir))
                project_data["chunking_result"] = chunking_result
                project_data["chunking_result"]["saved_files"] = saved_files
                print(f"Chunks saved: {len(saved_files)} files")
            else:
                print("Document within token limit. No chunking required.")
                project_data["chunking_result"] = chunking_result
        
        print(f"Project data saved to: {project_dir}")


def list_available_projects(input_docs_path: str = "input_docs") -> List[str]:
    """Lists all available project folders in the input_docs directory.
    
    Args:
        input_docs_path: Path to the input documents directory
        
    Returns:
        List of project folder names
    """
    input_path = Path(input_docs_path)
    if not input_path.exists():
        print(f"Warning: Input directory '{input_docs_path}' does not exist")
        return []
    
    projects = [d.name for d in input_path.iterdir() if d.is_dir()]
    return sorted(projects)


def process_documents(project_name: str, 
                     processor_type: str = "docling",
                     auto_chunk: bool = False,
                     input_docs_path: str = "input_docs",
                     output_docs_path: str = "output_docs") -> Dict[str, Any]:
    """Process documents using the specified processor.
    
    Args:
        project_name: Name of the project folder to process
        processor_type: Type of processor to use ('docling' or 'document_intelligence')
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
    print(f"Available projects: {projects}")
    
    # Process a specific project
    if projects:
        project_name = projects[0]  # Process first available project
        print(f"\nProcessing project: {project_name}")
        result = processor.process_project_documents(project_name)
        print(f"Processing completed. Status: {result['metadata']['processing_status']}")
        print(f"Documents processed: {result['metadata']['successful_documents']}/{result['metadata']['total_documents']}")
    else:
        print("No projects found in input_docs directory")