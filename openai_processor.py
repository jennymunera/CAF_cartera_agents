import os
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging para reducir verbosidad de Azure
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)

class OpenAIProcessor:
    """
    Procesador de Azure OpenAI para análisis de documentos.
    Procesa documentos y chunks usando 3 prompts específicos.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_client()
        
    def _setup_client(self):
        """Configura el cliente de Azure OpenAI usando variables de entorno."""
        try:
            # Obtener configuración del .env
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://OpenAI-Tech2.openai.azure.com/')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
            
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY no encontrada en variables de entorno")
            
            self.client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=endpoint,
                api_key=api_key
            )
            
            self.logger.info(f"Cliente Azure OpenAI configurado exitosamente - Endpoint: {endpoint}")
            
        except Exception as e:
            self.logger.error(f"Error configurando cliente Azure OpenAI: {str(e)}")
            raise
    
    def _get_document_prefix(self, document_content: Dict[str, Any]) -> str:
        """
        Extrae el prefijo del documento basado en el nombre del archivo.
        
        Args:
            document_content: Contenido del documento
            
        Returns:
            Prefijo del documento en mayúsculas (ej: 'IXP', 'ROP', 'INI')
        """
        # Obtener nombre del documento
        document_name = document_content.get('document_name', document_content.get('filename', ''))
        
        # Si es un chunk, obtener el nombre base
        if '_chunk_' in document_name:
            document_name = document_name.split('_chunk_')[0]
        
        # Extraer prefijo (primeras 3 letras antes del primer guión)
        if '-' in document_name:
            prefix = document_name.split('-')[0].upper()
        else:
            # Si no hay guión, tomar las primeras 3 letras
            prefix = document_name[:3].upper()
        
        return prefix
    
    def process_document_with_prompt1(self, document_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa documento con Prompt 1 - Análisis de Auditoría
        Solo procesa documentos que comiencen con 'IXP'
        
        Args:
            document_content: Contenido del documento cargado desde JSON
            
        Returns:
            Dict con resultados del procesamiento de auditoría o None si no aplica
        """
        
        try:
            # Verificar si el documento debe ser procesado con este prompt
            document_prefix = self._get_document_prefix(document_content)
            allowed_prefixes = ['IXP']
            
            if document_prefix not in allowed_prefixes:
                self.logger.info(f"⏭️ Saltando Prompt 1 para documento con prefijo '{document_prefix}' (solo procesa: {allowed_prefixes})")
                return None
                
            # Preparar contenido para el prompt
            content_text = document_content.get('content', '')
            
            # Extraer nombre del documento y chunk si existe
            base_document_name = document_content.get('document_name', document_content.get('filename', 'unknown'))
            chunk_index = document_content.get('chunk_index')
            
            if chunk_index is not None:
                document_name = f"{base_document_name}_chunk_{chunk_index:03d}"
            else:
                document_name = base_document_name
            
            self.logger.info(f"🤖 Procesando con Azure OpenAI: {document_name}")
            
            # Prompt de Auditoría - Exactamente igual al archivo prompt Auditoria.txt
            prompt = f"""
Eres un Analista experto en documentos de auditoría de proyectos del Banco CAF.
Tu tarea es extraer todas las variables del formato Auditorías a partir de documentos IXP, interpretar las opiniones de auditores externos y emitir un concepto final (Favorable / Favorable con reservas / Desfavorable) con justificación breve.

Debes trabajar con rigor: no inventes, usa sinónimos y variantes, y aplica un checklist antes de concluir que algo no existe.

Prioridad documental:

Solo documentos cuyo nombre inicia con IXP.

Si hay múltiples versiones, usa la más reciente y registra cambios en observacion.

CFA y CFX son códigos distintos, deben extraerse por separado.

Checklist anti–"NO EXTRAIDO":

Agota en este orden antes de marcar un campo como NO_EXTRAIDO:

Portada / primeras 2 páginas → Código CFA, CFX, Contrato del préstamo, Fecha del informe.

Índice → saltos a Opinión / Dictamen / Conclusión (variantes ES/PT/EN: "Opinion", "Unqualified opinion", "Parecer", "Sem ressalvas", "Conclusão", "Observación").

Secciones válidas de concepto → Opinión, Dictamen, Conclusión de auditoría.

Tablas administrativas → (solo si el campo es SSC, ver "Gating por fuente") Estado, Fecha de vencimiento, Fecha de cambio de estado.

Encabezados/pies → "Última revisión", "Actualización", "Fecha del informe".

Anexos / Carta de gerencia → posibles dictámenes del auditor.

Dónde buscar (por campo)

codigo_CFA: portada/primeras páginas. Variantes: "Código de operación CFA", "Op. CFA", "Operación CFA".

codigo_CFX: cabeceras o secciones administrativas/financieras. Variantes: "Código CFX", "Op. CFX".

opiniones (control interno / licitación / uso de recursos / unidad ejecutora): solo en Opinión/Dictamen/Conclusión → lenguaje sobre suficiencia/deficiencias, adquisiciones/procurement, conformidad vs plan, desempeño UGP.

fecha_ultima_revision: encabezados/pies ("Última revisión/Actualización").

Campos SSC (ver lista abajo): su evidencia se acepta desde SSC o tablas administrativas solo si el campo está marcado como SSC y la fuente está habilitada (ver Gating).

Sinónimos útiles

Opinión: dictamen, conclusiones, parecer, opinion, parecer, conclusão.

Sin salvedades: sin reservas, unqualified, sem ressalvas.

Entrega informe externo: entregado, recibido, presentado, publicado en SSC, dispensado.

Estado: estado, estatus, situación, condición.

Niveles de confianza (por campo)

Cada variable debe incluir un objeto con:
value (string/num/date o null), confidence (EXTRAIDO_DIRECTO | EXTRAIDO_INFERIDO | NO_EXTRAIDO), evidence (cita breve).

Normalización:

estado_informe_norm ∈ {{dispensado, normal, satisfecho, vencido, null}}

informe_externo_entregado_norm ∈ {{a tiempo, dispensado, vencido, null}}

concepto_*_norm ∈ {{Favorable, Favorable con reservas, Desfavorable, no se menciona}}

Heurísticas rápidas (few-shot):

"sin salvedades / no reveló deficiencias significativas" → Favorable.

"excepto por… / con salvedades" → Favorable con reservas.

"se sostienen deficiencias / incumplimiento" → Desfavorable.

Status auditoría:

Clasifica con base en el documento:

Disponible: entregado / existe.

No disponible: vencido / dispensado / no entregado.

No requerido: explícitamente no aplica.

Pendiente: aún no llega la fecha o está en trámite.

Gating por fuente (Auditoría):

Solo estos campos pueden usar SSC como fuente:

estado_informe_SSC

informe_auditoria_externa_se_entrego_SSC

fecha_vencimiento_SSC

fecha_cambio_estado_informe_SSC

status_auditoria_SSC

Todos los demás campos NO pueden usar SSC; deben extraerse de los documentos con prefijo IXP.

Si la evidencia de un campo depende de SSC y SSC está deshabilitado temporalmente, devuelve:

value=null, confidence="NO_EXTRAIDO"

Prohibido inferir campos no-SSC desde pistas de SSC.


Reglas de salida:

Genera JSON estructurado con todos los campos.

Si no hay evidencia → value=null, confidence="NO_EXTRAIDO", evidence=null.

concepto_rationale y texto_justificacion: siempre una cita corta (1–2 frases) de Opinión/Dictamen.

fecha_extraccion: fecha-hora actual del sistema.

nombre_archivo: documento fuente.

Esquema de salida JSON
{{
  "codigo_CFA": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "codigo_CFX": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "estado_informe_SSC": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "estado_informe_SSC_norm": "null",

  "informe_auditoria_externa_se_entrego_SSC": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "informe_auditoria_externa_se_entrego_SSC_norm": "null",

  "concepto_control_interno": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "concepto_control_interno_norm": "no se menciona",

  "concepto_licitacion": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "concepto_licitacion_norm": "no se menciona",

  "concepto_uso_recursos": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "concepto_uso_recursos_norm": "no se menciona",

  "concepto_unidad_ejecutora": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "concepto_unidad_ejecutora_norm": "no se menciona",

  "fecha_vencimiento_SSC": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "fecha_cambio_estado_informe_SSC": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "fecha_extraccion": "YYYY-MM-DD HH:MM",
  "fecha_ultima_revision": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "status_auditoria_SSC": "Pendiente",
  "nombre_archivo": "IXP_....pdf",

  "texto_justificacion": {{ "quote": null}}
}}

**DOCUMENTO A ANALIZAR:**
{document_content.get('content', '')}

**METADATOS DEL DOCUMENTO:**
- Nombre: {document_content.get('filename', 'N/A')}
- Proyecto: {document_content.get('project_name', 'N/A')}
- Páginas: {document_content.get('pages', 'N/A')}

**INSTRUCCIONES FINALES:**
1. Analiza el documento y extrae información de auditoría
2. Responde ÚNICAMENTE con JSON válido
3. NO incluyas texto adicional antes o después del JSON
4. Asegúrate de que todas las comillas estén correctamente escapadas
5. Si no encuentras información, usa arrays vacíos []
6. Verifica que el JSON sea válido antes de responder
            """
            
            # Llamada a Azure OpenAI
            response = self.client.chat.completions.create(
                model=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4'),
                messages=[
                    {"role": "system", "content": "Eres un Analista experto en documentos de auditoría. Tu tarea es extraer información específica de documentos de auditoría siguiendo un formato estructurado y emitiendo conceptos normalizados para entregar en formato JSON lo solicitado."},
                    {"role": "user", "content": f"{prompt}\n\nDocumento:\n{content_text}"}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            # Extraer respuesta
            ai_response = response.choices[0].message.content
            
            # Imprimir respuesta para verificación
            print(f"\n{'='*60}")
            print(f"RESPUESTA DE AZURE OPENAI PARA: {document_name}")
            print(f"{'='*60}")
            print(ai_response)
            print(f"{'='*60}\n")
            
            # Parsear JSON de la respuesta del LLM
            try:
                # Limpiar la respuesta primero
                cleaned_response = ai_response.strip()
                
                # Remover bloques de código markdown si existen
                if '```json' in cleaned_response:
                    start = cleaned_response.find('```json') + 7
                    end = cleaned_response.find('```', start)
                    if end != -1:
                        cleaned_response = cleaned_response[start:end].strip()
                elif '```' in cleaned_response:
                    start = cleaned_response.find('```') + 3
                    end = cleaned_response.find('```', start)
                    if end != -1:
                        cleaned_response = cleaned_response[start:end].strip()
                
                # Extraer JSON de la respuesta
                json_start = cleaned_response.find('{')
                json_end = cleaned_response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_content = cleaned_response[json_start:json_end]
                    
                    # Limpiar caracteres problemáticos
                    json_content = json_content.replace('\n', ' ').replace('\t', ' ')
                    json_content = ' '.join(json_content.split())  # Normalizar espacios
                    
                    # Intentar parsear JSON
                    try:
                        parsed_json = json.loads(json_content)
                    except json.JSONDecodeError as parse_error:
                        # Intentar reparar JSON común
                        self.logger.warning(f"⚠️ Intentando reparar JSON para {document_name}: {str(parse_error)}")
                        
                        # Reparaciones comunes
                        repaired_json = json_content
                        
                        # Agregar coma faltante antes de closing brace si es necesario
                        if parse_error.msg == "Expecting ',' delimiter":
                            pos = parse_error.pos
                            if pos < len(repaired_json) and repaired_json[pos-1:pos+1] in ['"\n', '" }', '"\t']:
                                repaired_json = repaired_json[:pos] + ',' + repaired_json[pos:]
                        
                        # Remover comas finales
                        repaired_json = repaired_json.replace(',}', '}').replace(',]', ']')
                        
                        # Intentar parsear JSON reparado
                        try:
                            parsed_json = json.loads(repaired_json)
                            self.logger.info(f"✅ JSON reparado exitosamente para {document_name}")
                        except json.JSONDecodeError:
                            # Si aún falla, crear estructura mínima con el esquema correcto
                             self.logger.warning(f"⚠️ Creando estructura JSON mínima para {document_name}")
                             parsed_json = {
                                 "codigo_CFA": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "codigo_CFX": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "estado_informe_SSC": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "estado_informe_SSC_norm": "null",
                                 "informe_auditoria_externa_se_entrego_SSC": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "informe_auditoria_externa_se_entrego_SSC_norm": "null",
                                 "concepto_control_interno": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "concepto_control_interno_norm": "no se menciona",
                                 "concepto_licitacion": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "concepto_licitacion_norm": "no se menciona",
                                 "concepto_uso_recursos": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "concepto_uso_recursos_norm": "no se menciona",
                                 "concepto_unidad_ejecutora": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "concepto_unidad_ejecutora_norm": "no se menciona",
                                 "fecha_vencimiento_SSC": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "fecha_cambio_estado_informe_SSC": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                 "fecha_ultima_revision": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                                 "status_auditoria": "Pendiente",
                                 "nombre_archivo": document_name,
                                 "texto_justificacion": {"quote": None},
                                 "observacion": None,
                                 "concepto_final": "Favorable",
                                 "concepto_rationale": {"quote": None}
                             }
                    
                    # Guardar JSON en subcarpeta LLM_output/Auditoria
                    project_name = document_content.get('project_name', 'unknown')
                    llm_output_dir = os.path.join("output_docs", project_name, "LLM_output", "Auditoria")
                    os.makedirs(llm_output_dir, exist_ok=True)
                    
                    # Crear nombre de archivo incluyendo chunk si aplica
                    base_name = os.path.splitext(base_document_name)[0]
                    if chunk_index is not None:
                        json_filename = f"{base_name}_chunk_{chunk_index:03d}_auditoria.json"
                    else:
                        json_filename = f"{base_name}_auditoria.json"
                    json_path = os.path.join(llm_output_dir, json_filename)
                    
                    # Guardar JSON parseado
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(parsed_json, f, indent=2, ensure_ascii=False)
                    
                    self.logger.info(f"💾 JSON guardado en: {json_path}")
                    
                else:
                    self.logger.warning(f"⚠️ No se pudo extraer JSON válido de la respuesta para {document_name}")
                    parsed_json = None
                    json_path = None
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Error parseando JSON para {document_name}: {str(e)}")
                parsed_json = None
                json_path = None
            except Exception as e:
                self.logger.error(f"❌ Error guardando JSON para {document_name}: {str(e)}")
                parsed_json = None
                json_path = None
            
            # Resultado estructurado
            result = {
                "prompt_type": "prompt_1_auditoria",
                "document_name": document_name,
                "processed_at": datetime.now().isoformat(),
                "prompt_used": prompt,
                "ai_response": ai_response,
                "parsed_json": parsed_json,
                "json_saved_path": json_path,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "status": "completed"
            }
            
            self.logger.info(f"✅ Prompt 1 procesado exitosamente - Tokens: {result['tokens_used']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error en Prompt 1 para {document_name}: {str(e)}")
            raise
    
    def process_document_with_prompt2(self, document_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa documento con Prompt 2 - Análisis de Productos
        Solo procesa documentos que comiencen con 'ROP', 'INI', 'DEC', 'IFS'
        
        Args:
            document_content: Contenido del documento JSON
            
        Returns:
            Dict con resultado del procesamiento o None si no aplica
        """
        # Verificar si el documento debe ser procesado con este prompt
        document_prefix = self._get_document_prefix(document_content)
        allowed_prefixes = ['ROP', 'INI', 'DEC', 'IFS']
        
        if document_prefix not in allowed_prefixes:
            self.logger.info(f"⏭️ Saltando Prompt 2 para documento con prefijo '{document_prefix}' (solo procesa: {allowed_prefixes})")
            return None
            
        # Extraer información del documento
        document_name = document_content.get('document_name') or document_content.get('filename', 'unknown')
        chunk_index = document_content.get('chunk_index')
        
        # Crear nombre descriptivo para logs
        if chunk_index is not None:
            display_name = f"{document_name}_chunk_{chunk_index:03d}"
        else:
            display_name = document_name
            
        self.logger.info(f"🤖 Procesando con Prompt 2 (Productos): {display_name}")
        
        # Prompt específico para análisis de productos - Exactamente igual al archivo prompt Productos.txt
        prompt_productos = f"""
Eres un Analista de Cartera experto en proyectos CAF.
Debes identificar todos los productos comprometidos en el proyecto y generar las filas solicitadas por cada producto, separando meta numérica y unidad, normalizando campos y dejando claro el estado de extracción.

Importante: no emites concepto final.

Prioridad documental:

Jerarquía: ROP > INI > DEC > IFS > Anexo Excel (si lo cita el índice).

En duplicados: usar la versión más reciente; si cambian valores, registrar en observacion.

Checklist anti–"NO_EXTRAIDO":

Tablas/Matrices → "Matriz de Indicadores", "Marco Lógico", "Metas físicas".

Narrativo → "Resultados esperados", "Componentes", "Seguimiento de indicadores" (IFS).

Anexos/Excel → cuando estén citados en índice.

Encabezados/pies → "Última revisión/Actualización".

Dónde buscar (por campo):

Código CFA / CFX: portada, primeras páginas, marcos lógicos, carátulas.

Descripción de producto: títulos/filas en matrices, POA, componentes, IFS.

Meta del producto / Meta unidad: columnas de metas → separa número/unidad (230 km → meta_num=230, meta_unidad=km).

Fuente del indicador: columna/nota "Fuente" (ROP, INI, DEC, IFS, SSC).

Fecha cumplimiento de meta: "Fecha meta", "Fecha de cumplimiento", "Plazo".

Tipo de dato: pendiente/proyectado/realizado (claves: programado, estimado, alcanzado).

Característica: {{administración, capacitación, fortalecimiento institucional, infraestructura}}.

Check_producto: "Sí" si corresponde inequívocamente a producto (no resultado).

Fecha última revisión: encabezados/pies.

Reglas especiales:

Validar producto vs resultado → no confundir.

Acumulado vs período → si es acumulativo, no dupliques registros.

Idiomas/formatos → aceptar ES/PT/EN y tablas rotadas.

Separación meta/unidad → reconocer variantes: "230 kilómetros", "1.500 personas", "100%", "2,5 ha".

No inventar → si falta meta o unidad, deja null.

Niveles de confianza:

Cada variable incluye:

value (dato literal o null).

confidence: EXTRAIDO_DIRECTO | EXTRAIDO_INFERIDO | NO_EXTRAIDO.

evidence: cita breve literal o cercana.


Normalización:

tipo_dato_norm ∈ {{pendiente, proyectado, realizado, null}}.

caracteristica_norm ∈ {{administracion, capacitacion, fortalecimiento institucional, infraestructura, null}}.

meta_num: número puro (ej. 230 de "230 km").

meta_unidad_norm: catálogo controlado (%, km, personas, m², m³, horas, hectáreas, kVA, MVA, l/s, galones, miles gal/día, toneladas, cantidad/año, miles m², etc.).

Few-shot (patrones típicos):

"230 km de carretera" → meta_num=230, meta_unidad_norm=km.

"1,500 personas capacitadas" → meta_num=1500, meta_unidad_norm=personas, caracteristica_norm=capacitacion.

"Resultado alcanzado" → tipo_dato_norm=realizado.

"Meta programada para 2024" → tipo_dato_norm=proyectado.

"Talleres de capacitación" → caracteristica_norm=capacitacion.

Reglas de salida:
Detecta todos los productos en el/los documento(s).
Por CADA producto identificado:
EMITE UNA (1) instancia del esquema completo "Esquema de salida JSON (por producto)".
No agregues ni elimines claves del esquema.
No mezcles datos de productos distintos en la misma instancia.
No incluyas texto adicional fuera de las líneas JSON.
Mantén el orden de las claves tal como está definido en "Esquema de salida JSON (por producto)".
Si no hay evidencia → value=null, confidence="NO_EXTRAIDO".

fecha_extraccion: fecha-hora actual del sistema.
nombre_archivo: documento fuente.

Esquema de salida JSON (por producto)
{{
  "codigo_CFA": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "codigo_CFX": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},

  "descripcion_producto": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},

  "meta_producto": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "meta_unidad": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "meta_num": null,
  "meta_unidad_norm": null,

  "fuente_indicador": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "fecha_cumplimiento_meta": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "tipo_dato": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "tipo_dato_norm": null,

  "caracteristica": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},
  "caracteristica_norm": null,

  "check_producto": "No",

  "fecha_extraccion": "YYYY-MM-DD HH:MM",
  "fecha_ultima_revision": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},

  "nombre_archivo": "ROP_....pdf",
 }}

