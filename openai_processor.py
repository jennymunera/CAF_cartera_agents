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
            
            # Prompt de Auditoría
            prompt = """Eres un Analista experto en documentos de auditoria, debes Extraer todas las variables del formato Auditorías priorizando archivos IXP, normalizando los campos categóricos y emitir un concepto final (Favorable / Favorable con reservas / Desfavorable) con justificación.

Prioridad documental: 

Solo documentos cuyo nombre inicia con IXP.

Si hay múltiples versiones, usa la más reciente y registra cambios en Observación.

Checklist anti–"NO EXTRAIDO" (agotar antes de rendirse): 

Portada / primeras 2 páginas → "Código de operación", CFA/CFX.

Índice → saltos a "Opinión", "Dictamen", "Conclusión".

Secciones válidas de concepto → Opinión, Opinión sin reserva/sin salvedades, Dictamen, Conclusión de auditoría (acepta variantes ES/PT/EN: "Opinion", "Unqualified opinion", "Parecer", "Sem ressalvas").

Tablas/seguimiento administrativo → Estado del informe, Fecha de vencimiento, Fecha de cambio de estado (según SSC o tabla del doc).

Encabezados/pies → "Última revisión/Actualización".

Anexos del auditor / "Carta de gerencia".

Elegir versión más reciente; Observación = campo: valor_anterior → valor_nuevo (doc_origen → doc_nuevo).

Dónde buscar (por campo): 

Código CFA: portada/primeras páginas ("Código de operación", "CFA", "codigo CFA").

código CFX: cerca de CFA, diferente al CFA, en cabeceras administrativas.

Estado del informe: tablas/seguimiento (normal, vencido, dispensado, satisfecho).

Si se entregó informe de auditoría externo: menciones explícitas de entrega/recepción/dispensa.

Concepto Control interno: solo en Opinión/Dictamen/Conclusión; frases sobre suficiencia/deficiencias de control interno.

Concepto licitación de proyecto: en Opinión/Dictamen; adquisiciones/contrataciones/procurement.

Concepto uso de recursos: en Opinión/Dictamen; conformidad/desvíos respecto al plan.

Concepto sobre unidad ejecutora: en Opinión/Dictamen; desempeño de la UGP.

Fecha de vencimiento / cambio de estado: tablas administrativas/SSC.

Fecha de extracción: ahora (fecha-hora del sistema).

Fecha de última revisión: encabezados/pies ("Última revisión/Actualización").

status auditoría: "disponible/ no disponible/ no requerido/ pendiente".

Nombre del archivo revisado: archivo base del dato final.

texto justificación: 1–2 frases de Opinión/Dictamen que sustenten los conceptos.

Observación: diferencias entre versiones.

Sinónimos útiles (flexibles)

Estado: estado, estatus, situación, condición.

Opinión: dictamen, conclusiones, parecer.

Entrega informe externo: entregado, recibido, presentado, publicado en SSC, dispensa.

Niveles de confianza (adjúntalos por campo): 

EXTRAIDO_DIRECTO (evidencia literal), EXTRAIDO_INFERIDO (sinónimo/contexto), NO_EXTRAIDO.
Formato por valor: valor|NIVEL_CONFIANZA.

Normalización + Concepto: 

estado_informe_norm ∈ {dispensado, normal, satisfecho, vencido} o null.

informe_externo_entregado_norm ∈ {a tiempo, dispensado, vencido} o null.

concepto_control_interno_norm, concepto_licitacion_norm, concepto_uso_recursos_norm, concepto_unidad_ejecutora_norm ∈ {Favorable, Favorable con reservas, Desfavorable, no se menciona}.

concepto_final ∈ {Favorable, Favorable con reservas, Desfavorable} + concepto_rationale (1–2 frases con cita corta).

Few-shot (mapeos rápidos): 

"sin salvedades… no reveló deficiencias significativas de control interno" → Control interno = Favorable.

"excepto por…" / "con salvedades…" → concepto = Favorable con reservas.

"se sostienen las observaciones / deficiencias" → concepto = Desfavorable.

Salida en JSON con la siguiente estructura (todas las claves; si falta evidencia, "NO EXTRAIDO")
Código CFA, Estado del informe, Si se entregó informe de auditoría externo, Concepto Control interno, Concepto licitación de proyecto, Concepto uso de recursos financieros según lo planificado, Concepto sobre unidad ejecutora, Fecha de vencimiento, Fecha de cambio del estado del informe, Fecha de extracción, Fecha de ultima revisión, status auditoría, código CFX, Nombre del archivo revisado, texto justificación, Observación, estado_informe_norm, informe_externo_entregado_norm, concepto_control_interno_norm, concepto_licitacion_norm, concepto_uso_recursos_norm, concepto_unidad_ejecutora_norm, concepto_final, concepto_rationale"""
            
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
                # Extraer JSON de la respuesta (puede venir con ```json o sin formato)
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_content = ai_response[json_start:json_end]
                    parsed_json = json.loads(json_content)
                    
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
        
        # Prompt específico para análisis de productos
        prompt_productos = f"""
Eres un Analista de Cartera, Experto en seguimiento documentos de proyectos, debes Identificar todos los productos comprometidos en el proyecto y genera una fila por producto, priorizando fuentes y separando meta (número) y unidad. Normaliza campos y emite concepto final por producto con justificación.

Prioridad documental:
ROP > INI > DEC > IFS (y anexo Excel si lo cita el índice). En duplicados, usar versión más reciente; cambios → Observación.

Checklist anti–"NO EXTRAIDO":
- Tablas/Matrices: "Matriz de Indicadores", "Marco Lógico", "Metas físicas".
- Narrativo: "Resultados esperados", "Componentes", "Seguimiento de indicadores" (IFS).
- Anexos/Excel de indicadores.
- Encabezados/pies → "Última revisión/Actualización".
- Validar que el registro sea producto (no resultado).

Dónde buscar (por campo):
- Código CFA / código CFX: portada/primeras páginas, marcos lógicos, carátulas (ROP/INI/DEC/IFS).
- descripción de producto: títulos/filas en matrices/POA/Componentes/IFS.
- meta del producto / meta unidad: columnas de meta ("230 km" → meta="230", unidad="km"). Si no es inequívoco → NO EXTRAIDO.
- fuente del indicador: columna/nota "Fuente" (ej.: ROP, INI, DEC, IFS, SSC).
- fecha cumplimiento de meta: "Fecha meta / Fecha de cumplimiento / Plazo".
- tipo de dato: pendiente/proyectado/realizado (detecta palabras clave como programado, estimado, alcanzado).
- característica ∈ {{administración, capacitación, equipamiento y mobiliario, fortalecimiento institucional, infraestructura}}.
- check_producto: "Sí" si el indicador es relacionado al producto y está extraído.

Casos / reglas especiales:
- Acumulado vs período: si la tabla es acumulativa, no dupliques.
- Idiomas/formatos: acepta ES/PT/EN y tablas rotadas.
- Separación meta/unidad: detecta variantes ("230 kilómetros", "230,5 Km", "100%", "1.500 personas").
- No inventes: si faltan meta o unidad, deja NO EXTRAIDO.

Niveles de confianza:
EXTRAIDO_DIRECTO, EXTRAIDO_INFERIDO, NO_EXTRAIDO. Formato: valor|NIVEL_CONFIANZA.

Normalización + Concepto:
- tipo_dato_norm ∈ {{pendiente, proyectado, realizado}} o null.
- caracteristica_norm ∈ {{administracion, capacitacion, fortalecimiento institucional, infraestructura}} o null.
- meta_num: número puro si inequívoco; si no, null.
- meta_unidad_norm: normalizar a catálogo (%, km, personas, metros cuadrados, metros cubicos, horas, hectareas, kilovoltioamperio, megavoltio amperio, litros/segundo, galones, miles de galones por dia, toneladas, cantidad/año, miles de metros al cuadrado, etc.).
- concepto_final ∈ {{Favorable, Favorable con reservas, Desfavorable}} según coherencia meta/fecha/Retraso + fuente.
- concepto_rationale (1–2 frases con evidencia y fuente).

Few-shot (patrones típicos):
- "230 km de carretera" → meta="230"|EXTRAIDO_DIRECTO, unidad="km"|EXTRAIDO_DIRECTO.
- "1,500 personas capacitadas" → meta="1500"|EXTRAIDO_DIRECTO, unidad="personas"|EXTRAIDO_DIRECTO.
- "Resultado alcanzado" → tipo_dato="realizado"|EXTRAIDO_DIRECTO.
- "Meta programada para 2024" → tipo_dato="proyectado"|EXTRAIDO_INFERIDO.
- "Talleres de capacitación" → característica="capacitación"|EXTRAIDO_INFERIDO.

Salida (una fila por producto; si falta evidencia, "NO EXTRAIDO"):
Código CFA, descripción de producto, meta del producto, meta unidad, fuente del indicador, fecha cumplimiento de meta, tipo de dato, característica, check_producto, fecha de extracción, fecha de ultima revisión, código CFX, Nombre del archivo revisado, Retraso, Observación, tipo_dato_norm, caracteristica_norm, meta_num, meta_unidad_norm, concepto_final, concepto_rationale.

Responde ÚNICAMENTE en formato JSON válido con la siguiente estructura:
{{
  "Código CFA": "valor|NIVEL_CONFIANZA",
  "descripción de producto": "valor|NIVEL_CONFIANZA",
  "meta del producto": "valor|NIVEL_CONFIANZA",
  "meta unidad": "valor|NIVEL_CONFIANZA",
  "fuente del indicador": "valor|NIVEL_CONFIANZA",
  "fecha cumplimiento de meta": "valor|NIVEL_CONFIANZA",
  "tipo de dato": "valor|NIVEL_CONFIANZA",
  "característica": "valor|NIVEL_CONFIANZA",
  "check_producto": "valor|NIVEL_CONFIANZA",
  "fecha de extracción": "{datetime.now().strftime('%Y-%m-%d')}",
  "fecha de ultima revisión": "valor|NIVEL_CONFIANZA",
  "código CFX": "valor|NIVEL_CONFIANZA",
  "Nombre del archivo revisado": "{display_name}",
  "Retraso": "valor|NIVEL_CONFIANZA",
  "Observación": "valor|NIVEL_CONFIANZA",
  "tipo_dato_norm": null,
  "caracteristica_norm": null,
  "meta_num": null,
  "meta_unidad_norm": null,
  "concepto_final": "Favorable|Favorable con reservas|Desfavorable",
  "concepto_rationale": "Justificación basada en evidencia encontrada"
}}

Documento a analizar:
{document_content.get('content', '')}
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
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_content = ai_response[json_start:json_end]
                    parsed_json = json.loads(json_content)
                    
                    self.logger.info(f"📋 JSON de productos parseado exitosamente")
                    
                    # Guardar JSON en carpeta LLM_output
                    project_name = document_content.get('project_name', 'unknown_project')
                    
                    # Crear nombre base del documento (sin chunk)
                    base_document_name = document_name.replace('_chunk_', '_CHUNK_').split('_CHUNK_')[0]
                    
                    # Crear nombre del archivo JSON
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
                    
                    self.logger.info(f"💾 JSON guardado en: {json_path}")
                    
                else:
                    self.logger.warning("⚠️ No se pudo extraer JSON válido de la respuesta")
                    parsed_json = None
                    json_path = None
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Error parseando JSON: {str(e)}")
                parsed_json = None
                json_path = None
            
            # Preparar resultado estructurado
            result = {
                "prompt_type": "prompt_2_productos",
                "document_name": display_name,
                "processed_at": datetime.now().isoformat(),
                "ai_response": ai_response,
                "parsed_json": parsed_json,
                "json_saved_path": json_path,
                "tokens_used": response.usage.total_tokens,
                "status": "completed"
            }
            
            self.logger.info(f"✅ Prompt 2 procesado exitosamente - Tokens: {response.usage.total_tokens}")
            return result
            
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
        
        # Prompt específico para análisis de desembolsos
        prompt_desembolsos = f"""
