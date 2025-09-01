# CrewAI + Docling: Sistema de Análisis de Documentos Financieros

## Descripción General

Este proyecto implementa un sistema inteligente que combina **Docling** para el procesamiento avanzado de documentos y **CrewAI** para la orquestación de agentes especializados. El sistema procesa documentos financieros (PDF, XLSX, Word, etc.) y extrae información estructurada mediante agentes especializados en auditorías, productos y desembolsos.

### Características Principales
- Procesamiento avanzado de documentos con **Docling**
- Sistema de 7 agentes especializados con **CrewAI**
- Extracción inteligente de datos financieros
- Detección automática de versiones y cambios
- Generación de reportes CSV estructurados
- Trazabilidad completa de origen de datos
- Suite completa de tests automatizados

## 2. Functional Requirements

### 2.1 Knowledge Base (Docling)
- Browse the documents folder.
- Convert each file to `DoclingDocument`, preserving origin metadata.
- Concatenate documents into one that preserves that traceability.

### 2.2 Specialized Agents (independent by format)
Each agent must:
- Apply priority to documents according to format:
  - Audits: files that start with `IXP`.
  - Products: priority `ROP > INI > DEC > IFS`.
  - Disbursements: priority `ROP > INI > DEC`.
- Extract the defined variables; if data is missing, use **"NOT EXTRACTED"**.
- Detect new versions or changes and reflect them in **"Observation"**.

#### 2.2.1 Audit Agent
Variables to extract:
- CFA Code
- Report status
- External audit report (Yes/No)
- Concepts from sections like "Opinion", "Ruling", etc.:
  - Internal control
  - Project bidding
  - Use of planned financial resources
  - Executing unit
- Due date
- Status change date
- Extraction date (timestamp)
- Last review date
- Audit status
- CFX Code
- Source file name
- Justification text
- Observation (when new version or change exists).

#### 2.2.2 Product Agent
For each identified product:
- Apply file priority (ROP, INI, DEC, IFS).
- Extract: CFA Code, description, target, unit, indicator source, compliance date, data type, characteristic, check_product, extraction date, last review, CFX code.
- Indicate delay if effective date > target.
- Observation (if there is new version or change).

#### 2.2.3 Disbursement Agent
Extract:
- Operation code (CFX)
- Disbursement date (CAF)
- CAF Amount
- CAF Amount in USD
- CAF Source
- Extraction date
- Last review date
- Observation (if there is new version or change).

### 2.3 Concept Expert Agents
Each specialized agent sends its output to the corresponding expert agent, which assigns a **final concept**:

#### 2.3.1 Audit Expert Agent
Receives output from the Audit Agent and assigns final concept:
- Favorable
- Favorable with reservations
- Unfavorable

#### 2.3.2 Product Expert Agent
Receives output from the Product Agent and assigns final concept:
- Favorable
- Favorable with reservations
- Unfavorable

#### 2.3.3 Disbursement Expert Agent
Receives output from the Disbursement Agent and assigns final concept:
- Favorable
- Favorable with reservations
- Unfavorable

### 2.4 Final Concatenator Agent
- Receives structured outputs from specialized agents.
- Generates three final CSV files: Audits, Products and Disbursements.
- Each CSV includes all defined columns (including "Observation" and data origin), with one row per record.

## 3. Suggested Architecture

```
Documents folder
│
DoclingDocument (with provenance)
│
├─> Audit Agent (IXP priority) ──> Audit Expert Agent
├─> Product Agent (ROP>INI>DEC>IFS priority) ──> Product Expert Agent
└─> Disbursement Agent (ROP>INI>DEC priority) ──> Disbursement Expert Agent
                                    │
                                    ▼
                            Final Concatenator Agent
                                    │
                                    ▼
                    Final CSVs: Audits / Products / Disbursements
```

**Total: 7 agents**
- 3 specialized agents (Audits, Products, Disbursements)
- 3 expert agents (one for each specialized)
- 1 final concatenator agent

## 4. Implementation Guide
- Configure Docling to preserve provenance.
- Create 3 specialized agents in CrewAI with priorities, extraction and version detection.
- Create 3 expert agents (one for each specialized) for concept classification.
- Develop 1 concatenator agent for final CSVs.
- Test the entire pipeline with the 7 agents and validate priority, origin and observation logic.

## 5. Usage Example
- Inputs: documents folder.
- Processing: Docling → specialized agents → expert agents → concatenator.
- Outputs: three CSVs with structured data and observations.

## 6. Technical Notes
Recommendations: use Python (CLI or API of Docling and CrewAI), YAML for agent configuration, version control, automated testing, define CSV formats (delimiter, encoding, names).

## Estructura del Proyecto

