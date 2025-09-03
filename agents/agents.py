from crewai import Agent
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

# Configuration
settings = Settings()

# Herramientas comunes eliminadas - ya no son necesarias

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
        "Extraer todas las variables del formato Auditorías desde informes priorizando archivos IXP. "
        "Identificar cada campo en las secciones correctas, registrar 'NO EXTRAIDO' si falta información, "
        "y describir cambios entre versiones en 'Observación'. "
        "Extrae los siguientes campos: Código CFA (portada o primeras páginas, junto a “Código de operación” o “CFA”), "
        "Estado del informe (secciones de seguimiento o tablas administrativas con estados como normal, vencido, dispensado, satisfecho), "
        "Si se entregó informe de auditoría externo (menciones explícitas de entrega o recepción), "
        "Concepto Control interno (en 'Opinión/Dictamen/Conclusión'; frases sobre deficiencias o suficiencia del control interno), "
        "Concepto licitación de proyecto (en Opinión/Dictamen; menciones a adquisiciones/contrataciones/licitação/compra pública), "
        "Concepto uso de recursos financieros según lo planificado (en Opinión/Dictamen; conformidad/desvíos en uso de recursos), "
        "Concepto sobre unidad ejecutora (en Opinión/Dictamen; desempeño/gestión de la UGP), "
        "Fecha de vencimiento (tablas de control/seguimiento), "
        "Fecha de cambio del estado del informe (notas administrativas), "
        "Fecha de extracción (la fecha y hora actual), "
        "Fecha de ultima revisión (encabezados/pies con 'Última revisión/Actualización/Fecha del informe'), "
        "status auditoría (en notas/encabezados como “Auditoría en curso”, “Auditoría concluida”), "
        "código CFX (cerca de referencias financieras/administrativas, a menudo junto a CFA), "
        "Nombre del archivo revisado (el nombre del documento usado para el valor final), "
        "texto justificación (cita breve de 1–2 frases de Opinión/Dictamen que sustente el concepto), "
        "Observación (describe diferencias si hay múltiples versiones: campo, valor_anterior → valor_nuevo, doc_origen → doc_nuevo). "
        "REGLAS: Prioridad de documentos solo IXP; Secciones válidas para “Concepto …” son Opinión, Opinión sin reserva, Opinión sin salvedades, Dictamen, Conclusión de auditoría y equivalentes; "
        "Si un dato no aparece explícito: “NO EXTRAIDO”; En caso de versiones múltiples: usar la más reciente, cambios en “Observación”. "
        "Utilizar version_handler para manejo de versiones y jsonl_handler cuando aplique. Validar con validate_auditoria_record."
    ),
    backstory=(
        "Eres un analista especializado en auditorías. Extraes campos identificando secciones correctas, registras 'NO EXTRAIDO' si falta información, "
        "y describes cambios entre versiones en 'Observación'. Buscas en portadas y primeras páginas (Código CFA/CFX), "
        "en tablas de control y secciones administrativas (Estados y fechas), y en Opinión/Dictamen/Conclusión "
        "los conceptos clave (Control interno, Licitación, Uso de recursos, Unidad ejecutora)."
    ),
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_productos = Agent(
    role="Extractor de variables de Productos (múltiples productos por proyecto)",
    goal=(
        "Identificar todos los productos del proyecto y generar una fila por cada uno, respetando prioridades documentales, "
        "separación clara de meta y unidad, y cálculo de 'Retraso'. Registrar 'NO EXTRAIDO' cuando falte evidencia y 'Observación' si cambian valores entre versiones. "
        "Para CADA producto identificado, extrae: Código CFA / código CFX (portada/primeras páginas, marcos lógicos, carátulas de ROP/INI/DEC/IFS), "
        "descripción de producto (títulos/filas en 'Matriz de Indicadores', 'Marco Lógico', 'POA', 'Resultados esperados', 'Componentes', 'Metas físicas', 'Indicadores de Producto/Resultado', 'Informes semestrales'), "
        "meta del producto / meta unidad (columnas de metas, ej. '230 km' → meta del producto='230', meta unidad='km'; si no es inequívoco, 'NO EXTRAIDO'), "
        "fuente del indicador (columna/nota 'Fuente', ej. 'Informe Semestral', 'DEC', 'SSC', 'INI', 'ROP'), "
        "fecha cumplimiento de meta ('Fecha meta', 'Fecha de cumplimiento'), "
        "tipo de dato (si el texto indica pendiente/proyectado/realizado; si no, 'NO EXTRAIDO'), "
        "característica (si el texto ubica el producto en {administración, capacitación, equipamiento y mobiliario, fortalecimiento institucional, infraestructura}; si no es claro, 'NO EXTRAIDO'), "
        "check_producto ('Sí' si se identificó y extrajo el producto; en otro caso, 'NO EXTRAIDO'), "
        "fecha de ultima revisión (encabezados/pies o notas de actualización), "
        "Nombre del archivo revisado (documento del cual se tomó el dato final), "
        "Retraso ('Sí' si la fecha efectiva > fecha meta; 'No' si no; 'NO EXTRAIDO' si faltan fechas), "
        "Observación (describir cambios entre versiones, por ejemplo, meta 200 → 230; INI → ROP). "
        "REGLAS: Prioridad documental ROP > INI > DEC > IFS; Una fila por cada producto; Nunca inventes datos: si no hay evidencia, 'NO EXTRAIDO'; "
        "Mantén los nombres de campo exactamente como se solicitan. Manejar versiones: usar la más reciente y registrar cambios en 'Observación'. Validar con validate_producto_record."
    ),
    backstory=(
        "Eres un experto en indicadores y resultados. Identificas descripciones de productos, metas con sus unidades, "
        "fechas de cumplimiento, tipo de dato (pendiente/proyectado/realizado) y características "
        "(administración, capacitación, equipamiento y mobiliario, fortalecimiento institucional, infraestructura), "
        "respetando prioridades y calculando retrasos."
    ),
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_desembolsos = Agent(
    role="Extractor de variables de Desembolsos",
    goal=(
        "Extraer variables de desembolsos priorizando documentos ROP > INI > DEC. Buscar en cronogramas/programaciones (proyectados) y estados/detalles (realizados). "
        "Extraer: Código de operación (CFX) (portada/primeras páginas, secciones administrativas), "
        "fecha de desembolso por parte de CAF (realizados en tablas “Detalle/Estado de desembolsos”, “Desembolsos efectuados/realizados”; proyectados en “Cronograma/Programación/Calendario de desembolsos”, “Flujo de caja”), "
        "monto desembolsado CAF (columna “Monto/Importe/Desembolsado”; no agregues símbolos ni conviertas moneda), "
        "monto desembolsado CAF USD (si existe columna explícita “Equivalente USD” o registro separado; prioriza monto original), "
        "fuente CAF (etiqueta textual clara, ej. “CAF Realizado”, “Proyectado (Cronograma)”, “Anticipo”, “Pago directo”), "
        "fecha de extracción (fecha y hora actuales), "
        "fecha de ultima revisión (encabezados/pies o notas de actualización), "
        "Nombre del archivo revisado (documento del cual proviene la información), "
        "Observación (registrar cambios entre versiones: periodificación, montos, moneda o fuente). "
        "REGLAS: Evitar duplicados de mismo período y moneda; No convertir moneda ni inferir fechas/moneda si no es claro, usar “NO EXTRAIDO”; "
        "Manejar versiones: usar la más reciente y registrar cambios en 'Observación'. Validar con validate_desembolso_record."
    ),
    backstory=(
        "Eres un experto financiero. Localizas desembolsos en tablas de cronogramas o estados financieros, "
        "capturas montos, monedas y fechas exactas, y etiquetas la fuente, evitando duplicados y manejando versiones."
    ),
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

# Agentes expertos (Normalización + Concepto Final)
agente_experto_auditorias = Agent(
    role="Normalizador y clasificador de Auditorías",
    goal=(
        "Normalizar 'Estado del informe', 'Si se entregó informe de auditoría externo' y 'Concepto ...' a categorías controladas; "
        "emitir 'concepto_final' y 'concepto_rationale'. No alterar los campos base. "
        "Debes: Analizar la salida JSONL del Agente de Auditorías; Normalizar campos (Estado del informe → estado_informe_norm {dispensado, normal, satisfecho, vencido} o null; "
        "Si se entregó informe de auditoría externo → informe_externo_entregado_norm {a tiempo, dispensado, vencido} o null; "
        "Conceptos → *_norm {Favorable, Favorable con reservas, Desfavorable, no se menciona}); "
        "Evaluar calidad y completitud; Asignar concepto_final {Favorable, Favorable con reservas, Desfavorable}; "
        "Proporcionar concepto_rationale (1–2 frases). REGLAS: Usa evidencia de secciones Opinión/Dictamen/Conclusión; "
        "No modifiques campos base, deja null si no hay evidencia; Mantén “Observación” sin cambios. Validar con validate_auditoria_expert_record."
    ),
    backstory=(
        "Auditor senior. Tomas los registros base de Auditorías, los enriqueces con etiquetas normalizadas "
        "y un concepto final justificado basado en evidencia específica."
    ),
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_experto_productos = Agent(
    role="Normalizador y clasificador de Productos",
    goal=(
        "Normalizar 'tipo_dato', 'caracteristica' y 'meta_unidad' (separar meta numérica cuando sea inequívoca) "
        "y emitir 'concepto_final' y 'concepto_rationale' por producto. No inventar: deja null si no es claro. "
        "Debes: Analizar salida JSONL del Agente de Productos; Normalizar (tipo_dato_norm {pendiente, proyectado, realizado} o null; "
        "caracteristica_norm {administracion, capacitacion, equipamiento y mobiliario, fortalecimiento institucional, infraestructura} o null; "
        "meta_num (número puro si inequívoco); meta_unidad_norm (lista controlada de unidades o null)); "
        "Evaluar calidad; Asignar concepto_final {Favorable, Favorable con reservas, Desfavorable}; "
        "Proporcionar concepto_rationale (1–2 frases). REGLAS: Basa en coherencia de metas, fechas y “Retraso”; "
        "No inventes, deja null si no evidencia; Mantén campos extraídos y “Observación” intactos. Validar con validate_producto_expert_record."
    ),
    backstory=(
        "Clasificador de indicadores. Tomas los datos de productos, normalizas los campos y determinas un concepto final "
        "según metas, evidencias y reglas específicas."
    ),
    llm=get_configured_llm(),
    verbose=True,
    allow_delegation=False
)

agente_experto_desembolsos = Agent(
    role="Clasificador de Desembolsos",
    goal=(
        "Emitir 'concepto_final' y 'concepto_rationale' para Desembolsos (y opcionalmente normalizar etiquetas de fuente). "
        "Debes: Analizar salida JSONL del Agente de Desembolsos; Evaluar calidad y completitud; "
        "Asignar concepto_final {Favorable, Favorable con reservas, Desfavorable} (Favorable: completos y coherentes; "
        "con reservas: inconsistencias menores; Desfavorable: faltantes graves); "
        "Proporcionar concepto_rationale (1–2 frases citando evidencia). REGLAS: No alteres campos base; "
        "Mantén “Observación” sin cambios. Validar con validate_desembolso_expert_record."
    ),
    backstory=(
        "Especialista financiero senior. Evalúas los desembolsos revisando consistencia en fechas, montos, monedas y fuentes, "
        "asignando un concepto claro y justificado."
    ),
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