Eres un analista de cartera experto en seguimiento de desembolsos, debes Extraer desembolsos proyectados y realizados, con tabla-primero, deduplicando por período+moneda, sin convertir moneda. Normaliza fuente y emite concepto final con justificación.

Prioridad documental
ROP > INI > DEC:

Proyectados: en Cronograma/Programación/Calendario (ROP/INI).

Realizados: "Detalle/Estado de desembolsos", EEFF o narrativa (si aparece).

Checklist anti–"NO EXTRAIDO": 

Tablas (cronograma/estado/flujo de caja).

Columnas típicas: Fecha | Monto | Moneda | Fuente/Tipo.

Equivalente USD: solo llenarlo si no existe la moneda original como registro separado.

DEDUP: no repitas mismo período + moneda del mismo evento.

Si falta algún dato (fecha/moneda/monto/fuente) tras revisar tablas y notas → NO EXTRAIDO.

Dónde buscar (por campo): 

Código de operación (CFX): portada/primeras páginas, cabecera del cronograma.

fecha de desembolso por parte de CAF:

Realizado → "Detalle/Estado de desembolsos", "Desembolsos efectuados/realizados".

Proyectado → "Cronograma/Programación/Calendario de desembolsos", "Flujo de caja".

monto desembolsado CAF: columna "Monto/Importe/Desembolsado" (sin símbolos, sin conversiones).

