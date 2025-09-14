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
from shared_code.utils.cosmo_db_client import CosmosDBClient

# Prompts como constantes
PROMPT_AUDITORIA = '''

prompt - Agente Auditoria

Eres un Analista experto en documentos de auditoría de proyectos del Banco CAF.
Tu tarea es extraer todas las variables del formato Auditorías a partir de documentos IXP, interpretar las opiniones de auditores externos y emitir un concepto final (Favorable / Favorable con reservas / Desfavorable) con justificación breve.

Debes trabajar con rigor: no inventes, usa sinónimos y variantes, y aplica un checklist antes de concluir que algo no existe.

Prioridad documental:

Solo documentos cuyo nombre inicia con IXP.

Si hay múltiples versiones, usa la más reciente y registra cambios en observacion.

CFA y CFX son códigos distintos, deben extraerse por separado.

Checklist anti–“NO EXTRAIDO”:

Agota en este orden antes de marcar un campo como NO_EXTRAIDO:

Portada / primeras 2 páginas → Código CFA, CFX, Contrato del préstamo, Fecha del informe.

Índice → saltos a Opinión / Dictamen / Conclusión (variantes ES/PT/EN: “Opinion”, “Unqualified opinion”, “Parecer”, “Sem ressalvas”, “Conclusão”, “Observación”).

Secciones válidas de concepto → Opinión, Dictamen, Conclusión de auditoría.

Tablas administrativas → (solo si el campo es SSC, ver “Gating por fuente”) Estado, Fecha de vencimiento, Fecha de cambio de estado.

Encabezados/pies → “Última revisión”, “Actualización”, “Fecha del informe”.

Anexos / Carta de gerencia → posibles dictámenes del auditor.

Dónde buscar (por campo)

codigo_CFA: portada/primeras páginas. Variantes: “Código de operación CFA”, “Op. CFA”, “Operación CFA”.

codigo_CFX: cabeceras o secciones administrativas/financieras. Variantes: “Código CFX”, “Op. CFX”.

opiniones (control interno / licitación / uso de recursos / unidad ejecutora): solo en Opinión/Dictamen/Conclusión → lenguaje sobre suficiencia/deficiencias, adquisiciones/procurement, conformidad vs plan, desempeño UGP.

fecha_ultima_revision: encabezados/pies (“Última revisión/Actualización”).

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

estado_informe_norm ∈ {dispensado, normal, satisfecho, vencido, null}

informe_externo_entregado_norm ∈ {a tiempo, dispensado, vencido, null}

concepto_*_norm ∈ {Favorable, Favorable con reservas, Desfavorable, no se menciona}

Heurísticas rápidas (few-shot):

“sin salvedades / no reveló deficiencias significativas” → Favorable.

“excepto por… / con salvedades” → Favorable con reservas.

“se sostienen deficiencias / incumplimiento” → Desfavorable.

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
{
  "codigo_CFA": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "codigo_CFX": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "estado_informe_SSC": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "estado_informe_SSC_norm": "null",

  "informe_auditoria_externa_se_entrego_SSC": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "informe_auditoria_externa_se_entrego_SSC_norm": "null",

  "concepto_control_interno": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "concepto_control_interno_norm": "no se menciona",

  "concepto_licitacion": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "concepto_licitacion_norm": "no se menciona",

  "concepto_uso_recursos": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "concepto_uso_recursos_norm": "no se menciona",

  "concepto_unidad_ejecutora": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "concepto_unidad_ejecutora_norm": "no se menciona",

  "fecha_vencimiento_SSC": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "fecha_cambio_estado_informe_SSC": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "fecha_extraccion": "YYYY-MM-DD HH:MM",
  "fecha_ultima_revision": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "status_auditoria_SSC": "Pendiente",
  "nombre_archivo": "IXP_....pdf",

  "texto_justificacion": { "quote": null}
}
'''

