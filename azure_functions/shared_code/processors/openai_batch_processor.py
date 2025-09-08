import os
import json
import logging
import re
import time
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from openai import AzureOpenAI
from shared_code.utils.app_insights_logger import get_logger
from shared_code.utils.blob_storage_client import BlobStorageClient

# Prompts como constantes
PROMPT_AUDITORIA = """prompt - Agente Auditoria

Eres un Analista experto en documentos de auditoria, debes Extraer todas las variables del formato Auditorías priorizando archivos IXP, normalizando los campos categóricos y emitir un concepto final (Favorable / Favorable con reservas / Desfavorable) con justificación.

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

Salida (todas las claves; si falta evidencia, "NO EXTRAIDO")
Código CFA, Estado del informe, Si se entregó informe de auditoría externo, Concepto Control interno, Concepto licitación de proyecto, Concepto uso de recursos financieros según lo planificado, Concepto sobre unidad ejecutora, Fecha de vencimiento, Fecha de cambio del estado del informe, Fecha de extracción, Fecha de ultima revisión, status auditoría, código CFX, Nombre del archivo revisado, texto justificación, Observación, estado_informe_norm, informe_externo_entregado_norm, concepto_control_interno_norm, concepto_licitacion_norm, concepto_uso_recursos_norm, concepto_unidad_ejecutora_norm, concepto_final, concepto_rationale"""

PROMPT_DESEMBOLSOS = """Prompt — Agente Desembolsos 

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

fuente_norm (opcional) → {CAF Realizado, Proyectado (Cronograma), Anticipo, Pago directo, Reembolso…} o null.

concepto_final ∈ {Favorable, Favorable con reservas, Desfavorable}:

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
Código de operación (CFX), fecha de desembolso por parte de CAF, monto desembolsado CAF, monto desembolsado CAF USD, fuente CAF proyectado, fecha de extracción, fecha de ultima revisión, Nombre del archivo revisado, Observación, fuente_norm (opcional), concepto_final, concepto_rationale."""

PROMPT_PRODUCTOS = """Prompt — Agente Productos 


Eres un Analista de Cartera, Experto en seguimiento documentos de proyectos, debes Identificar todos los productos comprometidos en el proyecto y genera una fila por producto, priorizando fuentes y separando meta (número) y unidad. Normaliza campos y emite concepto final por producto con justificación.

Prioridad documental
ROP > INI > DEC > IFS (y anexo Excel si lo cita el índice). En duplicados, usar versión más reciente; cambios → Observación.

Checklist anti–"NO EXTRAIDO":

Tablas/Matrices: "Matriz de Indicadores", "Marco Lógico", "Metas físicas".

Narrativo: "Resultados esperados", "Componentes", "Seguimiento de indicadores" (IFS).

Anexos/Excel de indicadores.

Encabezados/pies → "Última revisión/Actualización".

Validar que el registro sea producto (no resultado).

Dónde buscar (por campo): 

Código CFA / código CFX: portada/primeras páginas, marcos lógicos, carátulas (ROP/INI/DEC/IFS).

descripción de producto: títulos/filas en matrices/POA/Componentes/IFS.

meta del producto / meta unidad: columnas de meta ("230 km" → meta="230", unidad="km"). Si no es inequívoco → NO EXTRAIDO.

fuente del indicador: columna/nota "Fuente" (ej.: ROP, INI, DEC, IFS, SSC).

fecha cumplimiento de meta: "Fecha meta / Fecha de cumplimiento / Plazo".

tipo de dato: pendiente/proyectado/realizado (detecta palabras clave como programado, estimado, alcanzado).

característica ∈ {administración, capacitación, equipamiento y mobiliario, fortalecimiento institucional, infraestructura}.

check_producto: "Sí" si el indicador es relacionado al producto y está extraído.

fecha de ultima revisión, Nombre del archivo revisado, Retraso (Sí si fecha efectiva > fecha meta), Observación.

Casos / reglas especiales: 

Acumulado vs período: si la tabla es acumulativa, no dupliques.

Idiomas/formatos: acepta ES/PT/EN y tablas rotadas.

Separación meta/unidad: detecta variantes ("230 kilómetros", "230,5 Km", "100%", "1.500 personas").

No inventes: si faltan meta o unidad, deja NO EXTRAIDO.

Niveles de confianza: 

EXTRAIDO_DIRECTO, EXTRAIDO_INFERIDO, NO_EXTRAIDO. Formato: valor|NIVEL_CONFIANZA.

Normalización + Concepto: 

tipo_dato_norm ∈ {pendiente, proyectado, realizado} o null.

caracteristica_norm ∈ {administracion, capacitacion, fortalecimiento institucional, infraestructura} o null.

meta_num: número puro si inequívoco; si no, null.

meta_unidad_norm: normalizar a catálogo (%, km, personas, metros cuadrados, metros cubicos, horas,hectareas, kilovoltioamperio, megavoltio amperio, litros/segundo, galones, miles de galones por dia, toneladas, cantidad/ año, miles de metros al cuadrado, etc.).

concepto_final ∈ {Favorable, Favorable con reservas, Desfavorable} según coherencia meta/fecha/Retraso + fuente; concepto_rationale (1–2 frases con evidencia y fuente).

Few-shot (patrones típicos): 

"230 km de carretera" → meta="230"|EXTRAIDO_DIRECTO, unidad="km"|EXTRAIDO_DIRECTO.

"1,500 personas capacitadas" → meta="1500"|EXTRAIDO_DIRECTO, unidad="personas"|EXTRAIDO_DIRECTO.

"Resultado alcanzado" → tipo_dato="realizado"|EXTRAIDO_DIRECTO.

"Meta programada para 2024" → tipo_dato="proyectado"|EXTRAIDO_INFERIDO.

"Talleres de capacitación" → característica="capacitación"|EXTRAIDO_INFERIDO.

Salida (una fila por producto; si falta evidencia, "NO EXTRAIDO")
Código CFA, descripción de producto, meta del producto, meta unidad, fuente del indicador, fecha cumplimiento de meta, tipo de dato, característica, check_producto, fecha de extracción, fecha de ultima revisión, código CFX, Nombre del archivo revisado, Retraso, Observación, tipo_dato_norm, caracteristica_norm, meta_num, meta_unidad_norm, concepto_final, concepto_rationale."""