**DOCUMENTO A ANALIZAR:**
{document_content.get('content', '')}

**METADATOS DEL DOCUMENTO:**
- Nombre: {document_content.get('filename', 'N/A')}
- Proyecto: {document_content.get('project_name', 'N/A')}
- Páginas: {document_content.get('pages', 'N/A')}

**INSTRUCCIONES FINALES:**
1. Analiza el documento y extrae información de productos
2. Responde ÚNICAMENTE con JSON válido
3. NO incluyas texto adicional antes o después del JSON
4. Asegúrate de que todas las comillas estén correctamente escapadas
5. Si no encuentras información, usa arrays vacíos []
6. Verifica que el JSON sea válido antes de responder
        """
        
        try:
            # Llamada a Azure OpenAI
            response = self.client.chat.completions.create(
                model=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4'),
                messages=[
                    {"role": "system", "content": "Eres un experto analista de cartera especializado en seguimiento de productos de proyectos."},
                    {"role": "user", "content": prompt_productos}
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            # Extraer respuesta del AI
            ai_response = response.choices[0].message.content.strip()
            
            # Parsear JSON de la respuesta
            try:
                # Limpiar la respuesta para extraer solo el JSON
                cleaned_response = ai_response.strip()
                
                # Remover bloques de código markdown si existen
                if '```json' in cleaned_response:
                    start = cleaned_response.find('```json') + 7
                    end = cleaned_response.find('```', start)
                    if end != -1:
                        cleaned_response = cleaned_response[start:end].strip()
                elif '```' in cleaned_response:
                    start = cleaned_response.find('```') + 3
                    end = cleaned_response.find('```', start)
                    if end != -1:
                        cleaned_response = cleaned_response[start:end].strip()
                
                # Intentar parsear múltiples objetos JSON o un array
                parsed_objects = []
                
                # Primero intentar como array JSON
                if cleaned_response.strip().startswith('['):
                    try:
                        parsed_objects = json.loads(cleaned_response)
                        if not isinstance(parsed_objects, list):
                            parsed_objects = [parsed_objects]
                        self.logger.info(f"📦 Array JSON parseado con {len(parsed_objects)} productos")
                    except json.JSONDecodeError:
                        self.logger.warning(f"⚠️ Fallo al parsear como array JSON")
                        parsed_objects = []
                
                # Si no es array, buscar múltiples objetos JSON separados
                if not parsed_objects:
                    # Buscar todos los objetos JSON en la respuesta
                    json_objects = []
                    start_pos = 0
                    
                    while True:
                        json_start = cleaned_response.find('{', start_pos)
                        if json_start == -1:
                            break
                            
                        # Encontrar el final del objeto JSON
                        brace_count = 0
                        json_end = json_start
                        
                        for i in range(json_start, len(cleaned_response)):
                            if cleaned_response[i] == '{':
                                brace_count += 1
                            elif cleaned_response[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if brace_count == 0:  # Objeto JSON completo encontrado
                            json_content = cleaned_response[json_start:json_end]
                            
                            # Limpiar caracteres problemáticos
                            json_content = json_content.replace('\n', ' ').replace('\t', ' ')
                            json_content = ' '.join(json_content.split())
                            
                            try:
                                parsed_obj = json.loads(json_content)
                                json_objects.append(parsed_obj)
                            except json.JSONDecodeError as parse_error:
                                # Intentar reparar JSON
                                repaired_json = json_content.replace(',}', '}').replace(',]', ']')
                                try:
                                    parsed_obj = json.loads(repaired_json)
                                    json_objects.append(parsed_obj)
                                    self.logger.info(f"✅ JSON reparado exitosamente")
                                except json.JSONDecodeError:
                                    self.logger.warning(f"⚠️ No se pudo parsear objeto JSON: {str(parse_error)}")
                            
                            start_pos = json_end
                        else:
                            break
                    
                    parsed_objects = json_objects
                
                # Si no se encontraron objetos válidos, crear uno mínimo
                if not parsed_objects:
                    self.logger.warning(f"⚠️ Creando estructura JSON mínima para {display_name}")
                    parsed_objects = [{
                        "codigo_CFA": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "codigo_CFX": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "descripcion_producto": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "meta_producto": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "meta_unidad": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "meta_num": None,
                        "meta_unidad_norm": None,
                        "fuente_indicador": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "fecha_cumplimiento_meta": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "tipo_dato": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "tipo_dato_norm": None,
                        "caracteristica": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "caracteristica_norm": None,
                        "check_producto": "No",
                        "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "fecha_ultima_revision": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "nombre_archivo": document_name
                    }]
                
                # Procesar cada objeto encontrado
                all_results = []
                project_name = document_content.get('project_name', 'unknown_project')
                base_document_name = document_name.replace('_chunk_', '_CHUNK_').split('_CHUNK_')[0]
                
                for idx, parsed_json in enumerate(parsed_objects):
                    self.logger.info(f"📋 Procesando producto {idx + 1} de {len(parsed_objects)}")
                    
                    # Crear nombre del archivo JSON para cada producto
                    if len(parsed_objects) > 1:
                        # Múltiples productos: agregar índice
                        if chunk_index is not None:
                            json_filename = f"{base_document_name}_chunk_{chunk_index:03d}_producto_{idx+1:03d}.json"
                        else:
                            json_filename = f"{base_document_name}_producto_{idx+1:03d}.json"
                    else:
                        # Un solo producto: usar nombre original
                        if chunk_index is not None:
                            json_filename = f"{base_document_name}_chunk_{chunk_index:03d}_productos.json"
                        else:
                            json_filename = f"{base_document_name}_productos.json"
                    
                    # Crear directorio si no existe
                    llm_output_dir = os.path.join("output_docs", project_name, "LLM_output", "Productos")
                    os.makedirs(llm_output_dir, exist_ok=True)
                    
                    # Guardar archivo JSON
                    json_path = os.path.join(llm_output_dir, json_filename)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                    
                    self.logger.info(f"💾 Producto {idx + 1} guardado en: {json_path}")
                    
                    # Calcular tokens utilizados (dividir entre el número de productos)
                    total_tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                    tokens_per_product = total_tokens // len(parsed_objects) if len(parsed_objects) > 0 else total_tokens
                    
                    result = {
                        "prompt_type": "prompt_2_productos",
                        "document_name": display_name,
                        "product_index": idx + 1,
                        "total_products": len(parsed_objects),
                        "processed_at": datetime.now().isoformat(),
                        "json_output_path": json_path,
                        "tokens_used": tokens_per_product,
                        "status": "success",
                        "parsed_json": parsed_json
                    }
                    
                    all_results.append(result)
                
                self.logger.info(f"✅ Prompt 2 procesado exitosamente - {len(parsed_objects)} productos - Tokens: {total_tokens}")
                
                # Retornar el primer resultado para compatibilidad, pero con información de todos
                if all_results:
                    main_result = all_results[0].copy()
                    main_result["all_products"] = all_results
                    main_result["tokens_used"] = total_tokens  # Total de tokens
                    main_result["ai_response"] = ai_response
                    main_result["status"] = "completed"
                    return main_result
                else:
                    # Si no hay resultados, crear uno de error
                    return {
                        "prompt_type": "prompt_2_productos",
                        "document_name": display_name,
                        "processed_at": datetime.now().isoformat(),
                        "ai_response": ai_response,
                        "parsed_json": None,
                        "json_saved_path": None,
                        "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else 0,
                        "status": "error",
                        "error": "No se pudieron parsear productos válidos"
                    }
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Error parseando JSON: {str(e)}")
                return {
                    "prompt_type": "prompt_2_productos",
                    "document_name": display_name,
                    "processed_at": datetime.now().isoformat(),
                    "ai_response": ai_response,
                    "parsed_json": None,
                    "json_saved_path": None,
                    "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else 0,
                    "status": "error",
                    "error": f"Error parseando JSON: {str(e)}"
                }
            
        except Exception as e:
            self.logger.error(f"❌ Error en Prompt 2 (Productos): {str(e)}")
            raise
    
    def process_document_with_prompt3(self, document_content: Dict[str, Any], document_name: str = None, chunk_index: int = None) -> Dict[str, Any]:
        """
        Procesa documento con Prompt 3 - Análisis de Desembolsos
        Solo procesa documentos que comiencen con 'ROP', 'INI', 'DEC'
        
        Args:
            document_content: Contenido del documento JSON
            document_name: Nombre del documento (opcional)
            chunk_index: Índice del chunk (opcional)
            
        Returns:
            Dict con resultado del procesamiento o None si no aplica
        """
        # Verificar si el documento debe ser procesado con este prompt
        document_prefix = self._get_document_prefix(document_content)
        allowed_prefixes = ['ROP', 'INI', 'DEC']
        
        if document_prefix not in allowed_prefixes:
            self.logger.info(f"⏭️ Saltando Prompt 3 para documento con prefijo '{document_prefix}' (solo procesa: {allowed_prefixes})")
            return None
            
        if document_name is None:
            document_name = document_content.get('filename', 'documento_desconocido')
            
        display_name = f"{document_name}_chunk_{chunk_index:03d}" if chunk_index is not None else document_name
        self.logger.info(f"💰 Procesando desembolsos: {display_name}")
        
        # Prompt específico para análisis de desembolsos - Exactamente igual al archivo prompt Desembolsos.txt
        prompt_desembolsos = f"""
