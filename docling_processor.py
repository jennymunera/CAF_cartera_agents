import os
import json
import torch
from pathlib import Path
from typing import List, Dict, Any
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions, AcceleratorOptions, AcceleratorDevice, TableStructureOptions
from chunking_processor import ChunkingProcessor


class DoclingProcessor:
    """Document processor using Docling to extract and concatenate content."""
    
    def __init__(self, input_dir: str = "input_docs", output_dir: str = "output_docs", 
                 auto_chunk: bool = True, max_tokens: int = 200000):
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
        
        # Detect and configure GPU usage
        self._setup_gpu_config()
        
        # Configure OCR options for better scanned document processing
        ocr_options = self._configure_ocr_engine()
        
        # Configure accelerator options
        accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA if self.use_gpu else AcceleratorDevice.CPU
        )
        
        # Configure full pipeline options - optimized for scanned documents
        self.pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            do_picture_description=False,  # Desactivar para mejorar velocidad en documentos escaneados
            generate_page_images=False,  # No necesario para extracción de texto
            generate_picture_images=False,  # No necesario para extracción de texto
            force_backend_text=False,  # Permitir OCR cuando sea necesario
            ocr_options=ocr_options,
            accelerator_options=accelerator_options,
            # Optimizar opciones de estructura de tabla para mejor velocidad
            table_structure_options=TableStructureOptions(
                do_cell_matching=False  # Desactivar para mejorar velocidad en documentos escaneados
            )
        )
        
        # Create document converter with full configuration for multiple formats
        self.doc_converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.XLSX,
                InputFormat.PPTX,
                InputFormat.HTML,
                InputFormat.IMAGE,
                InputFormat.MD,
                InputFormat.ASCIIDOC
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options
                )
                # Other formats use default options automatically
            }
        )
    
    def _setup_gpu_config(self):
        """Configura el uso de GPU si está disponible."""
        self.use_gpu = torch.cuda.is_available()
        
        if self.use_gpu:
            self.device = torch.device('cuda')
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"GPU detectada y habilitada: {gpu_name} ({gpu_memory:.1f} GB)")
            print(f"PyTorch versión: {torch.__version__}")
            
            # Configurar optimizaciones de GPU
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
        else:
            self.device = torch.device('cpu')
            print("GPU no disponible, usando CPU")
            print(f"PyTorch versión: {torch.__version__}")
    
    def _configure_ocr_engine(self):
        """Configura el motor OCR con EasyOCR optimizado para documentos escaneados."""
        print("Usando EasyOCR con configuración optimizada para documentos escaneados")
        return EasyOcrOptions(
            lang=["es", "en"],  # Español e inglés
            force_full_page_ocr=True,  # Forzar OCR en toda la página
            confidence_threshold=0.4,  # Umbral de confianza más bajo para capturar más texto
            bitmap_area_threshold=0.01  # Umbral más bajo para detectar áreas de texto más pequeñas
        )
    
    def process_single_document(self, file_path) -> Dict[str, Any]:
        """Processes a single document and extracts its content.
        
        Args:
            file_path: Path to the file to process (string or Path object)
            
        Returns:
            Dict with document data and metadata
        """
        try:
            # Convert to Path object if it's a string
            if isinstance(file_path, str):
                file_path = Path(file_path)
                
            print(f"Processing document: {file_path.name}")
            if self.use_gpu:
                print(f"Usando GPU: {torch.cuda.get_device_name(0)}")
            else:
                print(f"Usando CPU")
            
            # Convert the document
            result = self.doc_converter.convert(str(file_path))
            
            # Extract content in different formats
            markdown_content = result.document.export_to_markdown()
            json_content = result.document.export_to_dict()
            
            # Extract metadata
            metadata = {
                "filename": file_path.name,
                "file_size": file_path.stat().st_size,
                "content_length": len(markdown_content),
                "processing_status": "success",
                "pages": len(result.document.pages) if hasattr(result.document, 'pages') else 0,
                "tables_found": len([item for item in json_content.get('main-text', []) if item.get('prov', [{}])[0].get('bbox') and 'table' in str(item).lower()]) if json_content else 0,
                "images_found": len([item for item in json_content.get('pictures', [])]) if json_content else 0
            }
            
            print(f"Document processed successfully: {file_path.name}")
            print(f"   Content length: {len(markdown_content)} characters")
            print(f"   Pages: {metadata['pages']}")
            print(f"   Tables found: {metadata['tables_found']}")
            print(f"   Images found: {metadata['images_found']}")
            
            return {
                "filename": file_path.name,
                "content": markdown_content,
                "json_data": json_content,
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
    
    def process_project_documents(self, project_name: str) -> Dict[str, Any]:
        """Processes all documents from a specific project.
        
        Args:
            project_name: Project name (folder inside input_docs)
            
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
        
        print(f"Starting project processing: {project_name}")
        
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
            doc_data = self.process_single_document(document_file)
            processed_documents.append(doc_data)
            
            if doc_data["metadata"]["processing_status"] == "success":
                successful_count += 1
            else:
                failed_count += 1
        
        # Concatenate content from successful documents
        concatenated_content = "\n\n" + "="*80 + "\n\n"
        concatenated_content += f"PROJECT: {project_name.upper()}\n"
        concatenated_content += f"PROCESSED DOCUMENTS: {successful_count}/{len(document_files)}\n"
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
    
    def save_processed_project(self, project_data: Dict[str, Any]):
        """Saves processed project data to output files in organized structure.
        
        Args:
            project_data: Processed project data
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
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        
        print(f"Files saved in organized structure:")
        print(f"   Project dir: {project_dir}")
        print(f"   Content: {markdown_file}")
        print(f"   Metadata: {json_file}")
        print(f"   Individual docs: {len([d for d in project_data['documents'] if d['metadata']['processing_status'] == 'success'])} files")
        
        # Perform automatic chunking if enabled
        if self.auto_chunk:
            print(f"\nPerforming automatic chunking analysis...")
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
        
        # Store folder structure info in project_data for later use
        project_data["folder_structure"] = {
            "project_dir": str(project_dir),
            "docs_dir": str(docs_dir),
            "agents_output_dir": str(agents_output_dir)
        }
    
    def list_available_projects(self) -> List[str]:
        """Lists available projects in input_docs.
        
        Returns:
            List of project names (folders)
        """
        if not self.input_dir.exists():
            return []
        
        projects = [item.name for item in self.input_dir.iterdir() if item.is_dir()]
        return sorted(projects)


def process_documents(project_name: str = None, auto_chunk: bool = True, max_tokens: int = 200000) -> Dict[str, Any]:
    """Main function to process documents with Docling.
    
    Args:
        project_name: Project name to process. If None, lists available projects.
        auto_chunk: Whether to perform automatic chunking after processing
        max_tokens: Maximum tokens per chunk when auto_chunk is enabled
        
    Returns:
        Processing result or list of available projects
    """
    processor = DoclingProcessor(auto_chunk=auto_chunk, max_tokens=max_tokens)
    
    if project_name is None:
        available_projects = processor.list_available_projects()
        print(f"Available projects: {available_projects}")
        return {"available_projects": available_projects}
    
    return processor.process_project_documents(project_name)


if __name__ == "__main__":
    # Usage example
    print("Docling Document Processor")
    print("="*40)
    
    # List available projects
    result = process_documents()
    
    if result.get("available_projects"):
        print("\nTo process a specific project, use:")
        print("   process_documents('project_name')")
    else:
        print("\nCreate folders in 'input_docs' with PDF files to get started.")