PROMPT_DESEMBOLSOS = '''

Prompt — Agente Desembolsos 

Eres un analista de cartera experto en seguimiento de desembolsos de proyectos CAF. Debes extraer desembolsos del proyecto por parte de CAF, sin convertir moneda, deduplicando por período + moneda y normalizando la fuente.
No inventes: si no hay evidencia suficiente, deja value=null y confidence="NO_EXTRAIDO".

Prioridad documental:

Jerarquía: ROP > INI > DEC.

Proyectados: buscar primero en Cronograma/Programación/Calendario (ROP/INI); si no hay, usar DEC.

Realizados: “Detalle/Estado de desembolsos”, EEFF o narrativa (en cualquier documento).

En duplicados/versiones: usar la versión más reciente y registrar cambios en observacion (periodificación, montos, moneda, fuente, documento).

Checklist anti–“NO_EXTRAIDO” (agotar en orden)

Tablas: cronograma/estado/flujo de caja.

Columnas típicas: Fecha/Período | Monto | Moneda | Fuente/Tipo (+ “Equivalente USD” si existe).

Narrativa/EEFF: “Desembolsos efectuados/realizados/pagos ejecutados/transferencias realizadas”.

Encabezados/pies: “Última revisión/Actualización/Versión”.

Si tras agotar el checklist no hay evidencia para un campo específico, deja ese campo como NO_EXTRAIDO.
Pero si existen período y monto, emite el registro.

Dónde buscar (por campo):

Código de operación (CFA): portada/primeras páginas, cabecera del cronograma, secciones administrativas. Variantes: “CFA”, “Código CFA”, “Operación CFA”, “Op. CFA”.

Fecha de desembolso (período):

“Detalle/Estado de desembolsos”, “Desembolsos efectuados/realizados”, “Pagos ejecutados”, “Transferencias realizadas”, “Cronograma/Programación/Calendario de desembolsos”, “Flujo de caja”, “Proyección financiera”.

Formatos válidos: YYYY, YYYY-MM, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY, Enero 2023, Q1 2023, Trimestre 1, Semestre 2, 2024-06.

Monto desembolsado CAF (monto_original): columna “Monto/Importe/Desembolsado/Valor/Total” (extrae número puro, sin símbolos y sin conversiones).

moneda: columna “Moneda” o heredar desde título/cabecera/leyenda de la tabla (p. ej. “(USD)”, “Moneda: PEN”) → entonces confidence="EXTRAIDO_INFERIDO" con evidencia de la leyenda.

monto_usd: solo si hay columna/registro explícito en USD o “Equivalente USD”. No crear fila aparte en USD si ya existe la moneda original para el mismo período/tipo_registro (ver DEDUP).

Fuente CAF (fuente_etiqueta): etiqueta clara: “CAF Realizado”, “Proyectado (Cronograma)”, “Anticipo”, “Pago directo”, “Reembolso”, con referencia de documento (p. ej. “(ROP)”, “(INI)”, “(DEC)” si está indicada).

Fecha de última revisión: encabezados/pies o notas (“Última revisión/Actualización/Fecha del documento/Versión/Modificado/Revisado el”).

Nombre del archivo revisado: documento del que proviene el dato final.

Reglas de extracción y deduplicación:

Tabla-primero: prioriza tablas sobre narrativa.

No convertir moneda ni inferir fechas/moneda no sustentadas.

Prioriza moneda original; conserva monto_usd solo si viene explícito en la tabla (o si no hay registro en moneda original).

DEDUP estricta: no repitas mismo período + misma moneda + mismo tipo_registro. Conserva la fila más reciente/consistente y registra diferencias en observacion.

Ambigüedad de fecha: usa el literal (Q1 2025, 2026, etc.); no expandas a fechas exactas.

tipo_registro_norm ∈ {proyectado, realizado} (derivado de la sección/tabla/fuente).

Niveles de confianza (por campo):

Cada variable se representa como objeto con:

value (string/num o null),

confidence: EXTRAIDO_DIRECTO | EXTRAIDO_INFERIDO | NO_EXTRAIDO,

evidence (cita breve literal o cercana),

Normalización:

fuente_norm (opcional) → {CAF Realizado, Proyectado (Cronograma), Anticipo, Pago directo, Reembolso, Transferencia, Giro, null}.

tipo_registro_norm → {proyectado, realizado}.

moneda → mantener código/etiqueta tal como aparece (no normalizar a ISO si no está explícito, salvo equivalentes claros como “US$”→“USD”).

Reglas de salida (cardinalidad y formato)

Cardinalidad

Detecta todos los registros de desembolso en el/los documento(s).
Por CADA registro identificado (unidad mínima = período/fecha × moneda × tipo_registro):
EMITE UNA (1) instancia del esquema completo “Esquema de salida JSON (por registro)”.
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
{
  "codigo_CFA": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "tipo_registro": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "tipo_registro_norm": null,  // proyectado | realizado

  "fecha_desembolso": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "monto_original": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "moneda": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "monto_usd": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "fuente_etiqueta": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },

  "fuente_norm": null,  // CAF Realizado | Proyectado (Cronograma) | Anticipo | Pago directo | Reembolso | Transferencia | Giro | null

  "fecha_extraccion": "YYYY-MM-DD HH:MM",

  "fecha_ultima_revision": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },

  "nombre_archivo": "ROP_....pdf"
}
'''

