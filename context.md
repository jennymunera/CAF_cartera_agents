# Context - Sistema de Análisis de Documentos con Agentes IA

## Resumen del Proyecto

Este proyecto implementa un sistema de análisis automatizado de documentos utilizando múltiples agentes de IA especializados. El sistema procesa documentos grandes mediante chunking inteligente y genera análisis detallados a través de agentes especializados en auditorías, productos y desembolsos.

## Arquitectura del Sistema

### Estructura de Carpetas
```
Agentes Jen/
├── main.py                    # Script principal
├── docling_processor.py       # Procesamiento de documentos
├── chunking_processor.py      # División en chunks
├── agents/
│   └── agents.py             # Definición de agentes
├── tasks/
│   └── task.py               # Definición de tareas
├── config/
│   └── settings.py           # Configuraciones
├── input_docs/               # Documentos de entrada
│   └── {project_name}/
└── output_docs/              # Documentos de salida
    └── {project_name}/
        ├── docs/             # Chunks y documentos procesados
        └── agents_output/    # JSONs individuales de agentes
```

### Flujo de Procesamiento

1. **Procesamiento Docling**: Extrae y convierte documentos a formato markdown
2. **Chunking Inteligente**: Divide documentos grandes en chunks de máximo 200,000 tokens
3. **Análisis por Agentes**: Cada chunk es procesado por:
   - Agentes Básicos: Auditorías, Productos, Desembolsos
   - Agentes Expertos: Versiones especializadas de cada agente básico
4. **Consolidación**: Agente concatenador unifica todos los resultados

## Modificaciones Implementadas

### ✅ Completadas

#### 1. Estructura de Carpetas Optimizada
- **Archivo**: `main.py` - función `create_project_folder_structure()`
- **Cambio**: Creación automática de subcarpetas `docs/` y `agents_output/` dentro de `output_docs/{project_name}/`
- **Propósito**: Organizar mejor las salidas del sistema

#### 2. Reubicación de Archivos de Documentos
- **Archivos**: `docling_processor.py`, `chunking_processor.py`
- **Cambio**: Todos los chunks, concatenados y metadata se guardan en `docs/`
- **Propósito**: Separar documentos procesados de salidas de agentes

#### 3. JSONs Individuales por Agente
- **Archivo**: `main.py` - función `run_analysis_on_chunk()`
- **Cambio**: Cada agente guarda su resultado como JSON individual en `agents_output/`
- **Formato**: `agente_{tipo}_chunk_{index}_output.json`
- **Estructura JSON**:
  ```json
  {
    "agent_name": "Nombre del Agente",
    "phase": "basic_analysis|expert_analysis|final_concatenation",
    "chunk_index": 0,
    "output": "Análisis completo...",
    "timestamp": "2025-08-31T19:40:02.880652"
  }
  ```

#### 4. Agente Concatenador con JSON
- **Archivo**: `main.py` - función `consolidate_chunk_results()`
- **Cambio**: El agente concatenador también guarda su resultado como JSON
- **Archivo**: `agente_concatenador_output.json`
- **Incluye**: Información sobre chunks procesados y timestamp

#### 5. Corrección de UnboundLocalError
- **Archivo**: `main.py` - función `run_full_analysis()`
- **Problema**: Variable `agents_output_dir` no definida en bloques de error
- **Solución**: Movida la definición al inicio de la función

#### 6. Optimización del Proceso de Chunking
- **Cambio**: El chunking se ejecuta inmediatamente después del procesamiento Docling
- **Beneficio**: Evita procesar todo el contenido concatenado, mejora eficiencia

### 🔄 Estado Actual del Sistema

#### Funcionando Correctamente:
- ✅ Estructura de carpetas automática
- ✅ Procesamiento por chunks (200,000 tokens máximo)
- ✅ Generación de JSONs individuales por agente y chunk
- ✅ Guardado en carpetas organizadas (`docs/` y `agents_output/`)
- ✅ Agentes básicos y expertos procesando correctamente

