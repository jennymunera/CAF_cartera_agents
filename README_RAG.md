# Sistema RAG Integrado con CrewAI

## 📋 Descripción General

Este proyecto implementa un sistema completo de **Retrieval-Augmented Generation (RAG)** integrado con agentes **CrewAI** para el procesamiento inteligente de documentos de proyectos. El sistema combina:

- **Azure Document Intelligence** para extracción de texto
- **Dense embeddings** para representación semántica
- **ChromaDB** para almacenamiento vectorial
- **Recuperación híbrida** con fusión RRF y re-ranking
- **Agentes CrewAI especializados** con capacidades RAG

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Documentos    │───▶│  Azure Document  │───▶│   Procesamiento │
│   (PDF, DOCX)   │    │   Intelligence   │    │   y Chunking    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Agentes CrewAI │◀───│   RAG Pipeline   │◀───│ Embeddings+Chroma│
│  con RAG Tool   │    │  (Híbrido + RRF) │    │   Vector Store  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Instalación y Configuración

### 1. Requisitos Previos

```bash
# Python 3.8+
python --version

# Variables de entorno requeridas
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=your_endpoint
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_key
OPENAI_API_KEY=your_openai_key  # Para los agentes CrewAI
```

### 2. Instalación de Dependencias

```bash
# Instalar dependencias RAG
pip install -r requirements_rag.txt

# O ejecutar el script de configuración automática
python setup_rag.py
```

### 3. Configuración Inicial

```bash
# Configurar el sistema RAG
python setup_rag.py

# Indexar documentos
python index_documents.py --path "ruta/a/documentos" --recursive

# Verificar instalación
python demo_rag_integration.py
```

## 📁 Estructura del Proyecto

```
├── rag/                          # Módulo RAG principal
│   ├── __init__.py              # Exportaciones principales
│   ├── config.py                # Configuración del sistema
│   ├── document_processor.py    # Procesamiento con Azure DI
│   ├── embeddings.py           # Gestión de embeddings densos
│   ├── vector_store.py         # Integración con ChromaDB
│   ├── retriever.py            # Recuperación híbrida + RRF
│   ├── rag_pipeline.py         # Pipeline principal
│   ├── observability.py        # Métricas y monitoreo
│   └── evaluation.py           # Sistema de evaluación
├── agents/
│   └── agents.py               # Agentes CrewAI con RAG
├── test/
│   ├── test_rag_system.py      # Tests del sistema RAG
│   └── test_crewai_rag_integration.py  # Tests integración
├── setup_rag.py                # Script de configuración
├── index_documents.py          # Script de indexación
├── demo_rag_integration.py     # Demostración completa
├── requirements_rag.txt        # Dependencias RAG
└── README_RAG.md              # Esta documentación
```

## 🔧 Componentes Principales

### 1. RAGConfig

Configuración centralizada del sistema:

```python
from rag import RAGConfig

# Cargar configuración
config = RAGConfig.from_json("rag_config.json")

# Configuración programática
config = RAGConfig(
    azure_endpoint="your_endpoint",
    azure_key="your_key",
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    vector_store_path="./chroma_db",
    chunk_size=512,
    chunk_overlap=50
)
```

### 2. RAGPipeline

Pipeline principal para indexación y consultas:

```python
from rag import RAGPipeline

# Inicializar pipeline
pipeline = RAGPipeline(config)

# Indexar documentos
pipeline.index_document("documento.pdf")

# Realizar consultas
results = pipeline.query(
    query="código CFA auditoría",
    top_k=5,
    use_reranking=True
)
```

### 3. Agentes CrewAI con RAG

Los agentes tienen acceso a la herramienta `rag_search`:

```python
from agents.agents import agente_auditorias, rag_tool
from crewai import Task, Crew

# Crear tarea que usa RAG
task = Task(
    description="Extrae códigos CFA usando rag_search",
    agent=agente_auditorias,
    expected_output="Códigos CFA encontrados"
)

# El agente puede usar: rag_search("código CFA")
```

## 📊 Uso del Sistema

