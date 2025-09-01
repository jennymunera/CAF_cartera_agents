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

class DocumentIntelligenceProcessor:
    def __init__(self, endpoint: str, api_key: str, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
    
    def process_document(self, file_path: str, model_id: str = "prebuilt-layout") -> Dict[str, Any]:
        start_time = time.time()
        file_path = Path(file_path)
        
        try:
            # Leer archivo
            with open(file_path, 'rb') as f:
                document_bytes = f.read()
            
            # Analizar documento - usando el enfoque recomendado para v4.0
            # Para archivos .docx, no especificamos content_type para que se detecte automáticamente
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
            
            # Extraer información
            extracted_data = {
                'processor': 'document_intelligence',
                'model_id': model_id,
                'file_name': file_path.name,
                'file_path': str(file_path),
                'processing_time': time.time() - start_time,
                'timestamp': datetime.now().isoformat(),
                'success': True,
                'error': None,
                'content': {
                    'text': self._extract_text(result),
                    'tables': self._extract_tables(result),
                    'images': self._extract_images(result),
                    'key_value_pairs': self._extract_key_value_pairs(result),
                    'paragraphs': self._extract_paragraphs(result)
                },
                'statistics': {
                    'total_pages': len(result.pages) if result.pages else 0,
                    'total_tables': len(result.tables) if result.tables else 0,
                    'total_paragraphs': len(result.paragraphs) if result.paragraphs else 0,
                    'total_key_value_pairs': len(result.key_value_pairs) if result.key_value_pairs else 0,
                    'confidence_score': self._calculate_average_confidence(result)
                }
            }
            
        except HttpResponseError as e:
            extracted_data = {
                'processor': 'document_intelligence',
                'model_id': model_id,
                'file_name': file_path.name,
                'file_path': str(file_path),
                'processing_time': time.time() - start_time,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'error': f"HTTP Error: {e.status_code} - {e.message}",
                'content': None,
                'statistics': None
            }
        except Exception as e:
            extracted_data = {
                'processor': 'document_intelligence',
                'model_id': model_id,
                'file_name': file_path.name,
                'file_path': str(file_path),
                'processing_time': time.time() - start_time,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'error': str(e),
                'content': None,
                'statistics': None
            }
        
        # Guardar resultado
        self._save_result(extracted_data)
        return extracted_data
    
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
            image_data = {
                'figure_id': i,
                'caption': getattr(figure, 'caption', ''),
                'bounding_regions': [],
                'confidence': getattr(figure, 'confidence', None)
            }
            
            if hasattr(figure, 'bounding_regions') and figure.bounding_regions:
                for region in figure.bounding_regions:
                    region_data = {
                        'page_number': region.page_number,
                        'polygon': [{'x': point.x, 'y': point.y} for point in region.polygon] if region.polygon else []
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
    
    def _save_result(self, data: Dict[str, Any]):
        filename = f"document_intelligence_{data['file_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Resultado guardado en: {output_path}")
    
    def process_multiple_documents(self, file_paths: List[str], model_id: str = "prebuilt-layout") -> List[Dict[str, Any]]:
        results = []
        for file_path in file_paths:
            print(f"Procesando con Document Intelligence: {file_path}")
            result = self.process_document(file_path, model_id)
            results.append(result)
        
        return results