Eres un analista de cartera experto en seguimiento de desembolsos de proyectos CAF. Debes extraer desembolsos del proyecto por parte de CAF, sin convertir moneda, deduplicando por período + moneda y normalizando la fuente.
No inventes: si no hay evidencia suficiente, deja value=null y confidence="NO_EXTRAIDO".

Prioridad documental:

Jerarquía: ROP > INI > DEC.

Proyectados: buscar primero en Cronograma/Programación/Calendario (ROP/INI); si no hay, usar DEC.

Realizados: "Detalle/Estado de desembolsos", EEFF o narrativa (en cualquier documento).

En duplicados/versiones: usar la versión más reciente y registrar cambios en observacion (periodificación, montos, moneda, fuente, documento).

Checklist anti–"NO_EXTRAIDO" (agotar en orden)

Tablas: cronograma/estado/flujo de caja.

Columnas típicas: Fecha/Período | Monto | Moneda | Fuente/Tipo (+ "Equivalente USD" si existe).

Narrativa/EEFF: "Desembolsos efectuados/realizados/pagos ejecutados/transferencias realizadas".

Encabezados/pies: "Última revisión/Actualización/Versión".

Si tras agotar el checklist no hay evidencia para un campo específico, deja ese campo como NO_EXTRAIDO.
Pero si existen período y monto, emite el registro.