```
Agentes Jen/
├── agents/                    # Módulo de agentes CrewAI
│   ├── __init__.py
│   └── agents.py                 # 7 agentes especializados
├── config/                    # Configuración del sistema
│   └── settings.py               # Configuraciones centralizadas
├── tasks/                     # Definición de tareas
│   ├── __init__.py
│   └── task.py                   # Tareas para cada agente
├── test/                      # Suite de tests
│   ├── __init__.py
│   ├── conftest.py               # Configuración de pytest
│   ├── test_crewai_workflow.py   # Tests del workflow CrewAI
│   ├── test_docling_processor.py # Tests del procesador Docling
│   ├── test_integration.py       # Tests de integración
│   ├── test_integration_pipeline.py # Tests del pipeline completo
│   └── test_system.py            # Tests del sistema completo
├── input_docs/                # Documentos de entrada
│   ├── CFA009660/               # Proyecto ejemplo 1
│   ├── CFA009757/               # Proyecto ejemplo 2
│   ├── CFA010061/               # Proyecto ejemplo 3
│   └── CFA010515/               # Proyecto ejemplo 4
├── output_docs/               # Documentos procesados
├── docling_processor.py       # Procesador de documentos Docling
├── main.py                    # Script principal del sistema
├── run_tests.py               # Script para ejecutar tests
├── pytest.ini                # Configuración de pytest
├── requirements.txt           # Dependencias del proyecto
├── .env                       # Variables de entorno
├── context.md                 # Contexto del proyecto
├── REPORTE_FINAL_SISTEMA.md   # Reporte final del sistema
└── README.md                  # Este archivo
```

## Instalación

### Prerrequisitos
- Python 3.8 o superior
- Miniconda o Anaconda (recomendado)
- Clave API de OpenAI

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd "Agentes Jen"
```

### 2. Crear entorno virtual con Miniconda
```bash
# Crear entorno
conda create -n crewai-docling python=3.11

# Activar entorno
conda activate crewai-docling
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Verificar instalación
```bash
# Ejecutar tests para verificar que todo funciona
python run_tests.py
```

## Configuración

### 1. Variables de entorno
Crea un archivo `.env` en la raíz del proyecto:
```bash
# Configuración de OpenAI
OPENAI_API_KEY=tu_clave_api_aqui
OPENAI_MODEL_NAME=gpt-4-turbo-preview

# Configuración del proyecto
PROJECT_NAME=CrewAI_Docling_System
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 2. Verificar configuración
```python
from config.settings import Settings
settings = Settings()
print(f"Modelo configurado: {settings.OPENAI_MODEL_NAME}")
```

## Uso del Sistema

### 1. Procesamiento de documentos con Docling
```python
from docling_processor import DoclingProcessor

# Crear procesador
processor = DoclingProcessor()

# Procesar documentos de un proyecto específico
result = processor.process_project_documents("CFA009660")
print(f"Documentos procesados: {result['total_documents']}")
```

### 2. Ejecución del sistema completo
```bash
# Ejecutar el pipeline completo
python main.py

# O procesar un proyecto específico
python main.py --project CFA009660
```

### 3. Ejecutar tests
```bash
# Todos los tests
python run_tests.py

# Tests específicos
pytest test/test_docling_processor.py -v
 pytest test/test_integration.py -v
 ```

## Arquitectura Técnica

### Sistema de 7 Agentes CrewAI

#### Agentes Especializados (3)
1. **Agente de Auditorías** - Prioridad IXP
2. **Agente de Productos** - Prioridad ROP > INI > DEC > IFS
3. **Agente de Desembolsos** - Prioridad ROP > INI > DEC

#### Agentes Expertos (3)
4. **Experto en Auditorías** - Conceptos: Favorable/Con reservas/Desfavorable
5. **Experto en Productos** - Evaluación de cumplimiento y retrasos
6. **Experto en Desembolsos** - Análisis de montos y fechas

#### Agente Coordinador (1)
7. **Concatenador Final** - Genera CSVs consolidados

### Flujo de Procesamiento
```
Documentos → Docling → Agentes Especializados → Agentes Expertos → Concatenador → CSVs
```

## Dependencias Principales

| Dependencia | Versión | Propósito |
|-------------|---------|----------|
| `crewai` | >=0.28.8 | Orquestación de agentes |
| `docling` | >=1.0.0 | Procesamiento de documentos |
| `openai` | >=1.12.0 | Modelos de lenguaje |
| `langchain` | >=0.1.0 | Framework LLM |
| `pandas` | >=2.0.0 | Manipulación de datos |
| `pytest` | >=7.4.0 | Testing framework |

## Suite de Tests

### Tests Implementados
- **test_docling_processor.py** - Tests del procesador Docling
- **test_crewai_workflow.py** - Tests del workflow CrewAI
- **test_integration.py** - Tests de integración básica
- **test_integration_pipeline.py** - Tests del pipeline completo
- **test_system.py** - Tests del sistema end-to-end

### Cobertura de Tests
```bash
# Ejecutar con cobertura
pytest --cov=. --cov-report=html

# Ver reporte de cobertura
open htmlcov/index.html
```

## Salidas del Sistema

### Archivos CSV Generados
1. **auditorias.csv** - Información de auditorías procesadas
2. **productos.csv** - Datos de productos financieros
3. **desembolsos.csv** - Información de desembolsos

### Estructura de Datos
Cada CSV incluye:
- Datos extraídos específicos del dominio
- Columna "Observación" para cambios detectados
- Trazabilidad del documento origen
- Timestamps de procesamiento

## Contribución

### Desarrollo
1. Fork el repositorio
2. Crea una rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

### Estándares de Código
```bash
# Formateo de código
black .

# Linting
flake8 .

# Tests antes de commit
pytest
```

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## Soporte

Para soporte técnico o preguntas:
- Email: [tu-email@ejemplo.com]
- Issues: [GitHub Issues]
- Documentación: Ver `context.md` y `REPORTE_FINAL_SISTEMA.md`

---

**Desarrollado usando CrewAI y Docling**