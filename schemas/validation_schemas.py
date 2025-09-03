from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# Esquema para Auditorías
class AuditoriaSchema(BaseModel):
    """Esquema de validación para registros de Auditorías"""
    codigo_cfa: str = Field(..., alias="Código CFA")
    estado_del_informe: str = Field(..., alias="Estado del informe")
    informe_auditoria_externo: str = Field(..., alias="Si se entregó informe de auditoría externo")
    concepto_control_interno: str = Field(..., alias="Concepto Control interno")
    concepto_licitacion: str = Field(..., alias="Concepto licitación de proyecto")
    concepto_uso_recursos: str = Field(..., alias="Concepto uso de recursos financieros según lo planificado")
    concepto_unidad_ejecutora: str = Field(..., alias="Concepto sobre unidad ejecutora")
    fecha_vencimiento: str = Field(..., alias="Fecha de vencimiento")
    fecha_cambio_estado: str = Field(..., alias="Fecha de cambio del estado del informe")
    fecha_extraccion: str = Field(..., alias="Fecha de extracción")
    fecha_ultima_revision: str = Field(..., alias="Fecha de ultima revisión")
    status_auditoria: str = Field(..., alias="status auditoría")
    codigo_cfx: str = Field(..., alias="código CFX")
    nombre_archivo_revisado: str = Field(..., alias="Nombre del archivo revisado")
    texto_justificacion: str = Field(..., alias="texto justificación")
    observacion: str = Field(..., alias="Observación")

    class Config:
        allow_population_by_field_name = True

# Esquema para Auditorías con campos normalizados por experto
class AuditoriaExpertSchema(AuditoriaSchema):
    """Esquema extendido con campos normalizados por experto"""
    estado_informe_norm: Optional[Literal["dispensado", "normal", "satisfecho", "vencido"]] = None
    informe_externo_entregado_norm: Optional[Literal["a tiempo", "dispensado", "vencido"]] = None
    concepto_control_interno_norm: Optional[Literal["Favorable", "Favorable con reservas", "Desfavorable", "no se menciona"]] = None
    concepto_licitacion_norm: Optional[Literal["Favorable", "Favorable con reservas", "Desfavorable", "no se menciona"]] = None
    concepto_uso_recursos_norm: Optional[Literal["Favorable", "Favorable con reservas", "Desfavorable", "no se menciona"]] = None
    concepto_unidad_ejecutora_norm: Optional[Literal["Favorable", "Favorable con reservas", "Desfavorable", "no se menciona"]] = None
    concepto_final: Literal["Favorable", "Favorable con reservas", "Desfavorable"]
    concepto_rationale: str = Field(..., description="Justificación de 1-2 frases para el concepto final")

# Esquema para Productos
class ProductoSchema(BaseModel):
    """Esquema de validación para registros de Productos"""
    codigo_cfa: str = Field(..., alias="Código CFA")
    descripcion_producto: str = Field(..., alias="descripción de producto")
    meta_producto: str = Field(..., alias="meta del producto", description="Solo número si es inequívoco, sino NO EXTRAIDO")
    meta_unidad: str = Field(..., alias="meta unidad", description="Unidad textual cruda")
    fuente_indicador: str = Field(..., alias="fuente del indicador")
    fecha_cumplimiento_meta: str = Field(..., alias="fecha cumplimiento de meta")
    tipo_dato: str = Field(..., alias="tipo de dato", description="Literal extraído")
    caracteristica: str = Field(..., alias="característica", description="Literal extraído")
    check_producto: str = Field(..., alias="check_producto")
    fecha_extraccion: str = Field(..., alias="fecha de extracción")
    fecha_ultima_revision: str = Field(..., alias="fecha de ultima revisión")
    codigo_cfx: str = Field(..., alias="código CFX")
    nombre_archivo_revisado: str = Field(..., alias="Nombre del archivo revisado")
    retraso: Literal["Sí", "No", "NO EXTRAIDO"] = Field(..., alias="Retraso")
    observacion: str = Field(..., alias="Observación")

    class Config:
        allow_population_by_field_name = True