Dónde buscar (por campo):

Código de operación (CFX): portada/primeras páginas, cabecera del cronograma, secciones administrativas. Variantes: "CFX", "Código CFX", "Operación CFX", "Op. CFX".

Fecha de desembolso (período):

"Detalle/Estado de desembolsos", "Desembolsos efectuados/realizados", "Pagos ejecutados", "Transferencias realizadas", "Cronograma/Programación/Calendario de desembolsos", "Flujo de caja", "Proyección financiera".

Formatos válidos: YYYY, YYYY-MM, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY, Enero 2023, Q1 2023, Trimestre 1, Semestre 2, 2024-06.

Monto desembolsado CAF (monto_original): columna "Monto/Importe/Desembolsado/Valor/Total" (extrae número puro, sin símbolos y sin conversiones).

moneda: columna "Moneda" o heredar desde título/cabecera/leyenda de la tabla (p. ej. "(USD)", "Moneda: PEN") → entonces confidence="EXTRAIDO_INFERIDO" con evidencia de la leyenda.

monto_usd: solo si hay columna/registro explícito en USD o "Equivalente USD". No crear fila aparte en USD si ya existe la moneda original para el mismo período/tipo_registro (ver DEDUP).

Fuente CAF (fuente_etiqueta): etiqueta clara: "CAF Realizado", "Proyectado (Cronograma)", "Anticipo", "Pago directo", "Reembolso", con referencia de documento (p. ej. "(ROP)", "(INI)", "(DEC)" si está indicada).

