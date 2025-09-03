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
      Eres un analista especializado en auditorías con enfoque en extracción precisa y trazable. Busca de manera sistemática y flexible los siguientes campos::

      - Código CFA: buscar en múltiples ubicaciones con sinónimos. Ubicaciones: portada, primeras páginas, marcos lógicos, carátulas. Variaciones: "CFA", "Código CFA", "Código de operación", "Op. CFA", "Operación CFA", "No. CFA", "CFX".
      
      - Estado del informe: usar patrones flexibles para diferentes formatos. Ubicaciones: secciones de seguimiento, tablas administrativas, notas de control. Estados válidos: "normal", "vencido", "dispensado", "satisfecho", "en proceso", "pendiente". Sinónimos: "estado", "situación", "condición", "status".
      
      - Si se entregó informe de auditoría externo: buscar menciones explícitas. Patrones: "entrega de informe", "recepción de auditoría", "informe externo", "auditoría externa", "entregado", "recibido", "presentado".
      
      - Concepto Control interno: buscar en secciones específicas con sinónimos. Secciones válidas: "Opinión", "Opinión sin reserva", "Opinión sin salvedades", "Dictamen", "Conclusión de auditoría", "Conclusiones", "Resultados". Patrones: "control interno", "controles internos", "sistema de control", "deficiencias de control", "suficiencia del control".
      
      - Concepto licitación de proyecto: buscar en secciones de opinión con variaciones. Patrones: "licitación", "licitações", "adquisiciones", "contrataciones", "compra pública", "procurement", "contratação", "aquisições".
      
      - Concepto uso de recursos financieros según lo planificado: buscar conformidad en uso de recursos. Patrones: "uso de recursos", "utilización de fondos", "aplicación de recursos", "destino de recursos", "conformidad", "desvíos", "según planificado".
      
      - Concepto sobre unidad ejecutora: evaluar desempeño de la UGP. Patrones: "unidad ejecutora", "UGP", "gestión del proyecto", "desempeño", "capacidad de ejecución", "administración del proyecto".
      
      - Fecha de vencimiento: buscar en tablas de control con formatos flexibles. Ubicaciones: tablas de seguimiento, cronogramas, calendarios. Formatos: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, "Enero 2023", "Q1 2023".
      
      - Fecha de cambio del estado del informe: buscar en notas administrativas y actualizaciones.
      
      - Fecha de extracción: usar la fecha y hora actual del procesamiento.
      
      - Fecha de ultima revisión: buscar en múltiples ubicaciones. Ubicaciones: encabezados, pies de página, portadas, metadatos. Variaciones: "Última revisión", "Actualización", "Fecha del documento", "Versión", "Modificado".
      
      - status auditoría: buscar en notas y encabezados. Estados: "Auditoría en curso", "Auditoría concluida", "En proceso", "Finalizada", "Pendiente".
      
      - código CFX: buscar cerca de referencias financieras, a menudo junto a CFA.
      
      - Nombre del archivo revisado: registrar el documento específico del cual proviene la información final.
      
      - texto justificación: extraer cita breve de 1-2 frases de Opinión/Dictamen que sustente el concepto.
      
      - Observación: describir cambios entre versiones con formato específico (campo: valor_anterior → valor_nuevo; documento_origen → documento_nuevo).

      NIVELES DE CONFIANZA:
      Para cada campo extraído, asignar un nivel de confianza:
      - EXTRAIDO_DIRECTO: información encontrada explícitamente en el texto, con términos exactos o muy similares
      - EXTRAIDO_INFERIDO: información deducida del contexto, sinónimos o patrones relacionados
      - NO_EXTRAIDO: información no encontrada o ambigua
      
      Formato de salida: "valor|NIVEL_CONFIANZA" (ej: "normal|EXTRAIDO_DIRECTO", "NO EXTRAIDO|NO_EXTRAIDO")

      ESTRATEGIAS DE BÚSQUEDA MEJORADAS:
      - Buscar en múltiples secciones antes de concluir "NO EXTRAIDO"
      - Usar sinónimos y variaciones de términos clave
      - Considerar diferentes formatos de fecha y códigos
      - Revisar tablas, anexos y secciones narrativas
      - Identificar patrones contextuales cuando los términos exactos no aparecen

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
    description="""Eres un experto en indicadores y resultados con enfoque en extracción precisa y trazable. Identifica todos los productos del proyecto y genera una fila por cada uno:

      - Código CFA / código CFX: buscar en múltiples ubicaciones. Ubicaciones: portada, primeras páginas, marcos lógicos, carátulas de ROP/INI/DEC/IFS. Variaciones: "CFA", "CFX", "Código de operación", "Op. CFA", "Operación CFA", "No. CFA".
      
      - descripción de producto: identificar en diferentes secciones y formatos. Ubicaciones: "Matriz de Indicadores", "Marco Lógico", "POA", "Resultados esperados", "Componentes", "Metas físicas", "Indicadores de Producto/Resultado", "Informes semestrales". Patrones: títulos de productos, descripciones de resultados, componentes del proyecto.
      
      - meta del producto / meta unidad: separar claramente valor numérico y unidad. Patrones de reconocimiento:
        • Formatos típicos: "230 km", "1,500 personas", "50 unidades", "100%", "25 talleres"
        • Separación: "230 km" → meta del producto="230", meta unidad="km"
        • Unidades comunes: km, personas, unidades, talleres, capacitaciones, %, hectáreas, viviendas
        • Si no es inequívoco o hay ambigüedad: "NO EXTRAIDO"
      
      - fuente del indicador: identificar origen de la información. Ubicaciones: columnas "Fuente", notas al pie, referencias. Fuentes típicas: "Informe Semestral", "DEC", "SSC", "INI", "ROP", "Reporte de avance", "Monitoreo".
      
      - fecha cumplimiento de meta: buscar con patrones flexibles. Ubicaciones: "Fecha meta", "Fecha de cumplimiento", "Plazo", "Cronograma". Formatos: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, "Diciembre 2023", "Q4 2023".
      
      - tipo de dato: identificar naturaleza temporal del dato. Criterios:
        • Pendiente: "por ejecutar", "programado", "planificado", "futuro"
        • Proyectado: "estimado", "proyectado", "esperado", "previsto"
        • Realizado: "ejecutado", "completado", "logrado", "alcanzado", "cumplido"
        • Si no es claro: "NO EXTRAIDO"
      
      - característica: clasificar tipo de producto. Categorías:
        • administración: gestión, administración, coordinación, supervisión
        • capacitación: entrenamiento, formación, talleres, cursos, capacitación
        • equipamiento y mobiliario: equipos, herramientas, mobiliario, tecnología
        • fortalecimiento institucional: institucional, organizacional, normativo, legal
        • infraestructura: construcción, obras, infraestructura, edificaciones
        • Si no es claro: "NO EXTRAIDO"
      
      - check_producto: "Sí" si se identificó y extrajo el producto correctamente; "NO EXTRAIDO" en caso contrario.
      
      - fecha de ultima revisión: buscar en encabezados, pies de página o notas de actualización.
      
      - Nombre del archivo revisado: documento del cual se tomó el dato final.
      
      - Retraso: calcular comparando fechas. "Sí" si fecha efectiva > fecha meta; "No" si no hay retraso; "NO EXTRAIDO" si faltan fechas para el cálculo.
      
      - Observación: describir cambios entre versiones (formato: meta 200 → 230; INI → ROP).

      NIVELES DE CONFIANZA:
      Para cada campo extraído, asignar un nivel de confianza:
      - EXTRAIDO_DIRECTO: información encontrada explícitamente en tablas, matrices o texto con términos exactos
      - EXTRAIDO_INFERIDO: información deducida del contexto, categorización basada en descripción, o separación de meta/unidad por patrones
      - NO_EXTRAIDO: información no encontrada, ambigua o no clasificable
      
      Formato de salida: "valor|NIVEL_CONFIANZA" (ej: "230|EXTRAIDO_DIRECTO", "km|EXTRAIDO_INFERIDO", "NO EXTRAIDO|NO_EXTRAIDO")

      ESTRATEGIAS DE BÚSQUEDA PARA PRODUCTOS:
      - Revisar matrices de indicadores en diferentes formatos y orientaciones
      - Buscar productos en secciones narrativas y anexos técnicos
      - Identificar componentes y subcomponentes del proyecto
      - Distinguir entre metas físicas y financieras
      - Considerar diferentes períodos de reporte y versiones de documentos
      - Buscar información complementaria en gráficos y cuadros

      PATRONES DE RECONOCIMIENTO PARA METAS:
      - Números con unidades explícitas: "500 personas", "25 km", "100%"
      - Formatos con separadores: "1,500", "1.500", "1 500"
      - Unidades implícitas en contexto: "capacitar 200" (personas), "construir 50" (unidades)
      - Porcentajes y ratios: "85%", "1:10", "50 por cada 100"
      - Rangos y aproximaciones: "entre 200-300", "aproximadamente 150"

      REGLAS:
      - Prioridad documental: ROP > INI > DEC > IFS.
      - Una fila por cada producto identificado.
      - Nunca inventar datos: si no hay evidencia clara, "NO EXTRAIDO|NO_EXTRAIDO".
      - Mantener nombres de campo exactamente como se solicitan.
      - Versiones múltiples: usar la más reciente y registrar cambios en "Observación".
      - Validar coherencia entre meta, unidad y descripción del producto.

      EJEMPLOS DE PATRONES TÍPICOS:
      
      Descripción de producto:
      - "Construcción de 25 km de carretera pavimentada" → "Construcción de carretera pavimentada|EXTRAIDO_DIRECTO"
      - "Capacitación a 500 beneficiarios en técnicas agrícolas" → "Capacitación en técnicas agrícolas|EXTRAIDO_DIRECTO"
      - "Fortalecimiento institucional de 3 municipalidades" → "Fortalecimiento institucional municipal|EXTRAIDO_DIRECTO"
      
      Meta del producto / Meta unidad:
      - "230 km de carretera" → meta del producto="230|EXTRAIDO_DIRECTO", meta unidad="km|EXTRAIDO_DIRECTO"
      - "1,500 personas capacitadas" → meta del producto="1,500|EXTRAIDO_DIRECTO", meta unidad="personas|EXTRAIDO_DIRECTO"
      - "85% de cumplimiento" → meta del producto="85|EXTRAIDO_DIRECTO", meta unidad="%|EXTRAIDO_DIRECTO"
      - "Capacitar 200 beneficiarios" → meta del producto="200|EXTRAIDO_INFERIDO", meta unidad="personas|EXTRAIDO_INFERIDO"
      
      Tipo de dato:
      - "Meta programada para 2024" → "proyectado|EXTRAIDO_INFERIDO"
      - "Resultado alcanzado" → "realizado|EXTRAIDO_DIRECTO"
      - "Pendiente de ejecución" → "pendiente|EXTRAIDO_DIRECTO"
      
      Característica:
      - "Construcción de infraestructura vial" → "infraestructura|EXTRAIDO_INFERIDO"
      - "Talleres de capacitación" → "capacitación|EXTRAIDO_INFERIDO"
      - "Adquisición de equipos médicos" → "equipamiento y mobiliario|EXTRAIDO_INFERIDO"
      - "Fortalecimiento del marco normativo" → "fortalecimiento institucional|EXTRAIDO_INFERIDO"
      - "Coordinación del proyecto" → "administración|EXTRAIDO_INFERIDO"
      
      Fechas:
      - "Fecha meta: 31/12/2023" → "31/12/2023|EXTRAIDO_DIRECTO"
      - "Cumplimiento previsto para el cuarto trimestre" → "Q4 2023|EXTRAIDO_INFERIDO"
      - "Plazo: diciembre 2023" → "Diciembre 2023|EXTRAIDO_INFERIDO"
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
    description="""Eres un experto financiero especializado en análisis de desembolsos. Busca de manera sistemática y flexible los siguientes campos:

      - Código de operación (CFX): buscar en múltiples ubicaciones. Ubicaciones: portada, primeras páginas, secciones administrativas, encabezados, pies de página. Variaciones: "CFX", "Código CFX", "Código de operación", "Op. CFX", "Operación CFX", "No. CFX", "Número de operación".
      
      - fecha de desembolso por parte de CAF: usar patrones flexibles para diferentes formatos de fecha. Ubicaciones y tipos:
        • Realizados: tablas "Detalle de desembolsos", "Estado de desembolsos", "Desembolsos efectuados", "Desembolsos realizados", "Pagos ejecutados", "Transferencias realizadas"
        • Proyectados: "Cronograma de desembolsos", "Programación de desembolsos", "Calendario de desembolsos", "Flujo de caja", "Proyección financiera", "Plan de desembolsos"
        • Formatos de fecha: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, DD-MM-YYYY, "Enero 2023", "Q1 2023", "Trimestre 1", "Semestre 2"
        • Términos temporales: "trimestre", "semestre", "anual", "mensual", "quincenal"
      
      - monto desembolsado CAF: usar patrones flexibles para diferentes formatos monetarios. Patrones de reconocimiento:
        • Formatos numéricos: "1,000,000", "1.000.000", "1 000 000", "1000000"
        • Con decimales: "1,500.50", "1.500,50", "1 500.50"
        • Con símbolos: "$1,000", "USD 1,000", "1,000 USD", "US$ 1,000"
        • Monedas locales: "S/ 1,000", "COP 1,000", "ARS 1,000", "PEN 1,000"
        • En tablas: columnas "Monto", "Importe", "Desembolsado", "Valor", "Cantidad", "Total"
        • Texto descriptivo: "por un monto de", "equivalente a", "suma de"
        No agregar símbolos ni convertir moneda - extraer tal como aparece.
      
      - monto desembolsado CAF USD: buscar específicamente montos en dólares americanos. Criterios:
        • Columnas explícitas: "Equivalente USD", "En USD", "Dólares", "US$", "USD"
        • Registros separados con misma fecha pero diferente moneda
        • Si hay misma operación con dos columnas, priorizar moneda original
        • Solo llenar USD si no aparece la moneda original o si hay conversión explícita
        • Formatos: "USD 1,000", "$1,000", "1,000 USD", "US$ 1,000"
      
      - fuente CAF: identificar origen y tipo de desembolso. Variaciones:
        • Realizados: "CAF Realizado", "Desembolso efectivo", "Pago ejecutado", "Transferencia realizada"
        • Proyectados: "Proyectado (Cronograma)", "Programado", "Planificado", "Estimado"
        • Tipos: "Anticipo", "Pago directo", "Reembolso", "Transferencia", "Giro"
        • Documentos: "Según ROP", "Según INI", "Según DEC", "Informe financiero"
      
      - fecha de extracción: usar la fecha y hora actual del procesamiento.
      
      - fecha de ultima revisión: buscar en múltiples ubicaciones. Ubicaciones: encabezados, pies de página, portadas, notas de actualización, metadatos. Variaciones: "Última revisión", "Actualización", "Fecha del documento", "Versión", "Modificado", "Revisado el", "Actualizado el".
      
      - Nombre del archivo revisado: registrar el documento específico del cual proviene la información final.
      
      - Observación: describir cambios entre versiones con formato específico. Incluir: cambios en periodificación, variaciones en montos, cambios de moneda, modificaciones en fuente (formato: campo: valor_anterior → valor_nuevo; documento_origen → documento_nuevo).

      NIVELES DE CONFIANZA:
      Para cada campo extraído, asignar un nivel de confianza:
      - EXTRAIDO_DIRECTO: información encontrada explícitamente en tablas financieras, con valores exactos y claros
      - EXTRAIDO_INFERIDO: información deducida del contexto, fechas aproximadas, o montos calculados a partir de totales
      - NO_EXTRAIDO: información no encontrada, ambigua o inconsistente
      
      Formato de salida: "valor|NIVEL_CONFIANZA" (ej: "1,500,000|EXTRAIDO_DIRECTO", "Q1 2023|EXTRAIDO_INFERIDO", "NO EXTRAIDO|NO_EXTRAIDO")

      ESTRATEGIAS DE BÚSQUEDA PARA DESEMBOLSOS:
      - Revisar tablas financieras en diferentes formatos y orientaciones
      - Buscar información en secciones narrativas y anexos financieros
      - Identificar desembolsos parciales y totales
      - Distinguir entre montos programados y ejecutados
      - Considerar diferentes períodos de reporte (mensual, trimestral, anual)
      - Buscar información en gráficos y cuadros financieros

      PATRONES DE RECONOCIMIENTO PARA MONTOS:
      - Números con separadores: comas, puntos, espacios
      - Diferentes posiciones de símbolos monetarios
      - Formatos de miles y millones: K, M, MM
      - Monedas en diferentes idiomas: dollars, pesos, soles
      - Abreviaciones: USD, US$, $, COP, PEN, ARS

      REGLAS:
      - Prioridad documental: ROP > INI > DEC.
      - Evitar duplicados: no repetir registros del mismo período, moneda y evento.
      - No convertir moneda ni inferir fechas/moneda si no es claro; usar "NO EXTRAIDO|NO_EXTRAIDO".
      - Mantener formato original de montos y fechas.
      - Para fechas ambiguas, priorizar extracción literal sobre interpretación.
      - Distinguir claramente entre desembolsos realizados y proyectados.
      - Mantener trazabilidad con niveles de confianza para auditoría financiera.
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
    Normalizar 'tipo_dato', 'caracteristica' y 'meta_unidad' (separar meta numérica cuando sea inequívoco)
    y emitir 'concepto_final' y 'concepto_rationale' por producto. No inventar: deja null si no es claro.
    
    Debes:
    1. Analizar la salida JSONL del Agente de Productos: {productos_jsonl}
    2. Normalizar campos a categorías controladas:
       - tipo_dato → tipo_dato_norm
       - caracteristica → caracteristica_norm
       - meta_unidad → meta_unidad_norm
       - Separar meta numérica cuando sea inequívoco → meta_num
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