# Esquema para Productos con campos normalizados por experto
class ProductoExpertSchema(ProductoSchema):
    """Esquema extendido con campos normalizados por experto"""
    tipo_dato_norm: Optional[Literal["pendiente", "proyectado", "realizado"]] = None
    caracteristica_norm: Optional[str] = Field(None, description="Normalizado a lista controlada")
    meta_num: Optional[float] = Field(None, description="Valor numérico separado cuando sea inequívoco")
    meta_unidad_norm: Optional[str] = Field(None, description="Unidad normalizada")
    concepto_final: Literal["Favorable", "Favorable con reservas", "Desfavorable"]
    concepto_rationale: str = Field(..., description="Justificación por producto")

# Esquema para Desembolsos
class DesembolsoSchema(BaseModel):
    """Esquema de validación para registros de Desembolsos"""
    codigo_operacion_cfx: str = Field(..., alias="Código de operación (CFX)")
    fecha_desembolso_caf: str = Field(..., alias="fecha de desembolso por parte de CAF")
    monto_desembolsado_caf: str = Field(..., alias="monto desembolsado CAF")
    monto_desembolsado_caf_usd: str = Field(..., alias="monto desembolsado CAF USD")
    fuente_caf: str = Field(..., alias="fuente CAF")
    fecha_extraccion: str = Field(..., alias="fecha de extracción")
    fecha_ultima_revision: str = Field(..., alias="fecha de ultima revisión")
    nombre_archivo_revisado: str = Field(..., alias="Nombre del archivo revisado")
    observacion: str = Field(..., alias="Observación")

    class Config:
        allow_population_by_field_name = True

# Esquema para Desembolsos con campos normalizados por experto
class DesembolsoExpertSchema(DesembolsoSchema):
    """Esquema extendido con campos normalizados por experto"""
    concepto_final: Literal["Favorable", "Favorable con reservas", "Desfavorable"]
    concepto_rationale: str = Field(..., description="Justificación para el concepto")
    # Campos opcionales de normalización de fuente
    fuente_caf_norm: Optional[str] = Field(None, description="Etiqueta de fuente normalizada")

# Esquema para Corpus JSONL
class CorpusChunkSchema(BaseModel):
    """Esquema para chunks del corpus JSONL"""
    id_chunk: str = Field(..., description="ID único del chunk")
    proyecto: str = Field(..., description="Nombre del proyecto")
    contenido: str = Field(..., description="Contenido del chunk")
    tokens: int = Field(..., description="Número de tokens del chunk")
    indice_chunk: int = Field(..., description="Índice del chunk")
    rango_secciones: str = Field(..., description="Rango de secciones incluidas")
    estrategia_chunking: str = Field(..., description="Estrategia de chunking utilizada")
    max_tokens_configurado: int = Field(..., description="Máximo de tokens configurado")
    overlap_tokens: int = Field(..., description="Tokens de solapamiento")
    timestamp_procesamiento: str = Field(..., description="Timestamp del procesamiento")
    fuente: str = Field(..., description="Fuente del procesamiento")
    version_esquema: str = Field(..., description="Versión del esquema")

# Funciones de validación
def validate_auditoria_record(data: dict) -> AuditoriaSchema:
    """Valida un registro de auditoría"""
    return AuditoriaSchema(**data)

def validate_auditoria_expert_record(data: dict) -> AuditoriaExpertSchema:
    """Valida un registro de auditoría con campos de experto"""
    return AuditoriaExpertSchema(**data)

def validate_producto_record(data: dict) -> ProductoSchema:
    """Valida un registro de producto"""
    return ProductoSchema(**data)

def validate_producto_expert_record(data: dict) -> ProductoExpertSchema:
    """Valida un registro de producto con campos de experto"""
    return ProductoExpertSchema(**data)

def validate_desembolso_record(data: dict) -> DesembolsoSchema:
    """Valida un registro de desembolso"""
    return DesembolsoSchema(**data)

def validate_desembolso_expert_record(data: dict) -> DesembolsoExpertSchema:
    """Valida un registro de desembolso con campos de experto"""
    return DesembolsoExpertSchema(**data)

def validate_corpus_chunk(data: dict) -> CorpusChunkSchema:
    """Valida un chunk del corpus JSONL"""
    return CorpusChunkSchema(**data)