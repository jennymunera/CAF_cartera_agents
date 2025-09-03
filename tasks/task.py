from crewai import Task
from agents.agents import (
    agente_auditorias, agente_productos, agente_desembolsos,
    agente_experto_auditorias, agente_experto_productos, agente_experto_desembolsos,
    agente_concatenador
)



# task_ingesta_document_intelligence eliminada - funcionalidad integrada en chunking_processor

# Tarea para Agente de Auditorías
task_auditorias = Task(
    description="""
      Extraer todas las variables del formato Auditorías desde informes priorizando archivos IXP.
      Identificar cada campo en las secciones correctas, registrar 'NO EXTRAIDO' si falta información,
      y describir cambios entre versiones en 'Observación'.

      Eres un analista especializado en auditorías. Extrae los siguientes campos:

      - Código CFA: portada o primeras páginas, junto a “Código de operación” o “CFA”.
      - Estado del informe: secciones de seguimiento o tablas administrativas con estados (normal, vencido, dispensado, satisfecho).
      - Si se entregó informe de auditoría externo: menciones explícitas de entrega o recepción (ej. “se entregó el informe de auditoría externa el …”).
      - Concepto Control interno: en “Opinión/Dictamen/Conclusión”; frases sobre deficiencias o suficiencia del control interno.
      - Concepto licitación de proyecto: en Opinión/Dictamen; menciones a adquisiciones/contrataciones/licitação/compra pública.
      - Concepto uso de recursos financieros según lo planificado: en Opinión/Dictamen; conformidad/ desvíos en uso de recursos.
      - Concepto sobre unidad ejecutora: en Opinión/Dictamen; desempeño/gestión de la UGP.
      - Fecha de vencimiento: tablas de control/seguimiento (“Fecha de vencimiento del informe”).
      - Fecha de cambio del estado del informe: notas administrativas (“el estado fue actualizado el …”).
      - Fecha de extracción: la fecha y hora actual.
      - Fecha de ultima revisión: encabezados/pies con “Última revisión/Actualización/Fecha del informe”.
      - status auditoría: en notas/encabezados (“Auditoría en curso”, “Auditoría concluida”, etc.).
      - código CFX: cerca de referencias financieras/administrativas, a menudo junto a CFA.
      - Nombre del archivo revisado: el nombre del documento usado para el valor final.
      - texto justificación: cita breve (1–2 frases) de Opinión/Dictamen que sustente el concepto.
      - Observación: describe diferencias si hay múltiples versiones (campo, valor_anterior → valor_nuevo, doc_origen → doc_nuevo).

      REGLAS:
      - Prioridad de documentos: solo IXP.
      - Secciones válidas para “Concepto …”: Opinión, Opinión sin reserva, Opinión sin salvedades, Dictamen, Conclusión de auditoría (y equivalentes).
      - Si un dato no aparece explícito: “NO EXTRAIDO”.
      - En caso de versiones múltiples: usar la más reciente; cambios → “Observación”.
    """,
    expected_output="""
    JSONL con registros de Auditorías (extracto base) que contenga:
      - "Código CFA"
      - "Estado del informe"
      - "Si se entregó informe de auditoría externo"
      - "Concepto Control interno"
      - "Concepto licitación de proyecto"
      - "Concepto uso de recursos financieros según lo planificado"
      - "Concepto sobre unidad ejecutora"
      - "Fecha de vencimiento"
      - "Fecha de cambio del estado del informe"
      - "Fecha de extracción"
      - "Fecha de ultima revisión"
      - "status auditoría"
      - "código CFX"
      - "Nombre del archivo revisado"
      - "texto justificación"
      - "Observación"
    """,
    agent=agente_auditorias,
    output_file="output_docs/{project_name}/agents_output/auditorias.jsonl"
)