monto desembolsado CAF USD: solo si hay columna/registro explícito en USD y no existe el original.

fuente CAF: etiqueta clara: "CAF Realizado", "Proyectado (Cronograma)", "Anticipo", "Pago directo", etc.

fecha de extracción (ahora), fecha de última revisión, Nombre del archivo revisado, Observación (cambios de montos/periodificación/moneda/fuente entre versiones).

Niveles de confianza: 

EXTRAIDO_DIRECTO, EXTRAIDO_INFERIDO, NO_EXTRAIDO (usa valor|NIVEL_CONFIANZA).

Normalización + Concepto: 

fuente_norm (opcional) → {{CAF Realizado, Proyectado (Cronograma), Anticipo, Pago directo, Reembolso…}} o null.

concepto_final ∈ {{Favorable, Favorable con reservas, Desfavorable}}:

Favorable: registros completos y coherentes (fecha, monto, moneda, fuente).

Con reservas: inconsistencias menores explicadas o diferencias programado/realizado documentadas.

Desfavorable: faltantes graves/errores o retrasos sin justificación.

concepto_rationale: 1–2 frases con evidencia (indicar fuente: ROP/INI/DEC/EEFF).

Few-shot (patrones de montos/fechas): 

2024-06 | 1.250.000 | USD | CAF Realizado → fecha="2024-06"|EXTRAIDO_DIRECTO, monto="1250000"|EXTRAIDO_DIRECTO, USD, fuente="CAF Realizado"|EXTRAIDO_DIRECTO.

