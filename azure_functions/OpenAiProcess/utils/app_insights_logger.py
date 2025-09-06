#!/usr/bin/env python3
"""
Módulo de logging centralizado compatible con Azure Application Insights.

Este módulo proporciona un sistema de logging estructurado que genera archivos
de logs en formato JSON, optimizado para su integración con Azure Application Insights.

Características:
- Logs estructurados en formato JSON
- Múltiples niveles de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Rotación automática de archivos de log
- Metadatos contextuales para cada evento
- Compatible con Azure Application Insights
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path


class AppInsightsFormatter(logging.Formatter):
    """
    Formateador personalizado para generar logs en formato JSON
    compatible con Azure Application Insights.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Formatea el registro de log como JSON estructurado.
        
        Args:
            record: Registro de logging a formatear
            
        Returns:
            str: Log formateado como JSON
        """
        # Crear timestamp en formato ISO 8601 con timezone UTC
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        
        # Estructura base del log
        log_entry = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread
        }
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Agregar campos personalizados si existen
        if hasattr(record, 'custom_fields'):
            log_entry["custom_fields"] = record.custom_fields
        
        # Agregar información de operación si existe
        if hasattr(record, 'operation_id'):
            log_entry["operation_id"] = record.operation_id
        
        if hasattr(record, 'operation_name'):
            log_entry["operation_name"] = record.operation_name
        
        # Agregar información de usuario/sesión si existe
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, 'session_id'):
            log_entry["session_id"] = record.session_id
        
        return json.dumps(log_entry, ensure_ascii=False)


class AppInsightsLogger:
    """
    Logger centralizado para Azure Application Insights.
    
    Proporciona métodos para logging estructurado con metadatos
    contextuales y rotación automática de archivos.
    """
    
    def __init__(self, 
                 name: str,
                 log_dir: str = "logs",
                 log_level: str = "INFO",
                 max_bytes: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5):
        """
        Inicializa el logger de Application Insights.
        
        Args:
            name: Nombre del logger
            log_dir: Directorio donde guardar los logs
            log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_bytes: Tamaño máximo del archivo de log antes de rotar
            backup_count: Número de archivos de backup a mantener
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Crear logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Evitar duplicar handlers si ya existen
        if not self.logger.handlers:
            self._setup_handlers(max_bytes, backup_count)
    
    def _setup_handlers(self, max_bytes: int, backup_count: int):
        """
        Configura los handlers de logging.
        
        Args:
            max_bytes: Tamaño máximo del archivo antes de rotar
            backup_count: Número de archivos de backup
        """
        # Handler para archivo con rotación
        log_file = self.log_dir / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(AppInsightsFormatter())
        
        # Handler para consola (opcional, para desarrollo)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(AppInsightsFormatter())
        
        # Agregar handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_operation_start(self, 
                           operation_name: str, 
                           operation_id: str,
                           **kwargs) -> None:
        """
        Registra el inicio de una operación.
        
        Args:
            operation_name: Nombre de la operación
            operation_id: ID único de la operación
            **kwargs: Campos personalizados adicionales
        """
        extra = {
            'operation_name': operation_name,
            'operation_id': operation_id,
            'custom_fields': {
                'event_type': 'operation_start',
                **kwargs
            }
        }
        self.logger.info(f"🚀 Iniciando operación: {operation_name}", extra=extra)
    
    def log_operation_end(self, 
                         operation_name: str, 
                         operation_id: str,
                         success: bool = True,
                         duration_ms: Optional[float] = None,
                         **kwargs) -> None:
        """
        Registra el fin de una operación.
        
        Args:
            operation_name: Nombre de la operación
            operation_id: ID único de la operación
            success: Si la operación fue exitosa
            duration_ms: Duración en milisegundos
            **kwargs: Campos personalizados adicionales
        """
        extra = {
            'operation_name': operation_name,
            'operation_id': operation_id,
            'custom_fields': {
                'event_type': 'operation_end',
                'success': success,
                'duration_ms': duration_ms,
                **kwargs
            }
        }
        
        status = "✅ completada" if success else "❌ falló"
        message = f"Operación {operation_name} {status}"
        if duration_ms:
            message += f" (duración: {duration_ms:.2f}ms)"
        
        if success:
            self.logger.info(message, extra=extra)
        else:
            self.logger.error(message, extra=extra)
    
    def log_document_processing(self, 
                               document_name: str,
                               operation_id: str,
                               stage: str,
                               **kwargs) -> None:
        """
        Registra eventos de procesamiento de documentos.
        
        Args:
            document_name: Nombre del documento
            operation_id: ID de la operación
            stage: Etapa del procesamiento
            **kwargs: Campos personalizados adicionales
        """
        extra = {
            'operation_id': operation_id,
            'custom_fields': {
                'event_type': 'document_processing',
                'document_name': document_name,
                'processing_stage': stage,
                **kwargs
            }
        }
        self.logger.info(f"📄 Procesando documento {document_name} - {stage}", extra=extra)
    
    def log_batch_operation(self, 
                           batch_id: str,
                           operation_id: str,
                           status: str,
                           **kwargs) -> None:
        """
        Registra eventos de operaciones batch.
        
        Args:
            batch_id: ID del batch job
            operation_id: ID de la operación
            status: Estado del batch
            **kwargs: Campos personalizados adicionales
        """
        extra = {
            'operation_id': operation_id,
            'custom_fields': {
                'event_type': 'batch_operation',
                'batch_id': batch_id,
                'batch_status': status,
                **kwargs
            }
        }
        self.logger.info(f"🔄 Batch {batch_id} - Estado: {status}", extra=extra)
    
    def log_error(self, 
                  message: str,
                  operation_id: Optional[str] = None,
                  error_code: Optional[str] = None,
                  **kwargs) -> None:
        """
        Registra errores con contexto adicional.
        
        Args:
            message: Mensaje de error
            operation_id: ID de la operación (opcional)
            error_code: Código de error (opcional)
            **kwargs: Campos personalizados adicionales
        """
        extra = {
            'custom_fields': {
                'event_type': 'error',
                'error_code': error_code,
                **kwargs
            }
        }
        
        if operation_id:
            extra['operation_id'] = operation_id
        
        self.logger.error(f"❌ {message}", extra=extra)
    
    def log_metric(self, 
                   metric_name: str,
                   value: float,
                   operation_id: Optional[str] = None,
                   **kwargs) -> None:
        """
        Registra métricas personalizadas.
        
        Args:
            metric_name: Nombre de la métrica
            value: Valor de la métrica
            operation_id: ID de la operación (opcional)
            **kwargs: Campos personalizados adicionales
        """
        extra = {
            'custom_fields': {
                'event_type': 'metric',
                'metric_name': metric_name,
                'metric_value': value,
                **kwargs
            }
        }
        
        if operation_id:
            extra['operation_id'] = operation_id
        
        self.logger.info(f"📊 Métrica {metric_name}: {value}", extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log de debug con campos personalizados."""
        extra = {'custom_fields': kwargs} if kwargs else {}
        self.logger.debug(message, extra=extra)
    
    def info(self, message: str, **kwargs):
        """Log de info con campos personalizados."""
        extra = {'custom_fields': kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log de warning con campos personalizados."""
        extra = {'custom_fields': kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """Log de error con campos personalizados."""
        extra = {'custom_fields': kwargs} if kwargs else {}
        self.logger.error(message, extra=extra)
    
    def critical(self, message: str, **kwargs):
        """Log crítico con campos personalizados."""
        extra = {'custom_fields': kwargs} if kwargs else {}
        self.logger.critical(message, extra=extra)


def get_logger(name: str, **kwargs) -> AppInsightsLogger:
    """
    Factory function para crear loggers de Application Insights.
    
    Args:
        name: Nombre del logger
        **kwargs: Argumentos adicionales para AppInsightsLogger
        
    Returns:
        AppInsightsLogger: Instancia del logger configurado
    """
    return AppInsightsLogger(name, **kwargs)


def generate_operation_id() -> str:
    """
    Genera un ID único para operaciones.
    
    Returns:
        str: ID único basado en timestamp y UUID
    """
    import uuid
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}"