# Tarea para Agente de Productos
task_productos = Task(
    description="""
    Identificar todos los productos del proyecto y generar una fila por cada uno,
      respetando prioridades documentales, separación clara de meta y unidad, y cálculo de 'Retraso'.
      Registrar “NO EXTRAIDO” cuando falte evidencia y “Observación” si cambian valores entre versiones.
    
      Eres un experto en indicadores y resultados. Para CADA producto identificado, extrae:

      - Código CFA / código CFX: portada/primeras páginas, marcos lógicos, carátulas de ROP/INI/DEC/IFS.
      - descripción de producto: títulos/filas en “Matriz de Indicadores”, “Marco Lógico”, “POA”, “Resultados esperados”,
        “Componentes”, “Metas físicas”, “Indicadores de Producto/Resultado”, “Informes semestrales” (capítulos “Resultados” o “Seguimiento de indicadores”).
      - meta del producto / meta unidad: columnas de metas (ej.: “230 km” → meta del producto="230", meta unidad="km");
        si no es inequívoco, usar “NO EXTRAIDO”.
      - fuente del indicador: columna/nota “Fuente” (ej.: “Informe Semestral”, “DEC”, “SSC”, “INI”, “ROP”).
      - fecha cumplimiento de meta: “Fecha meta”, “Fecha de cumplimiento” (usar tal cual está).
      - tipo de dato: si el texto indica pendiente/proyectado/realizado; si no, “NO EXTRAIDO”.
      - característica: si el texto ubica el producto en {administración, capacitación, equipamiento y mobiliario,
        fortalecimiento institucional, infraestructura}; si no es claro, “NO EXTRAIDO”.
      - check_producto: “Sí” si se identificó y extrajo el producto; en otro caso, “NO EXTRAIDO”.
      - fecha de ultima revisión: encabezados/pies o notas de actualización.
      - Nombre del archivo revisado: documento del cual se tomó el dato final.
      - Retraso: “Sí” si la fecha efectiva > fecha meta; “No” si no; “NO EXTRAIDO” si faltan fechas.
      - Observación: describir cambios entre versiones (por ejemplo, meta 200 → 230; INI → ROP).

      REGLAS:
      - Prioridad documental: ROP > INI > DEC > IFS.
      - Una fila por cada producto.
      - Nunca inventes datos: si no hay evidencia, “NO EXTRAIDO”.
      - Mantén los nombres de campo exactamente como se solicitan.

      

    """,
    expected_output="""
    JSONL con registros de Productos (extracto base por producto) que contenga:
      - "Código CFA"
      - "descripción de producto"
      - "meta del producto"
      - "meta unidad"
      - "fuente del indicador"
      - "fecha cumplimiento de meta"
      - "tipo de dato"
      - "característica"
      - "check_producto"
      - "fecha de extracción"
      - "fecha de ultima revisión"
      - "código CFX"
      - "Nombre del archivo revisado"
      - "Retraso"
      - "Observación"
    """,
    agent=agente_productos,
    output_file="output_docs/{project_name}/agents_output/productos.jsonl"
)

# Tarea para Agente de Desembolsos
task_desembolsos = Task(
    description="""
    Eres un experto financiero. Extrae:

      - Código de operación (CFX): portada/primeras páginas, secciones administrativas del proyecto.
      - fecha de desembolso por parte de CAF:
        • Realizados: tablas “Detalle/Estado de desembolsos”, “Desembolsos efectuados/realizados”.
        • Proyectados: “Cronograma/Programación/Calendario de desembolsos”, “Flujo de caja”.
      - monto desembolsado CAF: columna “Monto/Importe/Desembolsado”; no agregues símbolos ni conviertas moneda.
      - monto desembolsado CAF USD: si existe columna explícita “Equivalente USD” o registro separado. Si es la misma operación con dos columnas, prioriza el monto en moneda original y llena USD solo si no aparece la original.
      - fuente CAF: etiqueta textual clara (p. ej., “CAF Realizado”, “Proyectado (Cronograma)”, “Anticipo”, “Pago directo”).
      - fecha de extracción: fecha y hora actuales.
      - fecha de ultima revisión: encabezados/pies o notas de actualización del documento.
      - Nombre del archivo revisado: documento del cual proviene la información.
      - Observación: registrar cambios entre versiones (periodificación, montos, moneda o fuente).

      REGLAS:
      - Prioridad documental: ROP > INI > DEC.
      - Evitar duplicados: no repitas registros que representen el mismo periodo y moneda del mismo evento.
      - No convertir moneda ni inferir fechas/moneda si no es claro; en su lugar, “NO EXTRAIDO”.

    """,
    expected_output="""
    JSONL con registros de Desembolsos (extracto base) que contenga:
      - "Código de operación (CFX)"
      - "fecha de desembolso por parte de CAF"
      - "monto desembolsado CAF"
      - "monto desembolsado CAF USD"
      - "fuente CAF"
      - "fecha de extracción"
      - "fecha de ultima revisión"
      - "Nombre del archivo revisado"
      - "Observación"
    """,
    agent=agente_desembolsos,
    output_file="output_docs/{project_name}/agents_output/desembolsos.jsonl"
)