### Indexación de Documentos

```bash
# Indexar un documento
python index_documents.py --file "documento.pdf"

# Indexar directorio completo
python index_documents.py --path "./documentos" --recursive

# Indexar con configuración específica
python index_documents.py --path "./docs" --batch-size 10 --clear-index
```

### Búsquedas RAG Directas

```python
from rag import RAGPipeline, RAGConfig

# Configurar pipeline
config = RAGConfig.from_json("rag_config.json")
pipeline = RAGPipeline(config)

# Búsqueda simple
results = pipeline.query("cronograma desembolsos")

# Búsqueda con filtros
results = pipeline.query(
    query="productos infraestructura",
    metadata_filter={"document_type": "ROP"},
    top_k=10
)

# Búsqueda híbrida con re-ranking
results = pipeline.query(
    query="concepto auditoría",
    use_reranking=True,
    rerank_top_k=20
)
```

### Integración con Agentes CrewAI

```python
from agents.agents import agente_auditorias
from crewai import Task, Crew

# Tarea con instrucciones RAG
task = Task(
    description="""
    Analiza el documento usando rag_search para encontrar:
    1. Códigos CFA y CFX
    2. Estados de auditoría
    3. Conceptos y opiniones
    
    Usa: rag_search("término de búsqueda")
    """,
    agent=agente_auditorias,
    expected_output="Análisis completo con extracciones"
)

crew = Crew(agents=[agente_auditorias], tasks=[task])
result = crew.kickoff()
```

## 🔍 Herramienta RAG para Agentes

Los agentes CrewAI tienen acceso a la herramienta `rag_search`:

### Sintaxis
```python
rag_search(
    query="término de búsqueda",
    document_types=["ROP", "INI", "DEC"],  # Opcional
    max_results=5  # Opcional
)
```

### Ejemplos de Uso en Agentes

```python
# Buscar códigos CFA
rag_search("código CFA operación")

# Buscar información específica de auditorías
rag_search("opinión dictamen auditoría", document_types=["IXP"])

# Buscar cronogramas de desembolsos
rag_search("cronograma desembolsos CAF", document_types=["ROP", "INI"])

# Buscar productos e indicadores
rag_search("productos metas indicadores", max_results=10)
```

## 📈 Monitoreo y Observabilidad

### Métricas del Sistema

```python
from rag import RAGObservability

# Inicializar observabilidad
obs = RAGObservability(config)

# Obtener métricas
metrics = obs.get_current_metrics()
print(f"Consultas totales: {metrics.query_metrics.total_queries}")
print(f"Tiempo promedio: {metrics.query_metrics.avg_response_time}ms")

# Exportar métricas
obs.export_metrics("metrics.json")
```

### Evaluación del Sistema

```python
from rag import RAGEvaluator

# Evaluar recuperación
evaluator = RAGEvaluator(pipeline)
results = evaluator.evaluate_retrieval(
    queries=["código CFA", "cronograma desembolsos"],
    ground_truth_docs=[["doc1.pdf"], ["doc2.pdf"]]
)

print(f"Precisión: {results.precision}")
print(f"Recall: {results.recall}")
```

## 🧪 Testing

### Ejecutar Tests

```bash
# Tests del sistema RAG
python -m pytest test/test_rag_system.py -v

# Tests de integración CrewAI
python -m pytest test/test_crewai_rag_integration.py -v

# Todos los tests
python -m pytest test/ -v
```

### Tests Específicos

```python
# Test de configuración
python -c "from rag import RAGConfig; print('Config OK')"

# Test de pipeline
python -c "from rag import RAGPipeline; print('Pipeline OK')"

# Test de agentes
python -c "from agents.agents import rag_tool; print('Agents OK')"
```

## 🚨 Solución de Problemas

### Problemas Comunes

1. **Error de Azure Document Intelligence**
   ```bash
   # Verificar credenciales
   echo $AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
   echo $AZURE_DOCUMENT_INTELLIGENCE_KEY
   ```