#### Verificado en Última Ejecución:
- ✅ 30 archivos JSON generados correctamente:
  - 15 archivos de agentes básicos (5 chunks × 3 agentes)
  - 15 archivos de agentes expertos (5 chunks × 3 agentes)
- ✅ Estructura JSON correcta con todos los campos requeridos
- ✅ Timestamps y metadatos incluidos

### ⚠️ Problemas Identificados

#### 1. Agente Concatenador Incompleto
- **Estado**: El proceso se interrumpe antes de completar la consolidación final
- **Síntoma**: Falta el archivo `agente_concatenador_output.json`
- **Causa**: Tareas de CrewAI se quedan en bucle infinito en la fase de consolidación
- **Impacto**: No se genera el análisis final unificado

#### 2. Ausencia de Archivos CSV
- **Estado**: No se generan archivos CSV como se esperaba
- **Ubicación esperada**: `docs/` junto con los archivos MD
- **Archivos actuales**: Solo se generan archivos `.md` y `.json`

### 📋 Tareas Pendientes

#### Alta Prioridad
1. **Resolver Bucle Infinito del Agente Concatenador**
   - Investigar por qué las tareas de CrewAI se quedan en "Executing Task..."
   - Posible timeout o configuración de agente concatenador
   - Verificar inputs del agente concatenador

2. **Implementar Generación de CSV**
   - Determinar qué datos deben exportarse a CSV
   - Agregar lógica de exportación CSV en el flujo de procesamiento
   - Ubicación: carpeta `docs/`

#### Media Prioridad
3. **Optimizar Rendimiento de Agentes**
   - Investigar por qué algunos agentes tardan mucho en procesar
   - Considerar timeouts y reintentos

4. **Mejorar Manejo de Errores**
   - Agregar más logging detallado
   - Implementar recuperación automática de fallos

### 🔧 Comandos de Ejecución

```bash
# Análisis completo con chunking automático
python main.py --full-analysis {PROJECT_NAME} --skip-processing

# Análisis básico sin chunking
python main.py --basic-analysis {PROJECT_NAME}
```

### 📁 Archivos de Salida Esperados

#### En `output_docs/{project_name}/docs/`:
- `{project}_chunk_XXX.md` - Chunks individuales
- `{project}_concatenated.md` - Documento completo
- `{project}_metadata.json` - Metadatos del procesamiento
- `{project}_chunking_metadata.json` - Información del chunking
- **PENDIENTE**: Archivos CSV con datos estructurados

#### En `output_docs/{project_name}/agents_output/`:
- `agente_auditorias_chunk_X_output.json`
- `agente_productos_chunk_X_output.json`
- `agente_desembolsos_chunk_X_output.json`
- `agente_experto_auditorias_chunk_X_output.json`
- `agente_experto_productos_chunk_X_output.json`
- `agente_experto_desembolsos_chunk_X_output.json`
- **PENDIENTE**: `agente_concatenador_output.json`

### 🚀 Próximos Pasos Recomendados

1. **Debugging del Agente Concatenador**:
   - Revisar configuración de timeout en CrewAI
   - Verificar inputs que se pasan al agente concatenador
   - Considerar dividir la tarea de consolidación en subtareas más pequeñas

2. **Implementación de CSV**:
   - Definir qué datos extraer (transacciones, auditorías, productos)
   - Crear función de exportación CSV
   - Integrar en el flujo de procesamiento

3. **Testing Completo**:
   - Ejecutar análisis completo hasta el final
   - Verificar que todos los archivos se generen correctamente
   - Validar calidad de los análisis generados

### 📊 Métricas del Sistema

- **Chunks procesados**: 5 (de un documento de ~1.96M tokens)
- **Agentes por chunk**: 6 (3 básicos + 3 expertos)
- **Total JSONs generados**: 30 (exitosos)
- **Tiempo de procesamiento**: ~2-3 minutos por chunk
- **Límite de tokens por chunk**: 200,000

---

**Última actualización**: 31 de agosto de 2025
**Estado del proyecto**: Funcional con tareas pendientes críticas
**Prioridad**: Resolver agente concatenador y generar CSVs