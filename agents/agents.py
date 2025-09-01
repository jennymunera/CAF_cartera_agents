from crewai import Agent
from config.settings import Settings

# Configuration
settings = Settings()

# Function to get LLM lazily
def get_configured_llm():
    try:
        return settings.get_llm()
    except Exception as e:
        print(f"Could not configure LLM: {e}")
        print("Configure OPENAI_API_KEY in the .env file to use the agents")
        return None

# Agentes especializados
agente_auditorias = Agent(
    role="Especialista en Auditorías",
    goal="Extraer y analizar información de auditorías con prioridad IXP",
    backstory="""Eres un especialista en auditorías con experiencia en análisis
    de documentos financieros. Tu especialidad es identificar hallazgos de auditoría,
    recomendaciones y observaciones, priorizando información de tipo IXP.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)

agente_productos = Agent(
    role="Especialista en Productos",
    goal="Extraer información de productos con prioridad ROP>INI>DEC>IFS",
    backstory="""Eres un especialista en productos financieros con experiencia
    en análisis de documentos. Tu especialidad es identificar información de productos,
    priorizando ROP, luego INI, DEC e IFS.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)

agente_desembolsos = Agent(
    role="Especialista en Desembolsos",
    goal="Extraer información de desembolsos con prioridad ROP>INI>DEC",
    backstory="""Eres un especialista en desembolsos con experiencia en análisis
    de documentos financieros. Tu especialidad es identificar información de desembolsos,
    priorizando ROP, luego INI y DEC.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)

# Agentes expertos en conceptos
agente_experto_auditorias = Agent(
    role="Experto en Conceptos de Auditoría",
    goal="Asignar concepto final a información de auditorías: Favorable, Favorable con salvedades, o Desfavorable",
    backstory="""Eres un experto en evaluación de auditorías con años de experiencia
    en clasificación de hallazgos. Tu especialidad es determinar el concepto final
    basado en la información procesada por el agente de auditorías.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)

agente_experto_productos = Agent(
    role="Experto en Conceptos de Productos",
    goal="Asignar concepto final a información de productos: Favorable, Favorable con salvedades, o Desfavorable",
    backstory="""Eres un experto en evaluación de productos financieros con años
    de experiencia en clasificación de riesgos. Tu especialidad es determinar
    el concepto final basado en la información procesada por el agente de productos.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)

agente_experto_desembolsos = Agent(
    role="Experto en Conceptos de Desembolsos",
    goal="Asignar concepto final a información de desembolsos: Favorable, Favorable con salvedades, o Desfavorable",
    backstory="""Eres un experto en evaluación de desembolsos con años de experiencia
    en análisis de riesgos financieros. Tu especialidad es determinar el concepto final
    basado en la información procesada por el agente de desembolsos.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)

# Agente concatenador final
agente_concatenador = Agent(
    role="Concatenador Final",
    goal="Consolidar y generar CSVs finales con toda la información procesada",
    backstory="""Eres un especialista en consolidación de datos con experiencia
    en generación de reportes. Tu especialidad es tomar la información procesada
    por todos los agentes y generar CSVs finales estructurados.""",
    verbose=True,
    allow_delegation=False,
    llm=get_configured_llm()
)