# Agentes del proyecto CrewAI - Sistema de 7 agentes
# Importa todos los agentes especializados, expertos y concatenador

from .agents import (
    agente_auditorias,
    agente_productos,
    agente_desembolsos,
    agente_experto_auditorias,
    agente_experto_productos,
    agente_experto_desembolsos,
    agente_concatenador
)

# Lista de todos los agentes disponibles (7 agentes)
__all__ = [
    # Agentes especializados (3)
    'agente_auditorias',
    'agente_productos', 
    'agente_desembolsos',
    # Agentes expertos (3)
    'agente_experto_auditorias',
    'agente_experto_productos',
    'agente_experto_desembolsos',
    # Agente concatenador (1)
    'agente_concatenador'
]