PROMPT_PRODUCTOS = ''' 
Prompt — Agente Productos 

Eres un Analista de Cartera experto en proyectos CAF.
Debes identificar todos los productos comprometidos en el proyecto y generar las filas solicitadas por cada producto, separando meta numérica y unidad, normalizando campos y dejando claro el estado de extracción.

Importante: no emites concepto final.

Prioridad documental:

Jerarquía: ROP > INI > DEC > IFS > Anexo Excel (si lo cita el índice).

En duplicados: usar la versión más reciente; si cambian valores, registrar en observacion.

Checklist anti–“NO_EXTRAIDO”:

Tablas/Matrices → “Matriz de Indicadores”, “Marco Lógico”, “Metas físicas”.

Narrativo → “Resultados esperados”, “Componentes”, “Seguimiento de indicadores” (IFS).

Anexos/Excel → cuando estén citados en índice.

Encabezados/pies → “Última revisión/Actualización”.

Dónde buscar (por campo):

Código CFA / CFX: portada, primeras páginas, marcos lógicos, carátulas.

Descripción de producto: títulos/filas en matrices, POA, componentes, IFS.

Meta del producto / Meta unidad: columnas de metas → separa número/unidad (230 km → meta_num=230, meta_unidad=km).

Fuente del indicador: columna/nota “Fuente” (ROP, INI, DEC, IFS, SSC).

Fecha cumplimiento de meta: “Fecha meta”, “Fecha de cumplimiento”, “Plazo”.

Tipo de dato: pendiente/proyectado/realizado (claves: programado, estimado, alcanzado).

Característica: {administración, capacitación, fortalecimiento institucional, infraestructura}.

Check_producto: “Sí” si corresponde inequívocamente a producto (no resultado).

Fecha última revisión: encabezados/pies.

Reglas especiales:

Validar producto vs resultado → no confundir.

Acumulado vs período → si es acumulativo, no dupliques registros.

Idiomas/formatos → aceptar ES/PT/EN y tablas rotadas.

Separación meta/unidad → reconocer variantes: “230 kilómetros”, “1.500 personas”, “100%”, “2,5 ha”.

No inventar → si falta meta o unidad, deja null.

Niveles de confianza:

Cada variable incluye:

value (dato literal o null).

confidence: EXTRAIDO_DIRECTO | EXTRAIDO_INFERIDO | NO_EXTRAIDO.

evidence: cita breve literal o cercana.

Normalización:

tipo_dato_norm ∈ {pendiente, proyectado, realizado, null}.

caracteristica_norm ∈ {administracion, capacitacion, fortalecimiento institucional, infraestructura, null}.

meta_num: número puro (ej. 230 de “230 km”).

meta_unidad_norm: catálogo controlado (%, km, personas, m², m³, horas, hectáreas, kVA, MVA, l/s, galones, miles gal/día, toneladas, cantidad/año, miles m², etc.).

Few-shot (patrones típicos):

“230 km de carretera” → meta_num=230, meta_unidad_norm=km.

“1,500 personas capacitadas” → meta_num=1500, meta_unidad_norm=personas, caracteristica_norm=capacitacion.

“Resultado alcanzado” → tipo_dato_norm=realizado.

“Meta programada para 2024” → tipo_dato_norm=proyectado.

“Talleres de capacitación” → caracteristica_norm=capacitacion.

Reglas de salida:
Detecta todos los productos en el/los documento(s).
Por CADA producto identificado:
EMITE UNA (1) instancia del esquema completo “Esquema de salida JSON (por producto)”.
No agregues ni elimines claves del esquema.
No mezcles datos de productos distintos en la misma instancia.
No incluyas texto adicional fuera de las líneas JSON.
Mantén el orden de las claves tal como está definido en “Esquema de salida JSON (por producto)”.
Si no hay evidencia → value=null, confidence="NO_EXTRAIDO".

fecha_extraccion: fecha-hora actual del sistema.
nombre_archivo: documento fuente.

Esquema de salida JSON (por producto)
{
  "codigo_CFA": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "codigo_CFX": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },

  "descripcion_producto": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },

  "meta_producto": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "meta_unidad": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "meta_num": null,
  "meta_unidad_norm": null,

  "fuente_indicador": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},
  "fecha_cumplimiento_meta": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null},

  "tipo_dato": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "tipo_dato_norm": null,

  "caracteristica": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },
  "caracteristica_norm": null,

  "check_producto": "No",

  "fecha_extraccion": "YYYY-MM-DD HH:MM",
  "fecha_ultima_revision": { "value": null, "confidence": "NO_EXTRAIDO", "evidence": null },

  "nombre_archivo": "ROP_....pdf",
 }
'''

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
                'prompt_1': PROMPT_AUDITORIA,
                'prompt_2': PROMPT_PRODUCTOS, 
                'prompt_3': PROMPT_DESEMBOLSOS
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
            allowed_prefixes = ['ROP', 'INI', 'DEC', 'IFS']
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
        # Manifest detallado para auditoría: prompt + contexto por request
        requests_manifest: List[Dict[str, Any]] = []
        
        try:
            blob_client = BlobStorageClient()
            
            # Procesar documentos DI desde blob storage
            di_documents = blob_client.list_processed_documents(project_name)
            for doc_name in di_documents:
                if doc_name.endswith('.json'):
                    self._add_document_to_batch_from_blob(
                        doc_name, project_name, batch_requests, documents_info, blob_client, 'DI', requests_manifest
                    )
            
            # Procesar chunks desde blob storage
            chunk_documents = blob_client.list_chunks(project_name)
            for chunk_name in chunk_documents:
                if chunk_name.endswith('.json'):
                    self._add_document_to_batch_from_blob(
                        chunk_name, project_name, batch_requests, documents_info, blob_client, 'chunks', requests_manifest
                    )
            
            if not batch_requests:
                raise ValueError(f"No se encontraron documentos para procesar en proyecto {project_name}")
            
            # Crear archivo JSONL temporal (formato requerido por Azure Batch API)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
                for request in batch_requests:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
                batch_input_file = f.name
            
            self.logger.info(f"📄 Archivo batch temporal creado: {batch_input_file} ({len(batch_requests)} requests)")
            
            # Subir archivo a Azure asegurando cierre del handle en Windows
            with open(batch_input_file, "rb") as fh:
                uploaded = self.client.files.create(
                    file=fh,
                    purpose="batch"
                )
            
            # Limpiar archivo temporal (handle ya cerrado)
            try:
                os.unlink(batch_input_file)
            except Exception as e:
                self.logger.warning(f"No se pudo eliminar archivo temporal {batch_input_file}: {str(e)}")
            
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

            # Guardar manifest con prompt + contexto por request (para auditoría)
            try:
                manifest_path = f"basedocuments/{project_name}/processed/openai_logs/batch_payload_{project_name}_{batch.id}.jsonl"
                lines = []
                for item in requests_manifest:
                    lines.append(json.dumps(item, ensure_ascii=False))
                manifest_bytes = ("\n".join(lines)).encode('utf-8')
                blob_client.upload_blob(manifest_path, manifest_bytes, content_type='application/x-ndjson')
                self.logger.info(f"🧾 Manifest de prompts/contexto guardado en blob: {manifest_path}")
            except Exception as e:
                self.logger.warning(f"No se pudo guardar el manifest de requests: {str(e)}")
            
            # Marcar en CosmosDB que el proyecto tiene un batch pendiente (best-effort)
            try:
                sharepoint_folder = os.environ.get("SHAREPOINT_FOLDER")
                container_folder = os.environ.get("COSMOS_CONTAINER_FOLDER")
                if sharepoint_folder and container_folder:
                    doc_id = f"{sharepoint_folder}|{project_name}"
                    cdb = CosmosDBClient()
                    doc = cdb.read_item(doc_id, doc_id, container_folder)
                    if doc is not None:
                        doc["isBatchPending"] = True
                        doc["jobBatchId"] = batch.id
                        cdb.upsert_item(doc, container_folder)
                        self.logger.info(f"CosmosDB folder marked pending: {doc_id}")
                else:
                    self.logger.warning("Cosmos env vars missing (SHAREPOINT_FOLDER/COSMOS_CONTAINER_FOLDER); skipping pending mark")
            except Exception as e:
                self.logger.warning(f"Could not mark CosmosDB pending for project {project_name}: {str(e)}")

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
            
            # Subir archivo a Azure (asegurar cierre de handle)
            with open(temp_batch_file, "rb") as fh:
                uploaded = self.client.files.create(
                    file=fh,
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

            # Best-effort: marcar en Cosmos que el proyecto/documento tiene batch pendiente
            try:
                # Si los chunks vienen del flujo de documento individual, inferir project_name del document_name si es posible
                project_name = os.environ.get("CURRENT_PROJECT_NAME")  # opcional si se setea antes
                # No siempre tenemos proyecto aquí; por compatibilidad, no forzar.
                sharepoint_folder = os.environ.get("SHAREPOINT_FOLDER")
                container_folder = os.environ.get("COSMOS_CONTAINER_FOLDER")
                if project_name and sharepoint_folder and container_folder:
                    doc_id = f"{sharepoint_folder}|{project_name}"
                    cdb = CosmosDBClient()
                    doc = cdb.read_item(doc_id, doc_id, container_folder)
                    if doc is not None:
                        doc["isBatchPending"] = True
                        doc["jobBatchId"] = batch.id
                        cdb.upsert_item(doc, container_folder)
                        self.logger.info(f"CosmosDB folder marked pending (chunks): {doc_id}")
            except Exception as e:
                self.logger.warning(f"Could not mark CosmosDB pending (chunks): {str(e)}")

            return batch_info
            
        except Exception as e:
            self.logger.error(f"Error procesando chunks: {str(e)}")
            raise

    def _add_document_to_batch_from_blob(self, doc_name: str, project_name: str, batch_requests: List[Dict], documents_info: List[Dict], blob_client: BlobStorageClient, doc_type: str, requests_manifest: Optional[List[Dict[str, Any]]] = None):
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
                    prompt_types = {1: "auditoria", 2: "productos", 3: "desembolsos"}
                    prompts_applied.append(prompt_types[prompt_num])
                    
                    # Agregar entrada al manifest (prompt + contexto)
                    if requests_manifest is not None:
                        requests_manifest.append({
                            "custom_id": custom_id,
                            "prompt_number": prompt_num,
                            "prompt_type": prompt_types[prompt_num],
                            "prompt_text": prompt,
                            "context": content,
                            "document_name": doc_name,
                            "document_type": doc_type,
                            "subfolder": subfolder,
                            "prefix": prefix,
                            "created_at": datetime.now().isoformat()
                        })
                    
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
                (2, "productos", self.prompt_productos),
                (3, "desembolsos", self.prompt_desembolsos)
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
