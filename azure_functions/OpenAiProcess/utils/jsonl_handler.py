import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

# Configure logging
logger = logging.getLogger(__name__)


class JSONLHandler:
    """Manejador para archivos JSONL (JSON Lines)."""
    
    def __init__(self):
        pass
    
    def write_jsonl(self, records: List[Dict[str, Any]], file_path: str, validate_func: Optional[Callable] = None) -> bool:
        """
        Escribe registros a un archivo JSONL.
        
        Args:
            records: Lista de diccionarios a escribir
            file_path: Ruta del archivo JSONL
            validate_func: Función opcional de validación
            
        Returns:
            bool: True si se escribió exitosamente, False en caso contrario
        """
        try:
            # Crear directorio padre si no existe
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for record in records:
                    # Validar registro si se proporciona función de validación
                    if validate_func:
                        try:
                            validate_func(record)
                        except Exception as e:
                            logger.error(f"Validation error in record: {e}")
                            return False
                    
                    # Escribir registro como línea JSON
                    json.dump(record, f, ensure_ascii=False)
                    f.write('\n')
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing JSONL file {file_path}: {e}")
            return False
    
    def read_jsonl(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Lee registros de un archivo JSONL.
        
        Args:
            file_path: Ruta del archivo JSONL
            
        Returns:
            List[Dict]: Lista de registros leídos
        """
        records = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            return records
            
        except Exception as e:
            logger.error(f"Error reading JSONL file {file_path}: {e}")
            return []