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
            prompt = f"""
            **ROL:** Eres un experto analista de cartera especializado en auditoría de proyectos de desarrollo.
            
            **PRIORIDAD DE DOCUMENTOS:**
            1. Informes de auditoría
            2. Informes de supervisión
            3. Informes de seguimiento
            4. Informes de evaluación
            5. Otros documentos relacionados con auditoría
            
            **CHECKLIST DE AUDITORÍA:**
            - ✅ Identificar hallazgos de auditoría
            - ✅ Extraer recomendaciones
            - ✅ Verificar estado de implementación
            - ✅ Evaluar riesgos identificados
            - ✅ Analizar medidas correctivas
            
            **INSTRUCCIONES DE EXTRACCIÓN:**
            1. Extrae TODOS los hallazgos de auditoría mencionados
            2. Para cada hallazgo, identifica:
               - Descripción del hallazgo
               - Nivel de criticidad (Alto/Medio/Bajo)
               - Recomendación asociada
               - Estado de implementación
               - Fecha límite (si aplica)
            3. Identifica riesgos operacionales, financieros o de cumplimiento
            4. Extrae medidas correctivas propuestas o implementadas
            
            **REGLAS DE NORMALIZACIÓN:**
            - Fechas en formato YYYY-MM-DD
            - Montos en USD (convertir si es necesario)
            - Estados: "Pendiente", "En Proceso", "Implementado", "Vencido"
            - Criticidad: "Alto", "Medio", "Bajo"
            
            **REGLAS CRÍTICAS PARA JSON:**
            - SIEMPRE usa comillas dobles para strings
            - NUNCA uses comillas simples dentro de strings
            - Escapa caracteres especiales: \" \n \t \\
            - NO incluyas saltos de línea dentro de strings
            - Reemplaza saltos de línea con espacios
            - Limita strings a máximo 200 caracteres
            
            **NIVEL DE CONFIANZA:**
            - Alto (0.9-1.0): Información explícita y clara
            - Medio (0.7-0.8): Información inferida con contexto
            - Bajo (0.5-0.6): Información parcial o ambigua
            
            **ESQUEMA DE SALIDA JSON:**
            {{
                "documento_info": {{
                    "nombre_documento": "string",
                    "tipo_documento": "string",
                    "fecha_documento": "YYYY-MM-DD",
                    "proyecto": "string"
                }},
                "hallazgos_auditoria": [
                    {{
                        "id_hallazgo": "string",
                        "descripcion": "string",
                        "criticidad": "Alto|Medio|Bajo",
                        "categoria": "string",
                        "recomendacion": "string",
                        "estado_implementacion": "Pendiente|En Proceso|Implementado|Vencido",
                        "fecha_limite": "YYYY-MM-DD",
                        "responsable": "string",
                        "nivel_confianza": 0.0
                    }}
                ],
                "riesgos_identificados": [
                    {{
                        "tipo_riesgo": "Operacional|Financiero|Cumplimiento|Reputacional",
                        "descripcion": "string",
                        "impacto": "Alto|Medio|Bajo",
                        "probabilidad": "Alto|Medio|Bajo",
                        "medidas_mitigacion": "string",
                        "nivel_confianza": 0.0
                    }}
                ],
                "medidas_correctivas": [
                    {{
                        "descripcion": "string",
                        "estado": "Propuesta|En Implementación|Implementada",
                        "fecha_implementacion": "YYYY-MM-DD",
                        "responsable": "string",
                        "nivel_confianza": 0.0
                    }}
                ],
                "resumen_auditoria": {{
                    "total_hallazgos": 0,
                    "hallazgos_criticos": 0,
                    "porcentaje_implementacion": 0.0,
                    "principales_riesgos": "string"
                }}
            }}
            
            **EJEMPLO DE SALIDA:**
            {{
                "documento_info": {{
                    "nombre_documento": "Informe de Auditoría Proyecto XYZ",
                    "tipo_documento": "Informe de Auditoría",
                    "fecha_documento": "2023-06-15",
                    "proyecto": "CFA009757"
                }},
                "hallazgos_auditoria": [
                    {{
                        "id_hallazgo": "H001",
                        "descripcion": "Falta de documentación en procesos de adquisición",
                        "criticidad": "Alto",
                        "categoria": "Cumplimiento",
                        "recomendacion": "Implementar procedimiento documentado para adquisiciones",
                        "estado_implementacion": "En Proceso",
                        "fecha_limite": "2023-09-30",
                        "responsable": "Gerencia de Adquisiciones",
                        "nivel_confianza": 0.9
                    }}
                ],
                "riesgos_identificados": [
                    {{
                        "tipo_riesgo": "Cumplimiento",
                        "descripcion": "Incumplimiento de normativas de adquisición",
                        "impacto": "Alto",
                        "probabilidad": "Medio",
                        "medidas_mitigacion": "Capacitación del personal y actualización de procedimientos",
                        "nivel_confianza": 0.8
                    }}
                ],
                "medidas_correctivas": [
                    {{
                        "descripcion": "Desarrollo de manual de procedimientos de adquisición",
                        "estado": "En Implementación",
                        "fecha_implementacion": "2023-08-31",
                        "responsable": "Consultor Externo",
                        "nivel_confianza": 0.9
                    }}
                ],
                "resumen_auditoria": {{
                    "total_hallazgos": 5,
                    "hallazgos_criticos": 2,
                    "porcentaje_implementacion": 60.0,
                    "principales_riesgos": "Riesgos de cumplimiento en procesos de adquisición y gestión financiera"
                }}
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
                            # Si aún falla, crear estructura mínima
                            self.logger.warning(f"⚠️ Creando estructura JSON mínima para {document_name}")
                            parsed_json = {
                                "documento_info": {
                                    "nombre_documento": document_name,
                                    "tipo_documento": "Informe de Auditoría",
                                    "fecha_documento": "",
                                    "proyecto": document_content.get('project_name', '')
                                },
                                "hallazgos_auditoria": [],
                                "riesgos_identificados": [],
                                "medidas_correctivas": [],
                                "resumen_auditoria": {
                                    "total_hallazgos": 0,
                                    "hallazgos_criticos": 0,
                                    "porcentaje_implementacion": 0.0,
                                    "principales_riesgos": "No se pudo extraer información debido a errores de formato"
                                }
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
        
        # Prompt específico para análisis de productos
        prompt_productos = f"""
        **ROL:** Eres un experto analista de cartera especializado en seguimiento de productos y resultados de proyectos de desarrollo.
        
        **PRIORIDAD DE DOCUMENTOS:**
        1. Reportes de Operación (ROP)
        2. Informes de Inicio (INI)
        3. Declaraciones de Efectividad (DEC)
        4. Informes de Seguimiento (IFS)
        5. Matrices de Marco Lógico
        
        **CHECKLIST DE PRODUCTOS:**
        - ✅ Identificar todos los productos comprometidos
        - ✅ Extraer metas físicas y financieras
        - ✅ Verificar estado de avance
        - ✅ Evaluar calidad de entregables
        - ✅ Analizar cumplimiento de cronograma
        
        **INSTRUCCIONES DE EXTRACCIÓN:**
        1. Extrae TODOS los productos mencionados en el proyecto
        2. Para cada producto, identifica:
           - Descripción del producto
           - Meta cuantitativa (número y unidad)
           - Fecha de cumplimiento esperada
           - Estado actual de avance
           - Calidad del entregable
        3. Clasifica productos por categoría
        4. Evalúa riesgos de cumplimiento
        
        **REGLAS DE NORMALIZACIÓN:**
        - Fechas en formato YYYY-MM-DD
        - Metas: separar número de unidad (ej: "230 km" → meta=230, unidad="km")
        - Estados: "No Iniciado", "En Proceso", "Completado", "Retrasado"
        - Categorías: "Infraestructura", "Capacitación", "Equipamiento", "Fortalecimiento Institucional", "Administración"
        
        **NIVEL DE CONFIANZA:**
        - Alto (0.9-1.0): Información explícita en matrices o tablas
        - Medio (0.7-0.8): Información inferida del contexto
        - Bajo (0.5-0.6): Información parcial o ambigua
        
        **ESQUEMA DE SALIDA JSON:**
        {{
            "documento_info": {{
                "nombre_documento": "string",
                "tipo_documento": "string",
                "fecha_documento": "YYYY-MM-DD",
                "proyecto": "string"
            }},
            "productos_identificados": [
                {{
                    "id_producto": "string",
                    "descripcion": "string",
                    "categoria": "Infraestructura|Capacitación|Equipamiento|Fortalecimiento Institucional|Administración",
                    "meta_numerica": 0,
                    "unidad_medida": "string",
                    "fecha_cumplimiento": "YYYY-MM-DD",
                    "estado_avance": "No Iniciado|En Proceso|Completado|Retrasado",
                    "porcentaje_avance": 0.0,
                    "calidad_entregable": "Excelente|Buena|Regular|Deficiente",
                    "fuente_informacion": "string",
                    "nivel_confianza": 0.0
                }}
            ],
            "analisis_cumplimiento": [
                {{
                    "categoria": "string",
                    "productos_totales": 0,
                    "productos_completados": 0,
                    "porcentaje_cumplimiento": 0.0,
                    "principales_riesgos": "string"
                }}
            ],
            "resumen_productos": {{
                "total_productos": 0,
                "productos_en_tiempo": 0,
                "productos_retrasados": 0,
                "porcentaje_cumplimiento_general": 0.0,
                "principales_desafios": "string"
            }}
        }}
        
        **EJEMPLO DE SALIDA:**
        {{
            "documento_info": {{
                "nombre_documento": "ROP Proyecto Infraestructura Rural",
                "tipo_documento": "Reporte de Operación",
                "fecha_documento": "2023-06-15",
                "proyecto": "CFA009757"
            }},
            "productos_identificados": [
                {{
                    "id_producto": "P001",
                    "descripcion": "Construcción de carreteras rurales",
                    "categoria": "Infraestructura",
                    "meta_numerica": 230,
                    "unidad_medida": "km",
                    "fecha_cumplimiento": "2023-12-31",
                    "estado_avance": "En Proceso",
                    "porcentaje_avance": 65.0,
                    "calidad_entregable": "Buena",
                    "fuente_informacion": "Matriz de Marco Lógico",
                    "nivel_confianza": 0.9
                }}
            ],
            "analisis_cumplimiento": [
                {{
                    "categoria": "Infraestructura",
                    "productos_totales": 3,
                    "productos_completados": 1,
                    "porcentaje_cumplimiento": 33.3,
                    "principales_riesgos": "Retrasos en adquisición de materiales"
                }}
            ],
            "resumen_productos": {{
                "total_productos": 8,
                "productos_en_tiempo": 5,
                "productos_retrasados": 3,
                "porcentaje_cumplimiento_general": 62.5,
                "principales_desafios": "Coordinación interinstitucional y disponibilidad de recursos"
            }}
        }}
        
        **DOCUMENTO A ANALIZAR:**
        {document_content.get('content', '')}
        
        **METADATOS DEL DOCUMENTO:**
        - Nombre: {document_content.get('filename', 'N/A')}
        - Proyecto: {document_content.get('project_name', 'N/A')}
        - Páginas: {document_content.get('pages', 'N/A')}
        
        Analiza el documento y extrae toda la información de productos siguiendo el esquema JSON especificado.
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
        **ROL:** Eres un experto analista de cartera especializado en seguimiento de desembolsos de proyectos de desarrollo.
        
        **PRIORIDAD DE DOCUMENTOS:**
        1. Reportes de Operación (ROP)
        2. Informes de Inicio (INI)
        3. Declaraciones de Efectividad (DEC)
        4. Estados financieros
        5. Cronogramas de desembolso
        
        **CHECKLIST DE DESEMBOLSOS:**
        - ✅ Identificar desembolsos proyectados y realizados
        - ✅ Extraer fechas y montos exactos
        - ✅ Verificar fuentes de financiamiento
        - ✅ Evaluar cumplimiento de cronograma
        - ✅ Analizar variaciones presupuestarias
        
        **INSTRUCCIONES DE EXTRACCIÓN:**
        1. Extrae TODOS los desembolsos mencionados (proyectados y realizados)
        2. Para cada desembolso, identifica:
           - Fecha de desembolso
           - Monto en moneda original
           - Equivalente en USD (si disponible)
           - Fuente de financiamiento
           - Estado (proyectado/realizado)
        3. No conviertas monedas - usa valores originales
        4. Deduplica por período + moneda
        
        **REGLAS DE NORMALIZACIÓN:**
        - Fechas en formato YYYY-MM-DD
        - Montos sin símbolos de moneda en el número
        - Estados: "Proyectado", "Realizado", "Pendiente", "Cancelado"
        - Fuentes: "CAF", "Contraparte Local", "Otros Organismos", "Recursos Propios"
        
        **NIVEL DE CONFIANZA:**
        - Alto (0.9-1.0): Información explícita en tablas de desembolso
        - Medio (0.7-0.8): Información inferida de cronogramas
        - Bajo (0.5-0.6): Información parcial o estimada
        
        **ESQUEMA DE SALIDA JSON:**
        {{
            "documento_info": {{
                "nombre_documento": "string",
                "tipo_documento": "string",
                "fecha_documento": "YYYY-MM-DD",
                "proyecto": "string"
            }},
            "desembolsos_identificados": [
                {{
                    "id_desembolso": "string",
                    "fecha_desembolso": "YYYY-MM-DD",
                    "monto_original": 0.0,
                    "moneda_original": "string",
                    "monto_usd": 0.0,
                    "fuente_financiamiento": "CAF|Contraparte Local|Otros Organismos|Recursos Propios",
                    "estado_desembolso": "Proyectado|Realizado|Pendiente|Cancelado",
                    "tipo_desembolso": "Inicial|Intermedio|Final|Extraordinario",
                    "concepto": "string",
                    "nivel_confianza": 0.0
                }}
            ],
            "analisis_cronograma": {{
                "total_proyectado": 0.0,
                "total_realizado": 0.0,
                "porcentaje_ejecucion": 0.0,
                "desviacion_cronograma": 0,
                "principales_retrasos": "string"
            }},
            "analisis_por_fuente": [
                {{
                    "fuente": "string",
                    "monto_proyectado_usd": 0.0,
                    "monto_realizado_usd": 0.0,
                    "porcentaje_cumplimiento": 0.0
                }}
            ],
            "resumen_desembolsos": {{
                "total_desembolsos": 0,
                "desembolsos_realizados": 0,
                "desembolsos_pendientes": 0,
                "monto_total_usd": 0.0,
                "principales_observaciones": "string"
            }}
        }}
        
        **EJEMPLO DE SALIDA:**
        {{
            "documento_info": {{
                "nombre_documento": "ROP Proyecto Infraestructura",
                "tipo_documento": "Reporte de Operación",
                "fecha_documento": "2023-06-15",
                "proyecto": "CFA009757"
            }},
            "desembolsos_identificados": [
                {{
                    "id_desembolso": "D001",
                    "fecha_desembolso": "2023-03-15",
                    "monto_original": 5000000.0,
                    "moneda_original": "USD",
                    "monto_usd": 5000000.0,
                    "fuente_financiamiento": "CAF",
                    "estado_desembolso": "Realizado",
                    "tipo_desembolso": "Inicial",
                    "concepto": "Primer desembolso para inicio de obras",
                    "nivel_confianza": 0.9
                }}
            ],
            "analisis_cronograma": {{
                "total_proyectado": 20000000.0,
                "total_realizado": 12000000.0,
                "porcentaje_ejecucion": 60.0,
                "desviacion_cronograma": -30,
                "principales_retrasos": "Retrasos en procesos de licitación"
            }},
            "analisis_por_fuente": [
                {{
                    "fuente": "CAF",
                    "monto_proyectado_usd": 15000000.0,
                    "monto_realizado_usd": 9000000.0,
                    "porcentaje_cumplimiento": 60.0
                }}
            ],
            "resumen_desembolsos": {{
                "total_desembolsos": 8,
                "desembolsos_realizados": 3,
                "desembolsos_pendientes": 5,
                "monto_total_usd": 20000000.0,
                "principales_observaciones": "Ejecución dentro de parámetros esperados con ligeros retrasos"
            }}
        }}
        
        **DOCUMENTO A ANALIZAR:**
        {document_content.get('content', '')}
        
        **METADATOS DEL DOCUMENTO:**
        - Nombre: {document_content.get('filename', 'N/A')}
        - Proyecto: {document_content.get('project_name', 'N/A')}
        - Páginas: {document_content.get('pages', 'N/A')}
        
        Analiza el documento y extrae toda la información de desembolsos siguiendo el esquema JSON especificado.
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