import json
import os
from typing import List, Dict, Any, Optional, Iterator
from pathlib import Path
from datetime import datetime

class JSONLHandler:
    """Maneja la lectura y escritura de archivos JSONL intermedios"""
    
    def __init__(self):
        self.encoding = 'utf-8'
    
    def write_jsonl(self, data: List[Dict[Any, Any]], file_path: str, 
                   append: bool = False, validate_func: Optional[callable] = None) -> bool:
        """Escribe datos a un archivo JSONL
        
        Args:
            data: Lista de diccionarios a escribir
            file_path: Ruta del archivo JSONL
            append: Si True, agrega al archivo existente
            validate_func: Función opcional para validar cada registro
        
        Returns:
            bool: True si la escritura fue exitosa
        """
        try:
            # Crear directorio si no existe
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            
            with open(file_path, mode, encoding=self.encoding) as f:
                for record in data:
                    # Validar registro si se proporciona función
                    if validate_func:
                        try:
                            validate_func(record)
                        except Exception as e:
                            print(f"Validación fallida para registro: {e}")
                            continue
                    
                    # Agregar timestamp si no existe
                    if 'timestamp_procesamiento' not in record:
                        record['timestamp_procesamiento'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    json_line = json.dumps(record, ensure_ascii=False)
                    f.write(json_line + '\n')
            
            return True
            
        except Exception as e:
            print(f"Error escribiendo archivo JSONL {file_path}: {e}")
            return False
    
    def read_jsonl(self, file_path: str, validate_func: Optional[callable] = None) -> List[Dict[Any, Any]]:
        """Lee datos desde un archivo JSONL
        
        Args:
            file_path: Ruta del archivo JSONL
            validate_func: Función opcional para validar cada registro
        
        Returns:
            List[Dict]: Lista de registros leídos
        """
        data = []
        
        if not os.path.exists(file_path):
            print(f"Archivo JSONL no encontrado: {file_path}")
            return data
        
        try:
            with open(file_path, 'r', encoding=self.encoding) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                        
                        # Validar registro si se proporciona función
                        if validate_func:
                            try:
                                validate_func(record)
                            except Exception as e:
                                print(f"Validación fallida en línea {line_num}: {e}")
                                continue
                        
                        data.append(record)
                        
                    except json.JSONDecodeError as e:
                        print(f"Error JSON en línea {line_num}: {e}")
                        continue
            
        except Exception as e:
            print(f"Error leyendo archivo JSONL {file_path}: {e}")
        
        return data
    
    def stream_jsonl(self, file_path: str, validate_func: Optional[callable] = None) -> Iterator[Dict[Any, Any]]:
        """Lee archivo JSONL de forma streaming (para archivos grandes)
        
        Args:
            file_path: Ruta del archivo JSONL
            validate_func: Función opcional para validar cada registro
        
        Yields:
            Dict: Cada registro del archivo
        """
        if not os.path.exists(file_path):
            print(f"Archivo JSONL no encontrado: {file_path}")
            return
        
        try:
            with open(file_path, 'r', encoding=self.encoding) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                        
                        # Validar registro si se proporciona función
                        if validate_func:
                            try:
                                validate_func(record)
                            except Exception as e:
                                print(f"Validación fallida en línea {line_num}: {e}")
                                continue
                        
                        yield record
                        
                    except json.JSONDecodeError as e:
                        print(f"Error JSON en línea {line_num}: {e}")
                        continue
            
        except Exception as e:
            print(f"Error leyendo archivo JSONL {file_path}: {e}")
    
    def append_record(self, record: Dict[Any, Any], file_path: str, 
                     validate_func: Optional[callable] = None) -> bool:
        """Agrega un solo registro a un archivo JSONL
        
        Args:
            record: Diccionario a agregar
            file_path: Ruta del archivo JSONL
            validate_func: Función opcional para validar el registro
        
        Returns:
            bool: True si la escritura fue exitosa
        """
        return self.write_jsonl([record], file_path, append=True, validate_func=validate_func)
    
    def count_records(self, file_path: str) -> int:
        """Cuenta el número de registros en un archivo JSONL
        
        Args:
            file_path: Ruta del archivo JSONL
        
        Returns:
            int: Número de registros
        """
        if not os.path.exists(file_path):
            return 0
        
        count = 0
        try:
            with open(file_path, 'r', encoding=self.encoding) as f:
                for line in f:
                    if line.strip():
                        count += 1
        except Exception as e:
            print(f"Error contando registros en {file_path}: {e}")
        
        return count
    
    def filter_jsonl(self, input_path: str, output_path: str, 
                    filter_func: callable, validate_func: Optional[callable] = None) -> int:
        """Filtra registros de un archivo JSONL y escribe a otro
        
        Args:
            input_path: Ruta del archivo JSONL de entrada
            output_path: Ruta del archivo JSONL de salida
            filter_func: Función que retorna True para registros a mantener
            validate_func: Función opcional para validar registros
        
        Returns:
            int: Número de registros filtrados
        """
        filtered_count = 0
        
        try:
            # Crear directorio de salida si no existe
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding=self.encoding) as out_f:
                for record in self.stream_jsonl(input_path, validate_func):
                    if filter_func(record):
                        json_line = json.dumps(record, ensure_ascii=False)
                        out_f.write(json_line + '\n')
                        filtered_count += 1
        
        except Exception as e:
            print(f"Error filtrando archivo JSONL: {e}")
        
        return filtered_count
    
    def merge_jsonl_files(self, input_paths: List[str], output_path: str, 
                         validate_func: Optional[callable] = None) -> int:
        """Combina múltiples archivos JSONL en uno solo
        
        Args:
            input_paths: Lista de rutas de archivos JSONL de entrada
            output_path: Ruta del archivo JSONL de salida
            validate_func: Función opcional para validar registros
        
        Returns:
            int: Número total de registros combinados
        """
        total_records = 0
        
        try:
            # Crear directorio de salida si no existe
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding=self.encoding) as out_f:
                for input_path in input_paths:
                    if not os.path.exists(input_path):
                        print(f"Archivo no encontrado: {input_path}")
                        continue
                    
                    for record in self.stream_jsonl(input_path, validate_func):
                        json_line = json.dumps(record, ensure_ascii=False)
                        out_f.write(json_line + '\n')
                        total_records += 1
        
        except Exception as e:
            print(f"Error combinando archivos JSONL: {e}")
        
        return total_records
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Obtiene información sobre un archivo JSONL
        
        Args:
            file_path: Ruta del archivo JSONL
        
        Returns:
            Dict: Información del archivo (tamaño, registros, etc.)
        """
        info = {
            'exists': False,
            'size_bytes': 0,
            'record_count': 0,
            'created_time': None,
            'modified_time': None
        }
        
        if os.path.exists(file_path):
            info['exists'] = True
            stat = os.stat(file_path)
            info['size_bytes'] = stat.st_size
            info['record_count'] = self.count_records(file_path)
            info['created_time'] = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            info['modified_time'] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        return info

# Instancia global del manejador JSONL
jsonl_handler = JSONLHandler()