2. **ChromaDB no inicializada**
   ```bash
   # Reinicializar base de datos
   python setup_rag.py --reset-db
   ```

3. **Embeddings no disponibles**
   ```bash
   # Reinstalar dependencias
   pip install --upgrade FlagEmbedding torch
   ```

4. **Agentes sin acceso RAG**
   ```python
   # Verificar inicialización
   from agents.agents import rag_tool
   print(rag_tool.rag_pipeline is not None)
   ```

### Logs y Debugging

```python
# Habilitar logging detallado
import logging
logging.basicConfig(level=logging.DEBUG)

# Verificar salud del sistema
from rag import RAGPipeline
pipeline = RAGPipeline.from_config("rag_config.json")
health = pipeline.health_check()
print(health)
```

## 📚 Ejemplos Avanzados

### 1. Flujo Completo de Procesamiento

```python
from rag import RAGConfig, RAGPipeline
from agents.agents import (
    agente_auditorias, agente_productos, agente_desembolsos
)
from crewai import Crew, Task

# 1. Configurar RAG
config = RAGConfig.from_json("rag_config.json")
pipeline = RAGPipeline(config)

# 2. Indexar documentos
pipeline.index_directory("./documentos_proyecto")

# 3. Crear tareas especializadas
tasks = [
    Task(
        description="Extrae auditorías usando rag_search",
        agent=agente_auditorias,
        expected_output="Datos de auditorías"
    ),
    Task(
        description="Extrae productos usando rag_search",
        agent=agente_productos,
        expected_output="Datos de productos"
    ),
    Task(
        description="Extrae desembolsos usando rag_search",
        agent=agente_desembolsos,
        expected_output="Datos de desembolsos"
    )
]

# 4. Ejecutar crew
crew = Crew(
    agents=[agente_auditorias, agente_productos, agente_desembolsos],
    tasks=tasks
)

results = crew.kickoff()
```

### 2. Búsqueda Avanzada con Filtros

```python
# Búsqueda por tipo de documento
results = pipeline.query(
    query="cronograma desembolsos",
    metadata_filter={
        "document_type": {"$in": ["ROP", "INI"]},
        "page_number": {"$gte": 1, "$lte": 10}
    }
)

# Búsqueda con re-ranking
results = pipeline.query(
    query="concepto control interno",
    use_reranking=True,
    rerank_top_k=20,
    final_top_k=5
)
```

### 3. Evaluación Personalizada

```python
from rag import RAGEvaluator

# Crear evaluador
evaluator = RAGEvaluator(pipeline)

# Dataset de evaluación
eval_data = [
    {
        "query": "código CFA proyecto",
        "relevant_docs": ["ROP_proyecto.pdf"],
        "expected_answer": "CFA-001"
    }
]

# Evaluar sistema
results = evaluator.evaluate_end_to_end(eval_data)
print(f"Precisión E2E: {results.overall_score}")
```

## 🔄 Mantenimiento

### Actualización de Índices

```bash
# Actualizar documentos modificados
python index_documents.py --path "./docs" --update-only

# Reindexar completamente
python index_documents.py --path "./docs" --clear-index
```

### Backup y Restauración

```python
from rag import RAGPipeline

# Crear backup
pipeline = RAGPipeline.from_config("rag_config.json")
pipeline.backup_system("backup_20240101.zip")

# Restaurar backup
pipeline.restore_system("backup_20240101.zip")
```

## 📞 Soporte

Para problemas o preguntas:

1. Revisa los logs en `./logs/rag_system.log`
2. Ejecuta `python demo_rag_integration.py` para diagnósticos
3. Verifica la configuración con `python setup_rag.py --check`

## 🎯 Próximos Pasos

- [ ] Implementar cache de consultas frecuentes
- [ ] Agregar soporte para más formatos de documento
- [ ] Integrar con sistemas de monitoreo externos
- [ ] Optimizar rendimiento para grandes volúmenes
- [ ] Implementar fine-tuning de embeddings

---

**Sistema RAG + CrewAI** - Procesamiento Inteligente de Documentos de Proyectos