# Tarea para Agente Experto en Auditorías
task_experto_auditorias = Task(
    description="""
    Normalizar 'Estado del informe', 'Si se entregó informe de auditoría externo' y 'Concepto ...' a categorías
    controladas; emitir 'concepto_final' y 'concepto_rationale'. No alterar los campos base.
    
    Debes:
    1. Analizar la salida JSONL del Agente de Auditorías: {auditorias_jsonl}
    2. Normalizar campos a categorías controladas:
       - Estado del informe → estado_informe_norm
       - Si se entregó informe de auditoría externo → informe_externo_entregado_norm
       - Conceptos de control interno, licitación, uso de recursos, unidad ejecutora → *_norm
    3. Evaluar la calidad y completitud de los datos extraídos
    4. Asignar un concepto final: Favorable, Favorable con salvedades, o Desfavorable
    5. Proporcionar justificación para el concepto asignado (concepto_rationale)
    6. No alterar los campos base del extracto
    
     REGLAS DE NORMALIZACIÓN:
      - estado_informe_norm: {dispensado, normal, satisfecho, vencido} o null si no determinable.
      - informe_externo_entregado_norm: {a tiempo, dispensado, vencido} o null si no determinable.
      - concepto_control_interno_norm, concepto_licitacion_norm, concepto_uso_recursos_norm, concepto_unidad_ejecutora_norm:
        cada uno ∈ {Favorable, Favorable con reservas, Desfavorable, no se menciona}. Usa exclusivamente evidencia de secciones de Opinión/Dictamen/Conclusión.

      REGLAS DE CONCEPTO FINAL:
      - concepto_final: ∈ {Favorable, Favorable con reservas, Desfavorable}. Basa tu decisión en los normalizados y en el “texto justificación”.
      - concepto_rationale: 1–2 frases que sinteticen la evidencia.

      REGLAS GENERALES:
      - No modifiques los campos base. Si no hay evidencia, deja null en los normalizados.
      - Mantén el campo “Observación” sin cambios.


    Entrada: {auditorias_jsonl}
    
    Aplicar juicio experto para normalizar y clasificar los resultados de auditoría.
    """,
    expected_output="""
    JSONL con columnas originales + campos normalizados y de concepto:
    - estado_informe_norm
    - informe_externo_entregado_norm
    - concepto_control_interno_norm
    - concepto_licitacion_norm
    - concepto_uso_recursos_norm
    - concepto_unidad_ejecutora_norm
    - concepto_final: Favorable/Favorable con salvedades/Desfavorable
    - concepto_rationale: Justificación detallada para el concepto
    """,
    agent=agente_experto_auditorias,
    output_file="output_docs/{project_name}/agents_output/auditorias_expert.jsonl"
)

# Tarea para Agente Experto en Productos
task_experto_productos = Task(
    description="""
    Normalizar 'tipo_dato', 'caracteristica' y 'meta_unidad' (separar meta numérica cuando sea inequívoca)
    y emitir 'concepto_final' y 'concepto_rationale' por producto. No inventar: deja null si no es claro.
    
    Debes:
    1. Analizar la salida JSONL del Agente de Productos: {productos_jsonl}
    2. Normalizar campos a categorías controladas:
       - tipo_dato → tipo_dato_norm
       - caracteristica → caracteristica_norm
       - meta_unidad → meta_unidad_norm
       - Separar meta numérica cuando sea inequívoca → meta_num
    3. Evaluar la calidad y completitud de los datos extraídos por producto
    4. Asignar un concepto final: Favorable, Favorable con salvedades, o Desfavorable
    5. Proporcionar justificación para el concepto asignado (concepto_rationale)
    6. No inventar datos: dejar null si no es claro
    7. No alterar los campos base del extracto
    
    Entrada: {productos_jsonl}
    
     REGLAS DE NORMALIZACIÓN:
      - tipo_dato_norm: {pendiente, proyectado, realizado} o null (si no es claro).
      - caracteristica_norm: {administracion, capacitacion, equipamiento y mobiliario, fortalecimiento institucional, infraestructura} o null.
      - meta_num: número puro de la meta si es inequívoco (ej. “230 km” → 230); si no, null.
      - meta_unidad_norm: una de {unidades establecidas cantidad, kilómetros, metros cúbicos, porcentaje, metros cuadrados, horas, metros, hectárea,
        metros cúbicos / año, kilovoltamperio, Megavoltio amperio, litros / segundo, metros cúbicos / hora, metros cúbicos / día,
        Galones por día, Miles de galones por día, kilómetros / hora, toneladas, cantidad / año, metros cúbicos / segundo, miles de metros al cuadrado} o null.

      REGLAS DE CONCEPTO FINAL:
      - concepto_final: ∈ {Favorable, Favorable con reservas, Desfavorable}. Basa tu decisión en la coherencia de metas, fechas y “Retraso”.
      - concepto_rationale: 1–2 frases con la evidencia clave.

      REGLAS GENERALES:
      - No inventes: si no hay evidencia inequívoca, deja null en normalizados.
      - Mantén intactos los campos extraídos y “Observación”.

    Aplicar juicio experto para normalizar y clasificar los resultados de productos.
    """,
    expected_output="""
    JSONL con columnas originales + campos normalizados y de concepto:
    - tipo_dato_norm
    - caracteristica_norm
    - meta_num (valor numérico separado cuando sea inequívoco)
    - meta_unidad_norm
    - concepto_final: Favorable/Favorable con salvedades/Desfavorable
    - concepto_rationale: Justificación detallada para el concepto por producto
    """,
    agent=agente_experto_productos,
    output_file="output_docs/{project_name}/agents_output/productos_expert.jsonl"
)

