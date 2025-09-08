# Context.md - Guía de Desarrollo para Agentes

## 📋 Estado Actual del Proyecto

**Fecha de última actualización**: Enero 2025  
**Commit actual**: `0bbb549` - Reestructuración completa: código compartido centralizado y README actualizado  
**Rama activa**: `agents_simple_azure_v1`

### ✅ Tareas Completadas Recientemente

1. **Reestructuración de Código Compartido**
   - Creada estructura `azure_functions/shared_code/` centralizada
   - Migrados todos los procesadores, utilidades y esquemas
   - Actualizadas importaciones en Azure Functions
   - Limpiadas carpetas de funciones (solo `function.json` e `__init__.py`)

2. **Documentación Actualizada**
   - README.md completamente actualizado con documentación precisa
   - Corregidas descripciones de scripts de diagnóstico
   - Expandida documentación del directorio `local/`

3. **Validación y Pruebas**
   - Verificadas todas las importaciones funcionan correctamente
   - Probadas las funciones reestructuradas
   - Confirmada funcionalidad completa del sistema

## 🏗️ Arquitectura del Sistema

### Componentes Principales

```
Agentes_jen_rebuild/
├── azure_functions/          # Azure Functions (producción)
│   ├── shared_code/          # 🆕 Código compartido centralizado
│   │   ├── processors/       # Procesadores de negocio
│   │   ├── utils/           # Utilidades comunes
│   │   └── schemas/         # Esquemas de validación
│   ├── OpenAiProcess/       # Function: procesamiento de documentos
│   ├── PoolingProcess/      # Function: monitoreo de batches
│   └── tests/              # Scripts de diagnóstico y pruebas
└── local/                  # Entorno de desarrollo local
    ├── processors/         # Versiones locales de procesadores
    ├── utils/             # Utilidades para desarrollo
    └── tests/             # Pruebas locales
```

### Flujo de Procesamiento

1. **Ingesta**: Documentos → Azure Blob Storage (`basedocuments/{proyecto}/raw`)
2. **Trigger**: Service Bus Message → OpenAiProcess
3. **Procesamiento**: Document Intelligence → Chunking → OpenAI Batch
4. **Monitoreo**: PoolingProcess (Timer, cada 5 min) → verifica batches
5. **Resultados**: Procesamiento completo → `basedocuments/{proyecto}/results`

## 🔧 Configuración Técnica

### Variables de Entorno Requeridas

```bash
# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...
AZURE_DOCUMENT_INTELLIGENCE_KEY=...

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://oai-poc-idatafactory-cr.openai.azure.com/
AZURE_OPENAI_API_VERSION=2025-04-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-2

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_STORAGE_CONTAINER_NAME=caf-documents

# Logging
APPLICATIONINSIGHTS_CONNECTION_STRING=...
```

### Estructura de Datos en Blob Storage

```
caf-documents/
└── basedocuments/
    └── {proyecto}/
        ├── raw/                    # Documentos originales
        ├── processed/
        │   ├── DI/                # Salidas Document Intelligence
        │   ├── chunks/            # Chunks procesados
        │   └── openai_logs/       # Metadatos de batches
        └── results/               # Resultados finales
```

## 🎯 Reglas de Negocio Importantes

### Filtrado por Prefijos de Documentos

```python
# Prefijos permitidos por tipo de prompt
AUDIT_PREFIXES = ['AUD', 'AUDIT', 'REV']
DISBURSEMENT_PREFIXES = ['DIS', 'DESEM', 'PAY']
PRODUCT_PREFIXES = ['PROD', 'PRODUCT', 'SERV']
```

### Prompts Disponibles

1. **Auditoría** (`prompt Auditoria.txt`): Análisis de documentos de auditoría
2. **Desembolsos** (`prompt Desembolsos.txt`): Procesamiento de pagos
3. **Productos** (`prompt Productos.txt`): Análisis de productos/servicios

