"""Módulo de esquemas de validación JSON para agentes"""

from .validation_schemas import (
    AuditoriaSchema,
    AuditoriaExpertSchema,
    ProductoSchema,
    ProductoExpertSchema,
    DesembolsoSchema,
    DesembolsoExpertSchema,
    CorpusChunkSchema,
    validate_auditoria_record,
    validate_auditoria_expert_record,
    validate_producto_record,
    validate_producto_expert_record,
    validate_desembolso_record,
    validate_desembolso_expert_record,
    validate_corpus_chunk
)

__all__ = [
    'AuditoriaSchema',
    'AuditoriaExpertSchema',
    'ProductoSchema',
    'ProductoExpertSchema',
    'DesembolsoSchema',
    'DesembolsoExpertSchema',
    'CorpusChunkSchema',
    'validate_auditoria_record',
    'validate_auditoria_expert_record',
    'validate_producto_record',
    'validate_producto_expert_record',
    'validate_desembolso_record',
    'validate_desembolso_expert_record',
    'validate_corpus_chunk'
]