# Tarea para Agente Experto en Desembolsos
task_experto_desembolsos = Task(
    description="""
    Emitir 'concepto_final' y 'concepto_rationale' para Desembolsos (y opcionalmente normalizar etiquetas de fuente).
    
    Debes:
    1. Analizar la salida JSONL del Agente de Desembolsos: {desembolsos_jsonl}
    2. Evaluar la calidad y completitud de los datos extraídos
    3. Opcionalmente normalizar etiquetas de fuente si es necesario
    4. Asignar un concepto final: Favorable, Favorable con salvedades, o Desfavorable
    5. Proporcionar justificación para el concepto asignado (concepto_rationale)
    6. No alterar los campos base del extracto
    
    REGLAS DE CLASIFICACION:

      - concepto_final: {Favorable, Favorable con reservas, Desfavorable}.
        • Favorable: registros completos y coherentes (fecha, monto, moneda, fuente).
        • Favorable con reservas: inconsistencias menores o diferencias explicadas entre programado/realizado.
        • Desfavorable: faltantes graves, incongruencias importantes o retrasos sostenidos sin justificación.
      - concepto_rationale: 1–2 frases que expliquen la decisión citando la evidencia.

      REGLAS GENERALES:
      - No alteres montos/monedas/fechas extraídas. Si un dato base está ausente o ambiguo, no lo modifiques.
      - Mantén “Observación” sin cambios.

    Entrada: {desembolsos_jsonl}
    
    Aplicar juicio experto para clasificar los resultados de desembolsos.
    """,
    expected_output="""
    JSONL con columnas originales + campos de concepto:
    - concepto_final: Favorable/Favorable con salvedades/Desfavorable
    - concepto_rationale: Justificación detallada para el concepto
    - Opcionalmente campos normalizados de fuente si se requiere
    """,
    agent=agente_experto_desembolsos,
    output_file="output_docs/{project_name}/agents_output/desembolsos_expert.jsonl"
)

# Tarea para Agente Concatenador Final
task_concatenador = Task(
    description="""
    Unificar los JSONL enriquecidos por experto y escribir tres archivos JSON separados (no CSV),
    con los campos requeridos por formato.
    
    Debes:
    1. Recopilar salidas JSONL de todos los agentes expertos:
       - {auditorias_expert_jsonl}
       - {productos_expert_jsonl}
       - {desembolsos_expert_jsonl}
    2. Generar tres archivos JSON separados (no CSV):
       - {auditorias_json}: array JSON con todos los registros de Auditorías
       - {productos_json}: array JSON con todos los registros de Productos
       - {desembolsos_json}: array JSON con todos los registros de Desembolsos
    3. Incluir todas las columnas definidas con seguimiento adecuado del origen de datos
    4. Asegurar formato JSON válido para cada archivo
    5. Mantener todos los campos originales y normalizados
    
    Entradas: {auditorias_expert_jsonl}, {productos_expert_jsonl}, {desembolsos_expert_jsonl}
    
    Crear salidas JSON finales para entrega.
    """,
    expected_output="""
    Tres archivos JSON que contengan:
    - auditorias.json: Array JSON con todos los registros de auditoría con conceptos finales y campos normalizados
    - productos.json: Array JSON con todos los registros de productos con conceptos finales y campos normalizados
    - desembolsos.json: Array JSON con todos los registros de desembolsos con conceptos finales
    
    Cada JSON incluye:
    - Todas las variables extraídas originales
    - Campos normalizados por expertos
    - Concepto final y rationale del experto
    - Seguimiento del origen y fuente de datos
    - Campos de observación y trazabilidad
    - Metadatos de procesamiento
    """,
    agent=agente_concatenador,
    output_file="output_docs/{project_name}/agents_output/concatenated_results.json"
)