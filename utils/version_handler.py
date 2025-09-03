from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib
import json
from pathlib import Path

class VersionHandler:
    """Maneja la detección de versiones y generación de observaciones para documentos"""
    
    def __init__(self):
        self.document_versions = {}
        self.timestamp_format = "YYYY-MM-DD HH:MM:SS"
    
    def generate_document_hash(self, content: str, metadata: Dict) -> str:
        """Genera un hash único para el contenido del documento"""
        combined_content = f"{content}_{metadata.get('source_name', '')}_{metadata.get('page_no', '')}"
        return hashlib.md5(combined_content.encode()).hexdigest()
    
    def detect_version_change(self, document_id: str, content_hash: str, 
                            current_timestamp: str) -> Tuple[bool, Optional[str]]:
        """Detecta si hay cambios de versión en un documento
        
        Returns:
            Tuple[bool, Optional[str]]: (has_changed, previous_version_info)
        """
        if document_id not in self.document_versions:
            # Primera versión del documento
            self.document_versions[document_id] = {
                'hash': content_hash,
                'timestamp': current_timestamp,
                'version_count': 1
            }
            return False, None
        
        previous_info = self.document_versions[document_id]
        
        if previous_info['hash'] != content_hash:
            # Se detectó un cambio
            previous_version_info = f"Versión anterior: {previous_info['timestamp']} (v{previous_info['version_count']})"
            
            # Actualizar información de versión
            self.document_versions[document_id] = {
                'hash': content_hash,
                'timestamp': current_timestamp,
                'version_count': previous_info['version_count'] + 1,
                'previous_hash': previous_info['hash'],
                'previous_timestamp': previous_info['timestamp']
            }
            
            return True, previous_version_info
        
        return False, None
    
    def generate_observation(self, has_version_change: bool, previous_version_info: Optional[str],
                           processing_notes: List[str] = None, quality_issues: List[str] = None) -> str:
        """Genera el campo 'Observación' basado en cambios de versión y notas de procesamiento
        
        Args:
            has_version_change: Si se detectó un cambio de versión
            previous_version_info: Información de la versión anterior
            processing_notes: Notas adicionales de procesamiento
            quality_issues: Problemas de calidad detectados
        
        Returns:
            str: Texto para el campo 'Observación'
        """
        observations = []
        
        if has_version_change and previous_version_info:
            observations.append(f"CAMBIO DE VERSIÓN DETECTADO: {previous_version_info}")
        
        if processing_notes:
            for note in processing_notes:
                observations.append(f"PROCESAMIENTO: {note}")
        
        if quality_issues:
            for issue in quality_issues:
                observations.append(f"CALIDAD: {issue}")
        
        if not observations:
            return "Sin observaciones"
        
        return " | ".join(observations)
    
    def get_current_timestamp(self) -> str:
        """Obtiene el timestamp actual en el formato especificado"""
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")
    
    def validate_no_extraido_rule(self, field_value: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """Valida la regla 'NO EXTRAIDO' para campos faltantes
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, quality_note)
        """
        if not field_value or field_value.strip() == "":
            return False, f"Campo '{field_name}' vacío - se debe usar 'NO EXTRAIDO'"
        
        if field_value.strip().upper() == "NO EXTRAIDO":
            return True, f"Campo '{field_name}' correctamente marcado como NO EXTRAIDO"
        
        return True, None
    
    def apply_priority_rules(self, documents: List[Dict], priority_prefixes: List[str]) -> List[Dict]:
        """Aplica reglas de prioridad por prefijos (ej: ROP > INI > DEC > IFS)
        
        Args:
            documents: Lista de documentos con metadatos
            priority_prefixes: Lista de prefijos en orden de prioridad
        
        Returns:
            List[Dict]: Documentos ordenados por prioridad
        """
        def get_priority_score(doc):
            source_name = doc.get('source_name', '').upper()
            for i, prefix in enumerate(priority_prefixes):
                if source_name.startswith(prefix.upper()):
                    return i
            return len(priority_prefixes)  # Menor prioridad para documentos sin prefijo conocido
        
        return sorted(documents, key=get_priority_score)
    
    def extract_traceability_fields(self, chunk_data: Dict) -> Dict[str, str]:
        """Extrae campos de trazabilidad estándar de un chunk
        
        Returns:
            Dict con campos: 'Nombre del archivo revisado', 'Página', 'Sección'
        """
        return {
            "Nombre del archivo revisado": chunk_data.get('source_name', 'NO EXTRAIDO'),
            "Página": str(chunk_data.get('page_no', 'NO EXTRAIDO')),
            "Sección": chunk_data.get('section', 'NO EXTRAIDO')
        }
    
    def validate_section_constraints(self, section: str, valid_sections: List[str]) -> bool:
        """Valida si una sección está en la lista de secciones válidas
        
        Args:
            section: Sección a validar
            valid_sections: Lista de secciones válidas
        
        Returns:
            bool: True si la sección es válida
        """
        if not section or section == 'NO EXTRAIDO':
            return False
        
        section_lower = section.lower().strip()
        valid_sections_lower = [s.lower().strip() for s in valid_sections]
        
        return section_lower in valid_sections_lower
    
    def calculate_delay(self, fecha_programada: str, fecha_real: str) -> str:
        """Calcula si hay retraso comparando fechas programadas vs reales
        
        Returns:
            str: 'Sí', 'No', o 'NO EXTRAIDO'
        """
        try:
            if not fecha_programada or not fecha_real:
                return 'NO EXTRAIDO'
            
            if fecha_programada == 'NO EXTRAIDO' or fecha_real == 'NO EXTRAIDO':
                return 'NO EXTRAIDO'
            
            # Intentar parsear las fechas (formato flexible)
            from dateutil import parser
            fecha_prog_dt = parser.parse(fecha_programada)
            fecha_real_dt = parser.parse(fecha_real)
            
            return 'Sí' if fecha_real_dt > fecha_prog_dt else 'No'
            
        except Exception:
            return 'NO EXTRAIDO'
    
    def normalize_numeric_meta(self, meta_text: str) -> Tuple[Optional[float], str]:
        """Separa valor numérico de unidad en campo 'meta'
        
        Returns:
            Tuple[Optional[float], str]: (valor_numerico, unidad_texto)
        """
        if not meta_text or meta_text.strip().upper() == 'NO EXTRAIDO':
            return None, 'NO EXTRAIDO'
        
        import re
        
        # Buscar patrones numéricos
        numeric_pattern = r'([0-9]+(?:\.[0-9]+)?)'
        matches = re.findall(numeric_pattern, meta_text)
        
        if matches:
            try:
                numeric_value = float(matches[0])
                # Extraer la parte no numérica como unidad
                unit_text = re.sub(numeric_pattern, '', meta_text).strip()
                return numeric_value, unit_text if unit_text else 'unidad'
            except ValueError:
                pass
        
        return None, meta_text

# Instancia global del manejador de versiones
version_handler = VersionHandler()