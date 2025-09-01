from crewai import Task
from agents.agents import (
    agente_auditorias,
    agente_productos,
    agente_desembolsos,
    agente_experto_auditorias,
    agente_experto_productos,
    agente_experto_desembolsos,
    agente_concatenador
)

# Tarea para Agente de Auditorías
task_auditorias = Task(
    description="""
    Analizar los documentos procesados para extraer información relacionada con auditorías con prioridad IXP.
    
    Debes:
    1. Revisar todos los documentos procesados de Docling
    2. Priorizar documentos IXP para análisis de auditoría
    3. Extraer variables y datos clave de auditoría
    4. Detectar versiones y cambios de documentos
    5. Identificar la fuente y origen de cada punto de datos
    
    Entrada: {processed_documents}
    
    Enfócate en extraer información específica de auditoría manteniendo la trazabilidad de datos.
    """,
    expected_output="""
    Una salida JSON estructurada que contenga:
    - Variables de auditoría extraídas
    - Fuente y origen del documento para cada punto de datos
    - Resultados de detección de versiones
    - Observaciones de procesamiento
    - Evaluación de calidad de datos
    """,
    agent=agente_auditorias
)

# Tarea para Agente de Productos
task_productos = Task(
    description="""
    Analizar los documentos procesados para extraer información relacionada con productos con prioridad ROP>INI>DEC>IFS.
    
    Debes:
    1. Revisar todos los documentos procesados de Docling
    2. Aplicar orden de prioridad: ROP > INI > DEC > IFS
    3. Extraer variables y datos específicos de productos
    4. Detectar versiones y cambios de documentos
    5. Identificar la fuente y origen de cada punto de datos
    
    Entrada: {processed_documents}
    
    Enfócate en información de productos respetando la jerarquía de prioridad establecida.
    """,
    expected_output="""
    Una salida JSON estructurada que contenga:
    - Variables de productos extraídas
    - Fuente y origen del documento para cada punto de datos
    - Resultados de procesamiento basado en prioridades
    - Resultados de detección de versiones
    - Observaciones de procesamiento
    """,
    agent=agente_productos
)

# Tarea para Agente de Desembolsos
task_desembolsos = Task(
    description="""
    Analizar los documentos procesados para extraer información relacionada con desembolsos con prioridad ROP>INI>DEC.
    
    Debes:
    1. Revisar todos los documentos procesados de Docling
    2. Aplicar orden de prioridad: ROP > INI > DEC
    3. Extraer variables específicas de desembolsos (códigos CFX, montos CAF, fechas)
    4. Detectar versiones y cambios de documentos
    5. Identificar la fuente y origen de cada punto de datos
    
    Entrada: {processed_documents}
    
    Enfócate en datos financieros de desembolsos con manejo adecuado de prioridades.
    """,
    expected_output="""
    Una salida JSON estructurada que contenga:
    - Códigos de operación (CFX)
    - Fechas de desembolso (CAF)
    - Montos CAF y conversiones USD
    - Fuentes CAF
    - Fuente y origen del documento para cada punto de datos
    - Resultados de detección de versiones
    - Observaciones de procesamiento
    """,
    agent=agente_desembolsos
)

# Tarea para Agente Experto en Auditorías
task_experto_auditorias = Task(
    description="""
    Revisar los resultados del análisis de auditorías y asignar una clasificación de concepto final.
    
    Debes:
    1. Analizar la salida estructurada del Agente de Auditorías
    2. Evaluar la calidad y completitud de los datos extraídos
    3. Asignar un concepto final: Favorable, Favorable con salvedades, o Desfavorable
    4. Proporcionar justificación para el concepto asignado
    
    Entrada: {audit_analysis_results}
    
    Aplicar juicio experto para clasificar los resultados de auditoría.
    """,
    expected_output="""
    Una evaluación final de auditoría que contenga:
    - Concepto final: Favorable/Favorable con salvedades/Desfavorable
    - Justificación detallada para el concepto
    - Evaluación de calidad del análisis
    - Recomendaciones de mejora si es necesario
    """,
    agent=agente_experto_auditorias
)

# Tarea para Agente Experto en Productos
task_experto_productos = Task(
    description="""
    Revisar los resultados del análisis de productos y asignar una clasificación de concepto final.
    
    Debes:
    1. Analizar la salida estructurada del Agente de Productos
    2. Evaluar la calidad y completitud de los datos extraídos
    3. Asignar un concepto final: Favorable, Favorable con salvedades, o Desfavorable
    4. Proporcionar justificación para el concepto asignado
    
    Entrada: {product_analysis_results}
    
    Aplicar juicio experto para clasificar los resultados de productos.
    """,
    expected_output="""
    Una evaluación final de productos que contenga:
    - Concepto final: Favorable/Favorable con salvedades/Desfavorable
    - Justificación detallada para el concepto
    - Evaluación de calidad del análisis
    - Recomendaciones de mejora si es necesario
    """,
    agent=agente_experto_productos
)

# Tarea para Agente Experto en Desembolsos
task_experto_desembolsos = Task(
    description="""
    Revisar los resultados del análisis de desembolsos y asignar una clasificación de concepto final.
    
    Debes:
    1. Analizar la salida estructurada del Agente de Desembolsos
    2. Evaluar la calidad y completitud de los datos extraídos
    3. Asignar un concepto final: Favorable, Favorable con salvedades, o Desfavorable
    4. Proporcionar justificación para el concepto asignado
    
    Entrada: {disbursement_analysis_results}
    
    Aplicar juicio experto para clasificar los resultados de desembolsos.
    """,
    expected_output="""
    Una evaluación final de desembolsos que contenga:
    - Concepto final: Favorable/Favorable con salvedades/Desfavorable
    - Justificación detallada para el concepto
    - Evaluación de calidad del análisis
    - Recomendaciones de mejora si es necesario
    """,
    agent=agente_experto_desembolsos
)

# Tarea para Agente Concatenador Final
task_concatenador = Task(
    description="""
    Consolidar todas las evaluaciones de expertos y generar archivos CSV finales.
    
    Debes:
    1. Recopilar salidas estructuradas de todos los agentes expertos
    2. Generar tres archivos CSV separados: Auditorías, Productos, Desembolsos
    3. Incluir todas las columnas definidas con seguimiento adecuado del origen de datos
    4. Asegurar una fila por registro con información completa
    5. Agregar columnas de observación para cambios de versión y notas de calidad de datos
    
    Entrada: {expert_assessments}
    
    Crear salidas CSV integrales para entrega final.
    """,
    expected_output="""
    Tres archivos CSV que contengan:
    - auditorias.csv: Todos los registros de auditoría con conceptos finales y observaciones
    - productos.csv: Todos los registros de productos con conceptos finales y observaciones  
    - desembolsos.csv: Todos los registros de desembolsos con conceptos finales y observaciones
    
    Cada CSV incluye:
    - Todas las variables extraídas
    - Concepto final del experto
    - Seguimiento del origen y fuente de datos
    - Notas de observación
    - Metadatos de procesamiento
    """,
    agent=agente_concatenador
)