Fecha de última revisión: encabezados/pies o notas ("Última revisión/Actualización/Fecha del documento/Versión/Modificado/Revisado el").

Nombre del archivo revisado: documento del que proviene el dato final.



Reglas de extracción y deduplicación:

Tabla-primero: prioriza tablas sobre narrativa.

No convertir moneda ni inferir fechas/moneda no sustentadas.

Prioriza moneda original; conserva monto_usd solo si viene explícito en la tabla (o si no hay registro en moneda original).

DEDUP estricta: no repitas mismo período + misma moneda + mismo tipo_registro. Conserva la fila más reciente/consistente y registra diferencias en observacion.

Ambigüedad de fecha: usa el literal (Q1 2025, 2026, etc.); no expandas a fechas exactas.

tipo_registro_norm ∈ {{proyectado, realizado}} (derivado de la sección/tabla/fuente).


Niveles de confianza (por campo):

Cada variable se representa como objeto con:

value (string/num o null),

confidence: EXTRAIDO_DIRECTO | EXTRAIDO_INFERIDO | NO_EXTRAIDO,

evidence (cita breve literal o cercana),


Normalización:

fuente_norm (opcional) → {{CAF Realizado, Proyectado (Cronograma), Anticipo, Pago directo, Reembolso, Transferencia, Giro, null}}.

tipo_registro_norm → {{proyectado, realizado}}.

moneda → mantener código/etiqueta tal como aparece (no normalizar a ISO si no está explícito, salvo equivalentes claros como "US$"→"USD").


Reglas de salida (cardinalidad y formato)

Cardinalidad

Detecta todos los registros de desembolso en el/los documento(s).
Por CADA registro identificado (unidad mínima = período/fecha × moneda × tipo_registro):
EMITE UNA (1) instancia del esquema completo "Esquema de salida JSON (por registro)".
No agregues ni elimines claves.
Si falta evidencia en una clave: value=null, confidence="NO_EXTRAIDO", evidence=null.
No incluyas texto adicional fuera del JSON.
Mantén el orden de claves como en el esquema.


Few-shot compacto (referencial, NO generar)
- Propósito: ilustrar patrones de extracción. NO son datos reales ni deben emitirse.
- Cardinalidad del ejemplo: 1 entrada de tabla → 1 (una) fila JSON.
- Prohibido: crear filas adicionales por el mismo ejemplo. 

Ejemplo A (realizado en USD) — NO EMITIR
Entrada de tabla (una fila):
  2024-06 | USD 1,250,000 | CAF Realizado (DEC)
Salida esperada (una sola fila JSON):
  tipo_registro_norm="realizado";
  fecha_desembolso.value="2024-06";
  monto_original.value=1250000; moneda.value="USD";
  monto_usd.value=1250000 (solo si no existe fila en moneda original);
  fuente_etiqueta.value="CAF Realizado (DEC)".

Ejemplo B (proyectado en moneda local con columna USD) — NO EMITIR
Entrada de tabla (una fila):
  Q1 2025 | PEN 3,500,000 | Equivalente USD 920,000 | Proyectado (Cronograma ROP)
Salida esperada (una sola fila JSON):
  tipo_registro_norm="proyectado";
  fecha_desembolso.value="Q1 2025";
  monto_original.value=3500000; moneda.value="PEN";
  monto_usd.value=920000 (si tu esquema conserva columna explícita);
  fuente_norm="Proyectado (Cronograma)".


Esquema de salida JSON (por registro)
{{
  "codigo_CFX": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "tipo_registro": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},
  "tipo_registro_norm": null,  // proyectado | realizado

  "fecha_desembolso": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "monto_original": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "moneda": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "monto_usd": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null}},

  "fuente_etiqueta": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},

  "fuente_norm": null,  // CAF Realizado | Proyectado (Cronograma) | Anticipo | Pago directo | Reembolso | Transferencia | Giro | null

  "fecha_extraccion": "YYYY-MM-DD HH:MM",

  "fecha_ultima_revision": {{ "value": null, "confidence": "NO_EXTRAIDO", "evidence": null }},

  "nombre_archivo": "ROP_....pdf"
}}

**DOCUMENTO A ANALIZAR:**
{document_content.get('content', '')}

**METADATOS DEL DOCUMENTO:**
- Nombre: {document_content.get('filename', 'N/A')}
- Proyecto: {document_content.get('project_name', 'N/A')}
- Páginas: {document_content.get('pages', 'N/A')}