"USD 1,000", "1.000.000", "1 000 000", "US$ 2,5 M" → extrae número puro (no agregues símbolos; no conviertas).

Reglas claves: 

No convertir moneda ni inferir fechas/moneda.

No duplicar periodo+moneda.

Priorizar moneda original; USD solo si no está la original.

Salida (si falta evidencia, "NO EXTRAIDO")
Código de operación (CFX), fecha de desembolso por parte de CAF, monto desembolsado CAF, monto desembolsado CAF USD, fuente CAF proyectado, fecha de extracción, fecha de ultima revisión, Nombre del archivo revisado, Observación, fuente_norm (opcional), concepto_final, concepto_rationale.

Responde ÚNICAMENTE en formato JSON válido con la siguiente estructura:
{{
  "Código de operación (CFX)": "valor|NIVEL_CONFIANZA",
  "fecha de desembolso por parte de CAF": "valor|NIVEL_CONFIANZA",
  "monto desembolsado CAF": "valor|NIVEL_CONFIANZA",
  "monto desembolsado CAF USD": "valor|NIVEL_CONFIANZA",
  "fuente CAF proyectado": "valor|NIVEL_CONFIANZA",
  "fecha de extracción": "{datetime.now().strftime('%Y-%m-%d')}",
  "fecha de ultima revisión": "valor|NIVEL_CONFIANZA",
  "Nombre del archivo revisado": "{display_name}",
  "Observación": "valor|NIVEL_CONFIANZA",
  "fuente_norm": null,
  "concepto_final": "Favorable|Favorable con reservas|Desfavorable",
  "concepto_rationale": "Justificación basada en evidencia encontrada"
}}