## 🛠️ Herramientas de Desarrollo

### Scripts de Diagnóstico (`azure_functions/tests/`)

- `diagnose_openai_variables.py`: Diagnóstica configuración OpenAI
- `check_blob_content.py`: Verifica contenido en Blob Storage
- `check_documents.py`: Analiza documentos vs prefijos permitidos
- `configure_azure_variables.sh`: Configura variables de entorno
- `send_test_message_simple.py`: Envía mensajes de prueba
- `download_batch_info.py`: Descarga información de batches

### Entorno Local (`local/`)

- `process_and_submit_batch.py`: Script principal para procesamiento local
- `results.py`: Monitoreo de batches desde entorno local
- Procesadores locales para desarrollo y debugging

## 🚀 Próximos Pasos Sugeridos

### Prioridad Alta

1. **Optimización de Performance**
   - Implementar paralelización en chunking_processor
   - Optimizar tamaño de chunks para mejor rendimiento
   - Añadir cache para Document Intelligence

2. **Monitoreo y Observabilidad**
   - Implementar métricas detalladas en Application Insights
   - Añadir alertas para fallos de batches
   - Dashboard de monitoreo en tiempo real

3. **Manejo de Errores**
   - Implementar retry logic robusto
   - Manejo de documentos corruptos
   - Dead letter queue para mensajes fallidos

### Prioridad Media

4. **Escalabilidad**
   - Implementar particionamiento de batches grandes
   - Optimizar uso de tokens OpenAI
   - Implementar throttling inteligente

5. **Seguridad**
   - Implementar rotación automática de keys
   - Añadir validación de entrada más robusta
   - Audit trail completo

6. **Testing**
   - Suite de tests automatizados
   - Tests de integración end-to-end
   - Tests de carga y performance

### Prioridad Baja

7. **Funcionalidades Adicionales**
   - Soporte para más tipos de documentos
   - API REST para consulta de resultados
   - Interface web para administración

## 🔍 Puntos de Atención

### Limitaciones Conocidas

1. **OpenAI Batch API**
   - Límite de 24h para completar batches
   - Máximo 50,000 requests por batch
   - Rate limits específicos por deployment

2. **Document Intelligence**
   - Límites de tamaño de archivo (500MB)
   - Tipos de archivo soportados limitados
   - Latencia variable según carga

3. **Azure Functions**
   - Timeout máximo de 10 minutos
   - Límites de memoria y CPU
   - Cold start en consumo

### Consideraciones de Desarrollo

1. **Importaciones**: Siempre usar `shared_code/` para código compartido
2. **Logging**: Usar `get_logger()` de `shared_code.utils.app_insights_logger`
3. **Configuración**: Variables de entorno centralizadas en `.env.example`
4. **Testing**: Usar scripts en `tests/` antes de desplegar

## 📚 Recursos Adicionales

- **README.md**: Documentación completa del proyecto
- **Prompts**: Archivos `.txt` con instrucciones para OpenAI
- **Schemas**: Definiciones de estructura en `shared_code/schemas/`
- **Logs**: Application Insights para monitoreo en tiempo real

## 🤝 Convenciones de Desarrollo

### Git Workflow

1. Trabajar en rama `agents_simple_azure_v1`
2. Commits descriptivos con scope claro
3. Push frecuente para backup
4. Tags para releases importantes

### Código

1. **Python**: PEP 8, type hints, docstrings
2. **Logging**: Niveles apropiados (DEBUG, INFO, WARNING, ERROR)
3. **Error Handling**: Try-catch específicos, no genéricos
4. **Testing**: Validar cambios con scripts de diagnóstico

### Despliegue

1. Usar `deploy_functions.sh` para despliegues completos
2. Validar variables de entorno antes de desplegar
3. Monitorear logs post-despliegue
4. Rollback plan siempre disponible

---

**Nota**: Este documento debe actualizarse con cada cambio significativo en la arquitectura o funcionalidad del sistema.