**INSTRUCCIONES FINALES:**
1. Analiza el documento y extrae información de desembolsos
2. Responde ÚNICAMENTE con JSON válido
3. NO incluyas texto adicional antes o después del JSON
4. Asegúrate de que todas las comillas estén correctamente escapadas
5. Si no encuentras información, usa arrays vacíos []
6. Verifica que el JSON sea válido antes de responder
        """
        
        try:
            # Llamada a Azure OpenAI
            response = self.client.chat.completions.create(
                model=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4'),
                messages=[
                    {"role": "system", "content": "Eres un experto analista de cartera especializado en seguimiento de desembolsos de proyectos."},
                    {"role": "user", "content": prompt_desembolsos}
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            # Extraer respuesta del AI
            ai_response = response.choices[0].message.content.strip()
            
            # Parsear JSON de la respuesta - Manejo de múltiples objetos
            try:
                # Limpiar la respuesta para extraer JSON
                cleaned_response = ai_response.strip()
                
                # Remover bloques de código markdown si existen
                if '```json' in cleaned_response:
                    start = cleaned_response.find('```json') + 7
                    end = cleaned_response.find('```', start)
                    if end != -1:
                        cleaned_response = cleaned_response[start:end].strip()
                elif '```' in cleaned_response:
                    start = cleaned_response.find('```') + 3
                    end = cleaned_response.find('```', start)
                    if end != -1:
                        cleaned_response = cleaned_response[start:end].strip()
                
                parsed_objects = []
                
                # Intentar parsear como array primero
                if cleaned_response.strip().startswith('['):
                    try:
                        array_data = json.loads(cleaned_response)
                        if isinstance(array_data, list):
                            parsed_objects = array_data
                            self.logger.info(f"📋 Parseado como array: {len(parsed_objects)} desembolsos")
                    except json.JSONDecodeError:
                        pass
                
                # Si no es array, buscar múltiples objetos JSON separados
                if not parsed_objects:
                    # Buscar todos los objetos JSON en la respuesta
                    json_objects = []
                    start_pos = 0
                    
                    while True:
                        json_start = cleaned_response.find('{', start_pos)
                        if json_start == -1:
                            break
                        
                        # Encontrar el final del objeto JSON
                        brace_count = 0
                        json_end = json_start
                        
                        for i in range(json_start, len(cleaned_response)):
                            if cleaned_response[i] == '{':
                                brace_count += 1
                            elif cleaned_response[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if brace_count == 0:
                            json_content = cleaned_response[json_start:json_end]
                            
                            # Limpiar y normalizar
                            json_content = json_content.replace('\n', ' ').replace('\t', ' ')
                            json_content = ' '.join(json_content.split())
                            
                            try:
                                parsed_obj = json.loads(json_content)
                                json_objects.append(parsed_obj)
                            except json.JSONDecodeError as parse_error:
                                # Intentar reparar JSON
                                repaired_json = json_content.replace(',}', '}').replace(',]', ']')
                                try:
                                    parsed_obj = json.loads(repaired_json)
                                    json_objects.append(parsed_obj)
                                    self.logger.info(f"✅ JSON reparado exitosamente")
                                except json.JSONDecodeError:
                                    self.logger.warning(f"⚠️ No se pudo parsear objeto JSON: {str(parse_error)}")
                            
                            start_pos = json_end
                        else:
                            break
                    
                    parsed_objects = json_objects
                
                # Si no se encontraron objetos válidos, crear uno mínimo
                if not parsed_objects:
                    self.logger.warning(f"⚠️ Creando estructura JSON mínima para desembolsos")
                    parsed_objects = [{
                        "codigo_CFX": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "tipo_registro": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "tipo_registro_norm": None,
                        "fecha_desembolso": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "monto_original": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "moneda": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "monto_usd": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "fuente_etiqueta": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "fuente_norm": None,
                        "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "fecha_ultima_revision": {"value": None, "confidence": "NO_EXTRAIDO", "evidence": None},
                        "nombre_archivo": document_name
                    }]
                
                # Procesar cada objeto encontrado
                all_results = []
                project_name = document_content.get('project_name', 'unknown_project')
                base_document_name = document_name.replace('_chunk_', '_CHUNK_').split('_CHUNK_')[0]
                
                for idx, parsed_json in enumerate(parsed_objects):
                    self.logger.info(f"💰 Procesando desembolso {idx + 1} de {len(parsed_objects)}")
                    
                    # Crear nombre del archivo JSON para cada desembolso
                    if len(parsed_objects) > 1:
                        # Múltiples desembolsos: agregar índice
                        if chunk_index is not None:
                            json_filename = f"{base_document_name}_chunk_{chunk_index:03d}_desembolso_{idx+1:03d}.json"
                        else:
                            json_filename = f"{base_document_name}_desembolso_{idx+1:03d}.json"
                    else:
                        # Un solo desembolso: usar nombre original
                        if chunk_index is not None:
                            json_filename = f"{base_document_name}_chunk_{chunk_index:03d}_desembolsos.json"
                        else:
                            json_filename = f"{base_document_name}_desembolsos.json"
                    
                    # Crear directorio si no existe
                    llm_output_dir = os.path.join("output_docs", project_name, "LLM_output", "Desembolsos")
                    os.makedirs(llm_output_dir, exist_ok=True)
                    
                    # Guardar archivo JSON
                    json_path = os.path.join(llm_output_dir, json_filename)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                    
                    self.logger.info(f"💾 Desembolso {idx + 1} guardado en: {json_path}")
                    
                    # Calcular tokens utilizados (dividir entre el número de desembolsos)
                    total_tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                    tokens_per_disbursement = total_tokens // len(parsed_objects) if len(parsed_objects) > 0 else total_tokens
                    
                    result = {
                        "prompt_type": "prompt_3_desembolsos",
                        "document_name": display_name,
                        "disbursement_index": idx + 1,
                        "total_disbursements": len(parsed_objects),
                        "processed_at": datetime.now().isoformat(),
                        "json_output_path": json_path,
                        "tokens_used": tokens_per_disbursement,
                        "status": "success",
                        "parsed_json": parsed_json
                    }
                    
                    all_results.append(result)
                
                self.logger.info(f"✅ Prompt 3 procesado exitosamente - {len(parsed_objects)} desembolsos - Tokens: {total_tokens}")
                
                # Retornar el primer resultado para compatibilidad, pero con información de todos
                if all_results:
                    main_result = all_results[0].copy()
                    main_result["all_disbursements"] = all_results
                    main_result["tokens_used"] = total_tokens  # Total de tokens
                    main_result["ai_response"] = ai_response
                    main_result["status"] = "completed"
                    return main_result
                else:
                    # Si no hay resultados, crear uno de error
                    return {
                        "prompt_type": "prompt_3_desembolsos",
                        "document_name": display_name,
                        "processed_at": datetime.now().isoformat(),
                        "ai_response": ai_response,
                        "parsed_json": None,
                        "json_saved_path": None,
                        "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else 0,
                        "status": "error",
                        "error": "No se pudieron parsear desembolsos válidos"
                    }
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Error parseando JSON para {display_name}: {str(e)}")
                return {
                    "prompt_type": "prompt_3_desembolsos",
                    "document_name": display_name,
                    "processed_at": datetime.now().isoformat(),
                    "ai_response": ai_response,
                    "parsed_json": None,
                    "json_saved_path": None,
                    "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else 0,
                    "status": "error",
                    "error": f"Error parseando JSON: {str(e)}"
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error procesando con Prompt 3 - {display_name}: {str(e)}")
            return {
                "prompt_type": "prompt_3_desembolsos",
                "document_name": display_name,
                "processed_at": datetime.now().isoformat(),
                "status": "processing_error",
                "error": str(e)
            }
    
    def process_single_document(self, document_path: str, project_name: str) -> List[Dict[str, Any]]:
        """
        Procesa un documento individual con el prompt de resumen (solo para prueba).
        
        Args:
            document_path: Ruta al archivo JSON del documento
            project_name: Nombre del proyecto
            
        Returns:
            Lista con resultado del prompt de resumen
        """
        self.logger.info(f"📄 Procesando documento: {document_path}")
        
        try:
            # Cargar contenido del documento
            with open(document_path, 'r', encoding='utf-8') as f:
                document_content = json.load(f)
            
            # Agregar nombre del proyecto al contenido del documento
            document_content['project_name'] = project_name
            
            results = []
            
            # Extraer document_name y chunk_index del contenido o path
            document_name = document_content.get('document_name', document_content.get('filename', Path(document_path).stem))
            chunk_index = None
            if '_chunk_' in str(document_path):
                # Extraer índice del chunk del nombre del archivo
                chunk_match = re.search(r'_chunk_(\d+)', str(document_path))
                if chunk_match:
                    chunk_index = int(chunk_match.group(1))
            
            # Procesar con los tres prompts
            result1 = self.process_document_with_prompt1(document_content)
            result2 = self.process_document_with_prompt2(document_content)
            result3 = self.process_document_with_prompt3(document_content, document_name, chunk_index)
            
            # Solo agregar resultados que no sean None
            if result1 is not None:
                results.append(result1)
            if result2 is not None:
                results.append(result2)
            if result3 is not None:
                results.append(result3)
            
            self.logger.info(f"✅ Documento procesado con filtros de prefijo aplicados: {document_path}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error procesando documento {document_path}: {str(e)}")
            raise
    
    def process_project_documents(self, project_name: str) -> Dict[str, Any]:
        """
        Procesa todos los documentos de un proyecto.
        
        Args:
            project_name: Nombre del proyecto (ej: CFA009660)
            
        Returns:
            Dict con todos los resultados procesados
        """
        project_path = os.path.join("output_docs", project_name)
        self.logger.info(f"🚀 Iniciando procesamiento OpenAI para proyecto: {project_name}")
        
        all_results = {
            "project_name": project_name,
            "processed_at": datetime.now().isoformat(),
            "documents": [],
            "chunks": [],
            "summary": {
                "total_documents": 0,
                "total_chunks": 0,
                "total_prompts_processed": 0
            }
        }
        
        try:
            # Procesar documentos DI
            di_path = os.path.join(project_path, 'DI')
            if os.path.exists(di_path):
                for filename in os.listdir(di_path):
                    if filename.endswith('.json'):
                        doc_path = os.path.join(di_path, filename)
                        doc_results = self.process_single_document(doc_path, project_name)
                        all_results["documents"].extend(doc_results)
                        all_results["summary"]["total_documents"] += 1
            
            # Procesar chunks
            chunks_path = os.path.join(project_path, 'chunks')
            if os.path.exists(chunks_path):
                for filename in os.listdir(chunks_path):
                    if filename.endswith('.json'):
                        chunk_path = os.path.join(chunks_path, filename)
                        chunk_results = self.process_single_document(chunk_path, project_name)
                        all_results["chunks"].extend(chunk_results)
                        all_results["summary"]["total_chunks"] += 1
            
            # Calcular total de prompts procesados (3 prompts por documento/chunk)
            total_prompts = (all_results["summary"]["total_documents"] + 
                           all_results["summary"]["total_chunks"]) * 3
            all_results["summary"]["total_prompts_processed"] = total_prompts
            
            self.logger.info(f"✅ Proyecto procesado - Docs: {all_results['summary']['total_documents']}, "
                           f"Chunks: {all_results['summary']['total_chunks']}, "
                           f"Prompts: {total_prompts}")
            
            # Concatenar archivos JSON de auditoría
            self.concatenate_auditoria_jsons(project_name)
            
            # Concatenar archivos JSON de productos
            self.concatenate_productos_jsons(project_name)
            
            # Concatenar archivos JSON de desembolsos
            self.concatenate_desembolsos_jsons(project_name)
            
            return all_results
            
        except Exception as e:
            self.logger.error(f"Error procesando proyecto {project_name}: {str(e)}")
            raise
    
    def concatenate_results(self, results: Dict[str, Any], output_path: str) -> str:
        """
        Concatena todos los resultados en un JSON final.
        
        Args:
            results: Resultados del procesamiento
            output_path: Ruta donde guardar el resultado final
            
        Returns:
            Ruta del archivo generado
        """
        self.logger.info(f"📋 Concatenando resultados finales")
        
        try:
            # TODO: Implementar lógica de concatenación específica
            # Por ahora, guardamos todos los resultados tal como están
            
            final_output = {
                "processing_metadata": {
                    "processed_at": datetime.now().isoformat(),
                    "processor_version": "1.0.0",
                    "total_items_processed": len(results.get("documents", [])) + len(results.get("chunks", []))
                },
                "project_info": {
                    "name": results.get("project_name", "unknown"),
                    "summary": results.get("summary", {})
                },
                "processed_documents": results.get("documents", []),
                "processed_chunks": results.get("chunks", []),
                "consolidated_analysis": {
                    "note": "[PENDIENTE - Implementar lógica de consolidación]",
                    "key_findings": [],
                    "cross_document_insights": [],
                    "recommendations": []
                }
            }
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Guardar resultado final
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_output, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Resultados concatenados guardados en: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error concatenando resultados: {str(e)}")
            raise
    
    def concatenate_auditoria_jsons(self, project_name: str) -> str:
        """
        Concatena todos los archivos JSON de auditoría en un solo archivo auditoria.json
        
        Args:
            project_name: Nombre del proyecto
            
        Returns:
            Ruta del archivo concatenado generado
        """
        self.logger.info(f"🔗 Concatenando archivos JSON de auditoría para proyecto {project_name}")
        
        try:
            # Rutas de las carpetas
            llm_output_dir = os.path.join("output_docs", project_name, "LLM_output", "Auditoria")
            output_file = os.path.join("output_docs", project_name, "auditoria.json")
            
            # Verificar que existe la carpeta LLM_output
            if not os.path.exists(llm_output_dir):
                self.logger.warning(f"⚠️ No existe la carpeta LLM_output: {llm_output_dir}")
                return None
            
            # Buscar todos los archivos JSON de auditoría
            auditoria_files = []
            for filename in os.listdir(llm_output_dir):
                if filename.endswith('_auditoria.json'):
                    file_path = os.path.join(llm_output_dir, filename)
                    auditoria_files.append((filename, file_path))
            
            if not auditoria_files:
                self.logger.warning(f"⚠️ No se encontraron archivos de auditoría en {llm_output_dir}")
                return None
            
            # Leer y concatenar todos los archivos JSON
            concatenated_data = {
                "metadata": {
                    "project_name": project_name,
                    "concatenated_at": datetime.now().isoformat(),
                    "total_files": len(auditoria_files),
                    "processor_version": "1.0.0"
                },
                "auditoria_results": []
            }
            
            for filename, file_path in sorted(auditoria_files):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # Agregar metadata del archivo
                    result_entry = {
                        "source_file": filename,
                        "document_name": filename.replace('_auditoria.json', ''),
                        "data": json_data
                    }
                    
                    concatenated_data["auditoria_results"].append(result_entry)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ Error leyendo JSON {filename}: {str(e)}")
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Error procesando archivo {filename}: {str(e)}")
                    continue
            
            # Guardar archivo concatenado
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(concatenated_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Archivos de auditoría concatenados: {len(auditoria_files)} archivos → {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"❌ Error concatenando archivos de auditoría: {str(e)}")
            raise
    
    def concatenate_productos_jsons(self, project_name: str) -> str:
        """
        Concatena todos los archivos JSON de productos en un solo archivo productos.json
        
        Args:
            project_name: Nombre del proyecto
            
        Returns:
            Ruta del archivo concatenado generado
        """
        self.logger.info(f"🔗 Concatenando archivos JSON de productos para proyecto {project_name}")
        
        try:
            # Rutas de las carpetas
            llm_output_dir = os.path.join("output_docs", project_name, "LLM_output", "Productos")
            output_file = os.path.join("output_docs", project_name, "productos.json")
            
            # Verificar que existe la carpeta LLM_output
            if not os.path.exists(llm_output_dir):
                self.logger.warning(f"⚠️ No existe la carpeta LLM_output: {llm_output_dir}")
                return None
            
            # Buscar todos los archivos JSON de productos (tanto _productos.json como _producto_XXX.json)
            productos_files = []
            for filename in os.listdir(llm_output_dir):
                if filename.endswith('_productos.json') or '_producto_' in filename and filename.endswith('.json'):
                    file_path = os.path.join(llm_output_dir, filename)
                    productos_files.append((filename, file_path))
            
            if not productos_files:
                self.logger.warning(f"⚠️ No se encontraron archivos de productos en {llm_output_dir}")
                return None
            
            # Leer y concatenar todos los archivos JSON
            concatenated_data = {
                "metadata": {
                    "project_name": project_name,
                    "concatenated_at": datetime.now().isoformat(),
                    "total_files": len(productos_files),
                    "processor_version": "1.0.0"
                },
                "productos_results": []
            }
            
            for filename, file_path in sorted(productos_files):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # Agregar metadata del archivo
                    result_entry = {
                        "source_file": filename,
                        "document_name": filename.replace('_productos.json', ''),
                        "data": json_data
                    }
                    
                    concatenated_data["productos_results"].append(result_entry)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ Error leyendo JSON {filename}: {str(e)}")
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Error procesando archivo {filename}: {str(e)}")
                    continue
            
            # Aplicar deduplicación
            original_count = len(concatenated_data["productos_results"])
            concatenated_data["productos_results"] = self.deduplicate_productos(concatenated_data["productos_results"])
            unique_count = len(concatenated_data["productos_results"])
            
            # Actualizar metadata con información de deduplicación
            concatenated_data["metadata"]["total_unique_productos"] = unique_count
            concatenated_data["metadata"]["duplicates_removed"] = original_count - unique_count
            
            # Guardar archivo concatenado
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(concatenated_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Archivos de productos concatenados: {len(productos_files)} archivos → {output_file}")
            self.logger.info(f"📊 Deduplicación productos: {original_count} → {unique_count} ({original_count - unique_count} duplicados eliminados)")
            return output_file
            
        except Exception as e:
            self.logger.error(f"❌ Error concatenando archivos de productos: {str(e)}")
            raise
    
    def concatenate_desembolsos_jsons(self, project_name: str) -> str:
        """
        Concatena todos los archivos JSON de desembolsos en un solo archivo desembolsos.json
        
        Args:
            project_name: Nombre del proyecto
            
        Returns:
            Ruta del archivo concatenado generado
        """
        self.logger.info(f"🔗 Concatenando archivos JSON de desembolsos para proyecto {project_name}")
        
        try:
            # Rutas de las carpetas
            llm_output_dir = os.path.join("output_docs", project_name, "LLM_output", "Desembolsos")
            output_file = os.path.join("output_docs", project_name, "desembolsos.json")
            
            # Verificar que existe la carpeta LLM_output
            if not os.path.exists(llm_output_dir):
                self.logger.warning(f"⚠️ No existe la carpeta LLM_output: {llm_output_dir}")
                return None
            
            # Buscar todos los archivos JSON de desembolsos (tanto _desembolsos.json como _desembolso_XXX.json)
            desembolsos_files = []
            for filename in os.listdir(llm_output_dir):
                if filename.endswith('_desembolsos.json') or '_desembolso_' in filename and filename.endswith('.json'):
                    file_path = os.path.join(llm_output_dir, filename)
                    desembolsos_files.append((filename, file_path))
            
            if not desembolsos_files:
                self.logger.warning(f"⚠️ No se encontraron archivos de desembolsos en {llm_output_dir}")
                return None
            
            # Leer y concatenar todos los archivos JSON
            concatenated_data = {
                "metadata": {
                    "project_name": project_name,
                    "concatenated_at": datetime.now().isoformat(),
                    "total_files": len(desembolsos_files),
                    "processor_version": "1.0.0"
                },
                "desembolsos_results": []
            }
            
            for filename, file_path in sorted(desembolsos_files):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # Agregar metadata del archivo
                    result_entry = {
                        "source_file": filename,
                        "document_name": filename.replace('_desembolsos.json', ''),
                        "data": json_data
                    }
                    
                    concatenated_data["desembolsos_results"].append(result_entry)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ Error leyendo JSON {filename}: {str(e)}")
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Error procesando archivo {filename}: {str(e)}")
                    continue
            
            # Aplicar deduplicación
            original_count = len(concatenated_data["desembolsos_results"])
            concatenated_data["desembolsos_results"] = self.deduplicate_desembolsos(concatenated_data["desembolsos_results"])
            unique_count = len(concatenated_data["desembolsos_results"])
            
            # Actualizar metadata con información de deduplicación
            concatenated_data["metadata"]["total_unique_desembolsos"] = unique_count
            concatenated_data["metadata"]["duplicates_removed"] = original_count - unique_count
            
            # Guardar archivo concatenado
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(concatenated_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Archivos de desembolsos concatenados: {len(desembolsos_files)} archivos → {output_file}")
            self.logger.info(f"📊 Deduplicación desembolsos: {original_count} → {unique_count} ({original_count - unique_count} duplicados eliminados)")
            return output_file
            
        except Exception as e:
            self.logger.error(f"❌ Error concatenando archivos de desembolsos: {str(e)}")
            raise
    
    def deduplicate_productos(self, productos_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Elimina duplicados de la lista de productos basándose en descripción, meta y unidad
        
        Args:
            productos_list: Lista de productos a deduplicar
            
        Returns:
            Lista de productos únicos
        """
        seen = set()
        unique_productos = []
        
        for item in productos_list:
            data = item['data']
            # Clave única basada en descripción, meta y unidad
            desc_val = data.get('descripcion_producto', {}).get('value', '')
            meta_val = data.get('meta_producto', {}).get('value', '')
            unidad_val = data.get('meta_unidad', {}).get('value', '')
            
            # Convertir a string y normalizar
            desc_str = str(desc_val).strip().lower() if desc_val is not None else ''
            meta_str = str(meta_val).strip() if meta_val is not None else ''
            unidad_str = str(unidad_val).strip().lower() if unidad_val is not None else ''
            
            key = (desc_str, meta_str, unidad_str)
            
            if key not in seen and key != ('', '', ''):
                seen.add(key)
                unique_productos.append(item)
        
        return unique_productos
    
    def deduplicate_desembolsos(self, desembolsos_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Elimina duplicados de la lista de desembolsos basándose en monto, moneda y fecha
        
        Args:
            desembolsos_list: Lista de desembolsos a deduplicar
            
        Returns:
            Lista de desembolsos únicos
        """
        seen = set()
        unique_desembolsos = []
        
        for item in desembolsos_list:
            data = item['data']
            # Clave única basada en monto, moneda y fecha
            monto_val = data.get('monto_original', {}).get('value', '')
            moneda_val = data.get('moneda', {}).get('value', '')
            fecha_val = data.get('fecha_desembolso', {}).get('value', '')
            
            # Convertir a string y normalizar
            monto_str = str(monto_val).strip() if monto_val is not None else ''
            moneda_str = str(moneda_val).strip().upper() if moneda_val is not None else ''
            fecha_str = str(fecha_val).strip() if fecha_val is not None else ''
            
            key = (monto_str, moneda_str, fecha_str)
            
            if key not in seen and key != ('', '', ''):
                seen.add(key)
                unique_desembolsos.append(item)
        
        return unique_desembolsos