Documento a analizar:
{document_content.get('content', '')}
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
            
            # Parsear JSON de la respuesta
            try:
                # Limpiar la respuesta para extraer solo el JSON
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_content = ai_response[json_start:json_end]
                    parsed_json = json.loads(json_content)
                    
                    self.logger.info(f"💰 JSON de desembolsos parseado exitosamente")
                    
                    # Guardar JSON en carpeta LLM_output/Desembolsos
                    project_name = document_content.get('project_name', 'unknown_project')
                    
                    # Crear nombre base del documento (sin chunk)
                    base_document_name = document_name.replace('_chunk_', '_CHUNK_').split('_CHUNK_')[0]
                    
                    # Crear nombre del archivo JSON
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
                    
                    self.logger.info(f"💾 JSON guardado en: {json_path}")
                    
                    # Calcular tokens utilizados
                    total_tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                    
                    result = {
                        "prompt_type": "prompt_3_desembolsos",
                        "document_name": display_name,
                        "processed_at": datetime.now().isoformat(),
                        "json_output_path": json_path,
                        "tokens_used": total_tokens,
                        "status": "success",
                        "parsed_json": parsed_json
                    }
                    
                    self.logger.info(f"✅ Prompt 3 procesado exitosamente - Tokens: {total_tokens}")
                    return result
                    
                else:
                    self.logger.warning(f"⚠️ No se pudo extraer JSON válido de la respuesta para {display_name}")
                    return {
                        "prompt_type": "prompt_3_desembolsos",
                        "document_name": display_name,
                        "processed_at": datetime.now().isoformat(),
                        "status": "json_parse_error",
                        "error": "No se pudo extraer JSON válido",
                        "raw_response": ai_response[:500]  # Primeros 500 caracteres para debug
                    }
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Error parseando JSON para {display_name}: {str(e)}")
                return {
                    "prompt_type": "prompt_3_desembolsos",
                    "document_name": display_name,
                    "processed_at": datetime.now().isoformat(),
                    "status": "json_decode_error",
                    "error": str(e),
                    "raw_response": ai_response[:500]
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
            
            # Buscar todos los archivos JSON de productos
            productos_files = []
            for filename in os.listdir(llm_output_dir):
                if filename.endswith('_productos.json'):
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
            
            # Guardar archivo concatenado
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(concatenated_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Archivos de productos concatenados: {len(productos_files)} archivos → {output_file}")
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
            
            # Buscar todos los archivos JSON de desembolsos
            desembolsos_files = []
            for filename in os.listdir(llm_output_dir):
                if filename.endswith('_desembolsos.json'):
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
            
            # Guardar archivo concatenado
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(concatenated_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"✅ Archivos de desembolsos concatenados: {len(desembolsos_files)} archivos → {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"❌ Error concatenando archivos de desembolsos: {str(e)}")
            raise