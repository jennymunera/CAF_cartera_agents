from typing import Dict, Any


def validate_corpus_chunk(record: Dict[str, Any]) -> bool:
    """
    Valida un registro de chunk del corpus.
    
    Args:
        record: Diccionario con los datos del chunk
        
    Returns:
        bool: True si es válido, False en caso contrario
        
    Raises:
        ValueError: Si el registro no cumple con el esquema esperado
    """
    required_fields = [
        'id_chunk',
        'proyecto', 
        'contenido',
        'tokens',
        'indice_chunk',
        'rango_secciones',
        'estrategia_chunking',
        'max_tokens_configurado',
        'overlap_tokens',
        'timestamp_procesamiento',
        'fuente',
        'version_esquema'
    ]
    
    # Verificar campos requeridos
    for field in required_fields:
        if field not in record:
            raise ValueError(f"Campo requerido faltante: {field}")
    
    # Validaciones específicas
    if not isinstance(record['tokens'], int) or record['tokens'] < 0:
        raise ValueError("El campo 'tokens' debe ser un entero positivo")
    
    if not isinstance(record['indice_chunk'], int) or record['indice_chunk'] < 0:
        raise ValueError("El campo 'indice_chunk' debe ser un entero positivo")
    
    if not isinstance(record['contenido'], str) or len(record['contenido'].strip()) == 0:
        raise ValueError("El campo 'contenido' debe ser una cadena no vacía")
    
    if not isinstance(record['proyecto'], str) or len(record['proyecto'].strip()) == 0:
        raise ValueError("El campo 'proyecto' debe ser una cadena no vacía")
    
    return True


def validate_document_metadata(record: Dict[str, Any]) -> bool:
    """
    Valida metadatos de documento.
    
    Args:
        record: Diccionario con metadatos del documento
        
    Returns:
        bool: True si es válido, False en caso contrario
    """
    required_fields = ['filename', 'file_size', 'processing_status']
    
    for field in required_fields:
        if field not in record:
            raise ValueError(f"Campo requerido faltante en metadatos: {field}")
    
    return True