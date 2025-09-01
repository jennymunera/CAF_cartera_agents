#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

def test_docx_processing():
    """Test processing of DOCX file with special characters"""
    
    # Configure DocumentConverter with all supported formats
    doc_converter = DocumentConverter(
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
                pipeline_options=PdfPipelineOptions(
                    do_ocr=True,
                    do_table_structure=True,
                    do_picture_description=True,
                    generate_page_images=True,
                    generate_picture_images=True
                )
            )
        }
    )
    
    # Test the specific DOCX file
    docx_file = Path("input_docs/CFA009660/con-cfa009660--ANEXO B  km25 - Tarata - Anzaldo - Ri╠üo Caine - 18 Julio 2016 (JSM).docx")
    
    print(f"Testing file: {docx_file}")
    print(f"File exists: {docx_file.exists()}")
    print(f"File size: {docx_file.stat().st_size if docx_file.exists() else 'N/A'} bytes")
    print(f"File encoding test: {repr(str(docx_file))}")
    
    if not docx_file.exists():
        print("ERROR: File does not exist!")
        return False
    
    try:
        print("\nAttempting to process with Docling...")
        result = doc_converter.convert(str(docx_file))
        
        # Extract content
        markdown_content = result.document.export_to_markdown()
        json_content = result.document.export_to_dict()
        
        print(f"SUCCESS: Document processed successfully!")
        print(f"Content length: {len(markdown_content)} characters")
        print(f"Pages: {len(result.document.pages) if hasattr(result.document, 'pages') else 0}")
        print(f"First 200 characters of content:")
        print(repr(markdown_content[:200]))
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to process document")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception message: {str(e)}")
        print(f"Full exception details:")
        import traceback
        traceback.print_exc()
        return False

def test_glob_pattern():
    """Test if glob can find the file with special characters"""
    
    project_path = Path("input_docs/CFA009660")
    print(f"\nTesting glob patterns in: {project_path}")
    
    # Test different glob patterns
    patterns = ['*.docx', '*.DOCX', '*Anzaldo*.docx', '*ANEXO*.docx']
    
    for pattern in patterns:
        files = list(project_path.glob(pattern))
        print(f"Pattern '{pattern}': found {len(files)} files")
        for file in files:
            print(f"  - {file.name}")
            print(f"    Encoded name: {repr(file.name)}")

if __name__ == "__main__":
    print("=" * 60)
    print("DOCX Special Characters Processing Test")
    print("=" * 60)
    
    # Change to the correct directory
    os.chdir(Path(__file__).parent)
    
    # Test glob patterns first
    test_glob_pattern()
    
    print("\n" + "=" * 60)
    print("Testing Docling Processing")
    print("=" * 60)
    
    # Test processing
    success = test_docx_processing()
    
    print("\n" + "=" * 60)
    print(f"Test Result: {'SUCCESS' if success else 'FAILED'}")
    print("=" * 60)