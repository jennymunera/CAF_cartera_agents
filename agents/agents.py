from crewai import Agent
from crewai.tools import BaseTool
from config.settings import Settings
from datetime import datetime
from utils.version_handler import version_handler
from utils.jsonl_handler import jsonl_handler
from schemas.validation_schemas import (
    validate_auditoria_record,
    validate_producto_record,
    validate_desembolso_record,
    validate_auditoria_expert_record,
    validate_producto_expert_record,
    validate_desembolso_expert_record,
    validate_corpus_chunk
)
from rag import RAGConfig, RAGPipeline
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import json
import os

# Configuration
settings = Settings()

# RAG System Integration
class RAGToolSchema(BaseModel):
    """Schema para los argumentos del RAG Tool"""
    query: str = Field(..., description="La consulta de búsqueda semántica")
    document_types: Optional[List[str]] = Field(default=None, description="Tipos de documento a filtrar (opcional)")
    max_results: int = Field(default=5, description="Número máximo de resultados a retornar")

class RAGTool(BaseTool):
    """Herramienta RAG para búsqueda semántica en documentos indexados"""
    
    name: str = "rag_search"
    description: str = (
        "Busca información relevante en documentos indexados usando búsqueda semántica. "
        "Útil para encontrar información específica sobre auditorías, productos, desembolsos, "
        "códigos CFA/CFX, fechas, conceptos y cualquier otro dato en los documentos del proyecto."
    )
    args_schema: type[BaseModel] = RAGToolSchema
    
    def __init__(self, rag_pipeline: Optional[RAGPipeline] = None, **kwargs):
        super().__init__(**kwargs)
        self._rag_pipeline = rag_pipeline or self._initialize_rag_pipeline()
    
    def _initialize_rag_pipeline(self) -> Optional[RAGPipeline]:
        """Inicializa el pipeline RAG si no se proporciona"""
        try:
            config_path = os.path.join(os.getcwd(), "rag_config.json")
            if os.path.exists(config_path):
                config = RAGConfig.load_from_file(config_path)
                return RAGPipeline(config)
            else:
                print("Warning: RAG config not found. RAG functionality disabled.")
                return None
        except Exception as e:
            print(f"Warning: Could not initialize RAG pipeline: {e}")
            return None
    
    def _run(self, query: str, document_types: Optional[List[str]] = None, 
             max_results: int = 5, **kwargs) -> str:
        """Ejecuta búsqueda RAG"""
        if not self._rag_pipeline:
            return "RAG system not available. Please ensure the system is properly configured."
        
        try:
            # Preparar filtros de metadatos si se especifican tipos de documento
            metadata_filter = {}
            if document_types:
                metadata_filter["document_type"] = {"$in": document_types}
            
            # Realizar búsqueda híbrida
            results = self._rag_pipeline.query(
                query=query,
                top_k=max_results,
                metadata_filter=metadata_filter if metadata_filter else None,
                use_reranking=True
            )
            
            if not results:
                return f"No se encontraron resultados relevantes para: {query}"
            
            # Formatear resultados para el agente
            formatted_results = []
            for i, result in enumerate(results, 1):
                chunk_info = {
                    "resultado": i,
                    "relevancia": f"{result.get('score', 0):.3f}",
                    "documento": result.get('metadata', {}).get('source_file', 'Desconocido'),
                    "tipo_documento": result.get('metadata', {}).get('document_type', 'Desconocido'),
                    "pagina": result.get('metadata', {}).get('page_number', 'N/A'),
                    "contenido": result.get('content', '')[:500] + ('...' if len(result.get('content', '')) > 500 else '')
                }
                formatted_results.append(chunk_info)
            
            return json.dumps(formatted_results, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"Error en búsqueda RAG: {str(e)}"

# Inicializar herramienta RAG global
rag_tool = RAGTool()

# Function to get LLM lazily
def get_configured_llm():
    try:
        return settings.get_llm()
    except Exception as e:
        print(f"Could not configure LLM: {e}")
        print("Configure OPENAI_API_KEY in the .env file to use the agents")
        return None

# Agentes especializados (Extractores)
agente_auditorias = Agent(
    role="Extractor de variables de Auditorías",
    goal=(
        "Extraer todas las variables del formato Auditorías desde informes IXP. "
        "Revisar índice del documento y priorizar secciones Opinión/Dictamen/Conclusión para conceptos. "
        "Usar patrones flexibles y sinónimos para identificar cada campo, asignar niveles de confianza "
        "(EXTRAIDO_DIRECTO|EXTRAIDO_INFERIDO|NO_EXTRAIDO)"
        "IMPORTANTE: Usa la herramienta rag_search para buscar información específica en los documentos indexados. "
        "Busca términos como 'código CFA', 'auditoría', 'opinión', 'dictamen', 'conclusión', etc. "
        "Extrae los siguientes campos con búsqueda flexible: Código CFA (portada, primeras páginas, "
        "variaciones: 'Código de operación CFA', 'Op. CFA', 'Operación CFA'), "
        "Estado del informe (secciones de seguimiento, sinónimos: 'Estado', 'Situación del informe', 'Condición'), "
        "Si se entregó informe de auditoría externo (menciones explícitas de entrega o recepción), "
        "Concepto Control interno (en 'Opinión/Dictamen/Conclusión'; frases sobre deficiencias o suficiencia del control interno), "
        "Concepto licitación de proyecto (en Opinión/Dictamen; menciones a adquisiciones/contrataciones/licitação/compra pública), "
        "Concepto uso de recursos financieros según lo planificado (en Opinión/Dictamen; conformidad/desvíos en uso de recursos), "
        "Concepto sobre unidad ejecutora (en Opinión/Dictamen; desempeño/gestión de la UGP), "
        "Fecha de vencimiento (tablas de control/seguimiento), "
        "Fecha de cambio del estado del informe (notas administrativas), "
        "Fecha de extracción (la fecha y hora actual), "
        "Fecha de ultima revisión (usar la más reciente por fecha de informe, encabezados/pies con 'Última revisión/Actualización/Fecha del informe'), "
        "status auditoría (en notas/encabezados como 'Auditoría en curso', 'Auditoría concluida'), "
        "código CFX (campo SEPARADO del CFA, cerca de referencias financieras/administrativas, variaciones: 'Código CFX', 'Op. CFX', 'Operación CFX'), "
        "Nombre del archivo revisado (el nombre del documento usado para el valor final), "
        "texto justificación (cita breve de 1–2 frases de Opinión/Dictamen que sustente el concepto), "
        "Observación (describe diferencias si hay múltiples versiones: campo, valor_anterior → valor_nuevo, doc_origen → doc_nuevo). "
        "REGLAS: Prioridad de documentos solo IXP; CFA y CFX son códigos DISTINTOS y campos SEPARADOS; Secciones válidas para 'Concepto …' son Opinión, Opinión sin reserva, Opinión sin salvedades, Dictamen, Conclusión de auditoría y equivalentes; "
        "Observación (cambios entre versiones con formato: campo: valor_anterior → valor_nuevo). "
        "IMPORTANTE: Usar niveles de confianza para cada extracción y aplicar patrones flexibles de búsqueda."
    ),
    backstory=(
        "Eres un analista especializado en auditorías con capacidad de reconocimiento flexible de patrones. "
        "Usas sinónimos y variaciones para identificar información, asignas niveles de confianza apropiados, "
        "y mantienes trazabilidad completa de las extracciones realizadas. "
        "Tienes acceso a un sistema RAG que te permite buscar información específica en documentos indexados."
    ),
    tools=[rag_tool],
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_productos = Agent(
    role="Extractor de variables de Productos (múltiples productos por proyecto)",
    goal=(
        "Identificar todos los productos del proyecto y generar una fila por cada uno, aplicando jerarquía documental específica "
        "ROP > INI > DEC para metas; si no existen, ir a IFS o anexo. Validar sección correcta (producto vs resultado), "
        "distinguir 'Acumulado vs por período', manejar 'IFS, anexo' e 'idiomas y formatos'. "
        "Usar patrones flexibles y sinónimos para identificar cada campo, asignar niveles de confianza "
        "(EXTRAIDO_DIRECTO|EXTRAIDO_INFERIDO|NO_EXTRAIDO), y registrar 'Observación' si cambian valores entre versiones. "
        "IMPORTANTE: Usa la herramienta rag_search para buscar información específica en los documentos indexados. "
        "Busca términos como 'productos', 'metas', 'indicadores', 'matriz lógica', 'componentes', 'ROP', 'INI', 'DEC', etc. "
        "Para CADA producto identificado, extrae con búsqueda flexible: Código CFA (campo separado, portada/primeras páginas, marcos lógicos, carátulas de ROP/INI/DEC/IFS, "
        "variaciones: 'Código de operación CFA', 'Op. CFA', 'Operación CFA'), "
        "código CFX (campo SEPARADO del CFA, cerca de referencias financieras/administrativas, variaciones: 'Código CFX', 'Op. CFX', 'Operación CFX'), "
        "descripción de producto (títulos/filas en 'Matriz de Indicadores', 'Marco Lógico', 'POA', 'Resultados esperados', 'Componentes', 'Metas físicas', 'Indicadores de Producto/Resultado', 'Informes semestrales'), "
        "meta del producto / meta unidad (columnas de metas, patrones flexibles para separación numérica y unidad, ej. '230 km' → meta del producto='230', meta unidad='km'; "
        "formatos variables: '230 kilómetros', '230,5 Km', 'doscientos treinta km'; si no es inequívoco, 'NO EXTRAIDO'), "
        "fuente del indicador (columna/nota 'Fuente', sinónimos: 'Origen', 'Procedencia', ej. 'Informe Semestral', 'DEC', 'SSC', 'INI', 'ROP'), "
        "fecha cumplimiento de meta (patrones flexibles: 'Fecha meta', 'Fecha de cumplimiento', 'Vencimiento', 'Plazo'), "
        "tipo de dato (patrones para identificar si el texto indica pendiente/proyectado/realizado; búsqueda en contexto; si no es claro, 'NO EXTRAIDO'), "
        "característica (patrones flexibles para ubicar el producto en {administración, capacitación, equipamiento y mobiliario, fortalecimiento institucional, infraestructura}; "
        "sinónimos y variaciones; si no es claro, 'NO EXTRAIDO'), "
        "check_producto ('Sí' si se identificó y extrajo el producto; en otro caso, 'NO EXTRAIDO'), "
        "fecha de ultima revisión (encabezados/pies o notas de actualización, patrones flexibles), "
        "Nombre del archivo revisado (documento del cual se tomó el dato final), "
        "Retraso ('Sí' si la fecha efectiva > fecha meta; 'No' si no; 'NO EXTRAIDO' si faltan fechas), "
        "Observación (describir cambios entre versiones, por ejemplo, meta 200 → 230; INI → ROP). "
        "REGLAS: Prioridad documental ROP > INI > DEC > IFS; CFA y CFX son códigos DISTINTOS y campos SEPARADOS; Una fila por cada producto; "
        "Nunca inventes datos: si no hay evidencia, 'NO EXTRAIDO'; Usar niveles de confianza para cada extracción; "
        "Aplicar patrones flexibles de búsqueda y reconocimiento; Mantén los nombres de campo exactamente como se solicitan. "
        "Manejar versiones: usar la más reciente y registrar cambios en 'Observación'. Validar con validate_producto_record."
    ),
    backstory=(
        "Eres un experto en indicadores y resultados con capacidad de reconocimiento flexible de patrones. "
        "Identificas y extraes productos relacionados al cumplimiento del proyecto, descripciones de productos, metas con sus unidades, "
        "fechas de cumplimiento, tipo de dato (pendiente/proyectado/realizado) y características "
        "(administración, capacitación, equipamiento y mobiliario, fortalecimiento institucional, infraestructura), "
        "usando sinónimos y variaciones para identificar información, asignando niveles de confianza apropiados, "
        "respetando prioridades documentales y calculando retrasos con trazabilidad completa. "
        "Tienes acceso a un sistema RAG que te permite buscar información específica en documentos indexados."
    ),
    tools=[rag_tool],
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_desembolsos = Agent(
    role="Extractor de variables de Desembolsos",
    goal=(
        "Extraer variables de desembolsos con ubicaciones específicas: cronogramas en Manual Operativo (ROP) o Informe Inicial (INI); "
        "si no están disponibles, buscar en DEC. Priorizar documentos ROP > INI > DEC. Usar patrones flexibles y sinónimos para identificar cada campo, "
        "asignar niveles de confianza (EXTRAIDO_DIRECTO|EXTRAIDO_INFERIDO|NO_EXTRAIDO), "
        "y registrar 'Observación' si cambian valores entre versiones. "
        "IMPORTANTE: Usa la herramienta rag_search para buscar información específica en los documentos indexados. "
        "Busca términos como 'desembolsos', 'cronograma', 'CAF', 'montos', 'fechas', 'ROP', 'INI', 'DEC', etc. "
        "Buscar cronogramas/programaciones (proyectados) prioritariamente en ROP/INI, y estados/detalles (realizados) en cualquier documento. "
        "Extraer con búsqueda flexible: Código de operación (CFX) (portada/primeras páginas, secciones administrativas, "
        "variaciones: 'Código CFX', 'Op. CFX', 'Operación CFX'), "
        "fecha de desembolso por parte de CAF (realizados en tablas 'Detalle/Estado de desembolsos', 'Desembolsos efectuados/realizados'; "
        "proyectados prioritariamente en ROP/INI: 'Cronograma/Programación/Calendario de desembolsos', 'Flujo de caja'; si no están, buscar en DEC, patrones flexibles para fechas), "
        "monto desembolsado CAF (columna 'Monto/Importe/Desembolsado'; priorizar moneda original, no agregues símbolos ni conviertas moneda, patrones flexibles para montos), "
        "monto desembolsado CAF USD (si existe columna 'Equivalente USD' o registro separado; conservar USD solo si no aparece moneda original), "
        "fuente CAF (etiqueta clara con fuente específica, ej. 'CAF Realizado (DEC)', 'Proyectado (Cronograma ROP)', 'Anticipo (INI)', 'Pago directo', sinónimos y variaciones), "
        "fecha de extracción (fecha y hora actuales), "
        "fecha de ultima revisión (encabezados/pies o notas de actualización, patrones flexibles), "
        "Nombre del archivo revisado (documento del cual proviene la información), "
        "Observación (registrar cambios entre versiones: periodificación, montos, moneda o fuente). "
        "REGLAS: Ubicaciones específicas para cronogramas: ROP/INI prioritario, DEC si no disponible; "
        "Priorizar moneda original y conservar USD solo si no aparece la original; No repetir mismo período+moneda; "
        "No convertir moneda ni inferir fechas/moneda, si no se encuentra usar 'NO EXTRAIDO'; "
        "Usar niveles de confianza para cada extracción; Aplicar patrones flexibles de búsqueda y reconocimiento; "
        "Manejar versiones: usar la más reciente y registrar cambios en 'Observación'. Validar con validate_desembolso_record."
    ),
    backstory=(
        "Eres un experto financiero con capacidad de reconocimiento flexible de patrones. "
        "Extraes información relacionada a desembolsos en tablas de cronogramas o estados financieros, "
        "capturas montos, monedas y fechas exactas usando sinónimos y variaciones para identificar información, "
        "asignas niveles de confianza apropiados, etiquetas la fuente con precisión, "
        "evitas duplicados y manejas versiones con trazabilidad completa. "
        "Tienes acceso a un sistema RAG que te permite buscar información específica en documentos indexados."
    ),
    tools=[rag_tool],
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

# Agentes expertos (Normalización + Concepto Final)
agente_experto_auditorias = Agent(
    role="Normalizador y clasificador de Auditorías",
    goal=(
        "Normalizar 'Estado del informe', 'Si se entregó informe de auditoría externo' y 'Concepto ...' a categorías controladas; "
        "emitir 'concepto_final' y 'concepto_rationale' basado en lenguaje específico del auditor. No alterar los campos base. "
        "IMPORTANTE: Usa la herramienta rag_search para verificar información específica en los documentos indexados cuando sea necesario. "
        "Debes: Analizar la salida JSONL del Agente de Auditorías; Normalizar campos (Estado del informe → estado_informe_norm {dispensado, normal, satisfecho, vencido} o null; "
        "Si se entregó informe de auditoría externo → informe_externo_entregado_norm {a tiempo, dispensado, vencido} o null; "
        "Conceptos → *_norm {Favorable, Favorable con reservas, Desfavorable, no se menciona}); "
        "Evaluar calidad y completitud; Asignar concepto_final basado en criterios específicos: "
        "Favorable (lenguaje positivo del auditor: 'adecuado', 'suficiente', 'cumple', 'satisfactorio'), "
        "Favorable con reservas (lenguaje mixto: 'con observaciones', 'salvedades menores', 'mejoras recomendadas'), "
        "Desfavorable (lenguaje crítico: 'deficiente', 'inadecuado', 'incumplimiento', 'deficiencias graves'); "
        "Proporcionar concepto_rationale (1–2 frases citando lenguaje específico del auditor). "
        "REGLAS: Usa EXCLUSIVAMENTE evidencia de secciones Opinión/Dictamen/Conclusión; "
        "Basar clasificación en terminología específica del auditor; No modifiques campos base, deja null si no hay evidencia; "
        "Mantén 'Observación' sin cambios. Validar con validate_auditoria_expert_record."
    ),
    backstory=(
        "Auditor senior. Tomas los registros base de Auditorías, los enriqueces con etiquetas normalizadas "
        "y un concepto final justificado basado en evidencia específica. "
        "Tienes acceso a un sistema RAG para verificar información cuando sea necesario."
    ),
    tools=[rag_tool],
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_experto_productos = Agent(
    role="Normalizador y clasificador de Productos",
    goal=(
        "Normalizar 'tipo_dato', 'caracteristica' y 'meta_unidad' aplicando casos especiales: distinguir 'Acumulado vs por período', "
        "manejar 'IFS en Excel anexo', considerar 'idiomas y formatos diversos', validar 'sección correcta (producto vs resultado)'. "
        "Separar meta numérica cuando sea inequívoco y emitir 'concepto_final' y 'concepto_rationale' por producto. No inventar: deja null si no es claro. "
        "IMPORTANTE: Usa la herramienta rag_search para verificar información específica en los documentos indexados cuando sea necesario. "
        "Debes: Analizar salida JSONL del Agente de Productos; Normalizar (tipo_dato_norm {pendiente, proyectado, realizado} o null; "
        "caracteristica_norm {administracion, capacitacion, equipamiento y mobiliario, fortalecimiento institucional, infraestructura} o null; "
        "meta_num (número puro si inequívoco, distinguiendo acumulado vs por período); meta_unidad_norm (lista controlada de unidades o null)); "
        "Evaluar calidad considerando jerarquía documental ROP > INI > DEC > IFS; Asignar concepto_final {Favorable, Favorable con reservas, Desfavorable}; "
        "Proporcionar concepto_rationale (1–2 frases). REGLAS: Basa en coherencia de metas, fechas y \"Retraso\"; "
        "Validar que los datos correspondan a productos y no a resultados; Considerar diferentes idiomas y formatos; "
        "No inventes, deja null si no evidencia; Mantén campos extraídos y \"Observación\" intactos. Validar con validate_producto_expert_record."
    ),
    backstory=(
        "Clasificador de indicadores. Tomas los datos de productos, normalizas los campos y determinas un concepto final "
        "según metas, evidencias y reglas específicas. "
        "Tienes acceso a un sistema RAG para verificar información cuando sea necesario."
    ),
    tools=[rag_tool],
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_experto_desembolsos = Agent(
    role="Clasificador de Desembolsos",
    goal=(
        "Emitir 'concepto_final' y 'concepto_rationale' para Desembolsos (y opcionalmente normalizar etiquetas de fuente). "
        "IMPORTANTE: Usa la herramienta rag_search para verificar información específica en los documentos indexados cuando sea necesario. "
        "Debes: Analizar salida JSONL del Agente de Desembolsos; Evaluar calidad y completitud; "
        "Asignar concepto_final {Favorable, Favorable con reservas, Desfavorable} (Favorable: completos y coherentes; "
        "con reservas: inconsistencias menores; Desfavorable: faltantes graves); "
        "Proporcionar concepto_rationale (1–2 frases citando evidencia). REGLAS: No alteres campos base; "
        "Mantén 'Observación' sin cambios. Validar con validate_desembolso_expert_record."
    ),
    backstory=(
        "Especialista financiero senior. Evalúas los desembolsos revisando consistencia en fechas, montos, monedas y fuentes, "
        "asignando un concepto claro y justificado. "
        "Tienes acceso a un sistema RAG para verificar información cuando sea necesario."
    ),
    tools=[rag_tool],
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

# Agente concatenador final
agente_concatenador = Agent(
    role="Concatenador de salidas finales",
    goal=(
        "Unificar las salidas enriquecidas (extractores + expertos) y generar tres JSON finales: auditorias.json, productos.json y desembolsos.json. "
        "Recopilar salidas JSONL de expertos; Generar arrays JSON separados incluyendo todas columnas con origen de datos; "
        "Asegurar formato JSON válido; Mantener campos originales, normalizados y de concepto; Preservar Observación y 'Nombre del archivo revisado'. "
        "Validar entradas con validate_corpus_chunk cuando aplique."
    ),
    backstory=(
        "Integrador de resultados. Reúnes todas las salidas enriquecidas y las consolidas en tres archivos JSON "
        "finales manteniendo integridad, trazabilidad y validaciones."
    ),
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)