# Configurar logging para reducir verbosidad de Azure
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)

class OpenAIBatchProcessor:
    """
    Procesador de Azure OpenAI Batch API para análisis de documentos.
    Genera batch jobs para procesar documentos y chunks usando 3 prompts específicos.
    """
    
    def __init__(self):
        self.logger = get_logger('openai_batch_processor')
        self._setup_client()
        self._load_prompts()
        
    def _setup_client(self):
        """Configura el cliente de Azure OpenAI usando variables de entorno."""
        try:
            # Obtener configuración del .env
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://oai-poc-idatafactory-cr.openai.azure.com/')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
            self.deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o-2')
            
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY no encontrada en variables de entorno")
            
            self.client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=endpoint,
                api_key=api_key
            )
            
            self.logger.info(f"Cliente Azure OpenAI Batch configurado exitosamente")
            self.logger.info(f"Endpoint: {endpoint}")
            self.logger.info(f"Deployment: {self.deployment_name}")
            
        except Exception as e:
            self.logger.error(f"Error configurando cliente Azure OpenAI: {str(e)}")
            raise
    
    def _load_prompts(self):
        """Carga los prompts desde constantes definidas en el código"""
        try:
            # Asignar prompts a atributos de instancia para compatibilidad
            self.prompt_auditoria = PROMPT_AUDITORIA
            self.prompt_desembolsos = PROMPT_DESEMBOLSOS
            self.prompt_productos = PROMPT_PRODUCTOS
            
            # Crear diccionario de prompts para acceso por número
            self.prompts = {
                'prompt_1': PROMPT_PRODUCTOS,
                'prompt_2': PROMPT_DESEMBOLSOS, 
                'prompt_3': PROMPT_AUDITORIA
            }
            
            self.logger.info("✅ Prompts cargados exitosamente desde constantes")
            
        except Exception as e:
            self.logger.error(f"Error cargando prompts: {str(e)}")
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
    
    def _should_process_with_prompt(self, document_content: Dict[str, Any], prompt_number: int) -> bool:
        """
        Determina si un documento debe ser procesado con un prompt específico.
        
        Args:
            document_content: Contenido del documento
            prompt_number: Número del prompt (1, 2, 3)
            
        Returns:
            True si debe procesarse, False si no
        """
        document_prefix = self._get_document_prefix(document_content)
        
        # Filtros por prefijo según prompt
        if prompt_number == 1:  # Auditoría
            allowed_prefixes = ['IXP']
        elif prompt_number == 2:  # Productos
            allowed_prefixes = ['ROP', 'INI', 'DEC', 'IFS']
        elif prompt_number == 3:  # Desembolsos
            allowed_prefixes = ['ROP', 'INI', 'DEC']
        else:
            return False
        
        return document_prefix in allowed_prefixes
    
    def _create_batch_request(self, custom_id: str, prompt: str, content: str) -> Dict[str, Any]:
        """
        Crea una request individual para el batch job.
        
        Args:
            custom_id: ID único para identificar la request
            prompt: Prompt a usar
            content: Contenido del documento
            
        Returns:
            Dict con la estructura de request para batch
        """
        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/chat/completions",
            "body": {
                "model": self.deployment_name,
                "messages": [
                    {
                        "role": "system", 
                        "content": "Eres un Analista experto en documentos de auditoría. Tu tarea es extraer información específica siguiendo un formato estructurado y emitiendo conceptos normalizados para entregar en formato JSON lo solicitado."
                    },
                    {
                        "role": "user", 
                        "content": f"{prompt}\n\nDocumento:\n{content}"
                    }
                ],
                "max_completion_tokens": 1000,
                "temperature": 0.3
            }
        }
    
    def create_batch_job(self, project_name: str) -> Dict[str, Any]:
        """
        Crea un batch job para procesar todos los documentos de un proyecto usando BlobStorageClient.
        
        Args:
            project_name: Nombre del proyecto (ej: CFA009660)
            
        Returns:
            Dict con información del batch job creado
        """
        self.logger.info(f"🚀 Creando batch job para proyecto: {project_name}")
        
        batch_requests = []
        documents_info = []
        
        try:
            blob_client = BlobStorageClient()
            
            # Procesar documentos DI desde blob storage
            di_documents = blob_client.list_processed_documents(project_name)
            for doc_name in di_documents:
                if doc_name.endswith('.json'):
                    self._add_document_to_batch_from_blob(doc_name, project_name, batch_requests, documents_info, blob_client, 'DI')
            
            # Procesar chunks desde blob storage
            chunk_documents = blob_client.list_chunks(project_name)
            for chunk_name in chunk_documents:
                if chunk_name.endswith('.json'):
                    self._add_document_to_batch_from_blob(chunk_name, project_name, batch_requests, documents_info, blob_client, 'chunks')
            
            if not batch_requests:
                raise ValueError(f"No se encontraron documentos para procesar en proyecto {project_name}")
            
            # Crear archivo JSONL temporal (formato requerido por Azure Batch API)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
                for request in batch_requests:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
                batch_input_file = f.name
            
            self.logger.info(f"📄 Archivo batch temporal creado: {batch_input_file} ({len(batch_requests)} requests)")
            
            # Subir archivo a Azure
            uploaded = self.client.files.create(
                file=open(batch_input_file, "rb"),
                purpose="batch"
            )
            
            # Limpiar archivo temporal
            os.unlink(batch_input_file)
            
            # Crear batch job
            batch = self.client.batches.create(
                input_file_id=uploaded.id,
                endpoint="/chat/completions",
                completion_window="24h",
                metadata={"project": project_name}
            )
            
            batch_info = {
                "batch_id": batch.id,
                "project_name": project_name,
                "input_file_id": uploaded.id,
                "created_at": datetime.now().isoformat(),
                "status": batch.status,
                "total_requests": len(batch_requests),
                "documents_info": documents_info
            }
            
            # Guardar información del batch en blob storage
            batch_info_content = json.dumps(batch_info, indent=2, ensure_ascii=False)
            batch_info_path = f"basedocuments/{project_name}/processed/openai_logs/batch_info_{project_name}_{batch.id}.json"
            blob_client.upload_blob(batch_info_path, batch_info_content)
            
            self.logger.info(f"✅ Batch job creado exitosamente:")
            self.logger.info(f"   📋 Batch ID: {batch.id}")
            self.logger.info(f"   📊 Total requests: {len(batch_requests)}")
            self.logger.info(f"   📁 Info guardada en blob: {batch_info_path}")
            
            return batch_info
            
        except Exception as e:
            self.logger.error(f"Error creando batch job: {str(e)}")
            raise
    
    def process_chunks(self, chunks: List[Dict], document_name: str, queue_type: str) -> Dict[str, Any]:
        """
        Procesa chunks directamente para crear un batch job.
        
        Args:
            chunks: Lista de chunks del documento
            document_name: Nombre del documento
            queue_type: Tipo de cola (no usado, mantenido por compatibilidad)
            
        Returns:
            Dict con información del batch job creado
        """
        try:
            self.logger.info(f"🚀 Procesando {len(chunks)} chunks para documento: {document_name}")
            
            batch_requests = []
            documents_info = []
            
            for i, chunk in enumerate(chunks):
                # Crear contenido del chunk con información del documento
                chunk_content = {
                    'content': chunk.get('content', ''),
                    'document_name': document_name,
                    'chunk_index': i
                }
                
                content_text = chunk_content.get('content', '')
                
                doc_info = {
                    "document_name": document_name,
                    "chunk_index": i,
                    "prefix": self._get_document_prefix(chunk_content),
                    "prompts_applied": []
                }
                
                # Verificar y agregar prompts aplicables
                prompts = [
                    (1, "auditoria", self.prompt_auditoria),
                    (2, "desembolsos", self.prompt_desembolsos),
                    (3, "productos", self.prompt_productos)
                ]
                
                for prompt_num, prompt_type, prompt_text in prompts:
                    if self._should_process_with_prompt(chunk_content, prompt_num):
                        custom_id = f"{document_name}_{prompt_type}_chunk_{i:03d}"
                        
                        request = self._create_batch_request(custom_id, prompt_text, content_text)
                        batch_requests.append(request)
                        doc_info["prompts_applied"].append(prompt_type)
                
                if doc_info["prompts_applied"]:
                    documents_info.append(doc_info)
                    self.logger.info(f"📄 Chunk {i} agregado al batch (prompts: {doc_info['prompts_applied']})")
            
            if not batch_requests:
                raise ValueError(f"No se generaron requests para el documento {document_name}")
            
            # Crear archivo JSONL temporal
            temp_batch_file = f"/tmp/batch_input_{document_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            
            with open(temp_batch_file, 'w', encoding='utf-8') as f:
                for request in batch_requests:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
            
            self.logger.info(f"📄 Archivo batch temporal creado: {temp_batch_file} ({len(batch_requests)} requests)")
            
            # Subir archivo a Azure
            uploaded = self.client.files.create(
                file=open(temp_batch_file, "rb"),
                purpose="batch"
            )
            
            # Crear batch job
            batch = self.client.batches.create(
                input_file_id=uploaded.id,
                endpoint="/chat/completions",
                completion_window="24h",
                metadata={"document": document_name}
            )
            
            batch_info = {
                "batch_id": batch.id,
                "document_name": document_name,
                "input_file_id": uploaded.id,
                "input_file_name": temp_batch_file,
                "created_at": datetime.now().isoformat(),
                "status": batch.status,
                "total_requests": len(batch_requests),
                "documents_info": documents_info
            }
            
            self.logger.info(f"✅ Batch job creado exitosamente:")
            self.logger.info(f"   📋 Batch ID: {batch.id}")
            self.logger.info(f"   📊 Total requests: {len(batch_requests)}")
            
            # Limpiar archivo temporal
            try:
                os.remove(temp_batch_file)
            except:
                pass
            
            return batch_info
            
        except Exception as e:
            self.logger.error(f"Error procesando chunks: {str(e)}")
            raise

    def _add_document_to_batch_from_blob(self, doc_name: str, project_name: str, batch_requests: List[Dict], documents_info: List[Dict], blob_client: BlobStorageClient, doc_type: str):
        """
        Añade un documento desde blob storage al batch job.
        
        Args:
            doc_name: Nombre del documento
            project_name: Nombre del proyecto
            batch_requests: Lista de requests del batch
            documents_info: Lista de información de documentos
            blob_client: Cliente de blob storage
            doc_type: Tipo de documento ('DI' o 'chunks')
        """
        try:
            # Determinar la subcarpeta según el tipo
            if doc_type == 'DI':
                subfolder = 'DI'
            else:  # chunks
                subfolder = 'chunks'
            
            # Descargar contenido del blob usando el método correcto
            doc_data = blob_client.load_processed_document(project_name, subfolder, doc_name)
            if not doc_data:
                self.logger.warning(f"No se pudo descargar el documento: {doc_name} desde {subfolder}")
                return
            
            # Asegurar que el nombre del documento esté en los datos
            if 'document_name' not in doc_data and 'filename' not in doc_data:
                doc_data['document_name'] = doc_name
            
            # Obtener prefijo del documento
            prefix = self._get_document_prefix(doc_data)
            self.logger.info(f"🔍 Documento: {doc_name}, Prefijo extraído: {prefix}")
            
            # Procesar con cada prompt según las reglas
            prompts_applied = []
            
            for prompt_num in [1, 2, 3]:
                should_process = self._should_process_with_prompt(doc_data, prompt_num)
                self.logger.info(f"📋 Prompt {prompt_num} para {doc_name}: {'✅ SÍ' if should_process else '❌ NO'}")
                if should_process:
                    custom_id = f"{project_name}_{Path(doc_name).stem}_prompt{prompt_num}"
                    prompt = self.prompts[f'prompt_{prompt_num}']
                    content = doc_data.get('content', '')
                    
                    batch_request = self._create_batch_request(custom_id, prompt, content)
                    batch_requests.append(batch_request)
                    
                    # Mapear número de prompt a tipo
                    prompt_types = {1: "auditoria", 2: "desembolsos", 3: "productos"}
                    prompts_applied.append(prompt_types[prompt_num])
                    
                    self.logger.info(f"📄 Añadido al batch: {custom_id} (Prefijo: {prefix})")
            
            # Añadir información del documento solo si se aplicaron prompts
            if prompts_applied:
                documents_info.append({
                    "document_name": doc_name,
                    "document_type": doc_type,
                    "subfolder": subfolder,
                    "prefix": prefix,
                    "prompts_applied": prompts_applied,
                    "processed_at": datetime.now().isoformat()
                })
                self.logger.info(f"📄 Documento agregado: {doc_name} (prompts: {prompts_applied})")
            else:
                self.logger.info(f"⏭️ Saltando documento: {doc_name} (no aplica ningún prompt)")
            
        except Exception as e:
            self.logger.error(f"Error procesando documento {doc_name}: {str(e)}")
            raise

    def _add_document_to_batch(self, doc_path: str, project_name: str, batch_requests: List[Dict], documents_info: List[Dict]):
        """
        Agrega un documento al batch con los prompts aplicables.
        
        Args:
            doc_path: Ruta al documento
            project_name: Nombre del proyecto
            batch_requests: Lista de requests del batch
            documents_info: Lista de información de documentos
        """
        try:
            # Cargar contenido del documento
            with open(doc_path, 'r', encoding='utf-8') as f:
                document_content = json.load(f)
            
            document_content['project_name'] = project_name
            content_text = document_content.get('content', '')
            
            # Extraer información del documento
            document_name = document_content.get('document_name', document_content.get('filename', Path(doc_path).stem))
            chunk_index = None
            if '_chunk_' in str(doc_path):
                chunk_match = re.search(r'_chunk_(\d+)', str(doc_path))
                if chunk_match:
                    chunk_index = int(chunk_match.group(1))
            
            doc_info = {
                "document_name": document_name,
                "file_path": doc_path,
                "chunk_index": chunk_index,
                "prefix": self._get_document_prefix(document_content),
                "prompts_applied": []
            }
            
            # Verificar y agregar prompts aplicables
            prompts = [
                (1, "auditoria", self.prompt_auditoria),
                (2, "desembolsos", self.prompt_desembolsos),
                (3, "productos", self.prompt_productos)
            ]
            
            for prompt_num, prompt_type, prompt_text in prompts:
                if self._should_process_with_prompt(document_content, prompt_num):
                    custom_id = f"{project_name}_{document_name}_{prompt_type}"
                    if chunk_index is not None:
                        custom_id += f"_chunk_{chunk_index:03d}"
                    
                    request = self._create_batch_request(custom_id, prompt_text, content_text)
                    batch_requests.append(request)
                    doc_info["prompts_applied"].append(prompt_type)
            
            if doc_info["prompts_applied"]:
                documents_info.append(doc_info)
                self.logger.info(f"📄 Agregado al batch: {document_name} (prompts: {doc_info['prompts_applied']})")
            else:
                self.logger.info(f"⏭️ Saltando documento: {document_name} (no aplica ningún prompt)")
                
        except Exception as e:
            self.logger.error(f"Error procesando documento {doc_path}: {str(e)}")
            raise