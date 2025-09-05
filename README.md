# Sistema de Procesamiento de Documentos CAF

## 📋 Descripción

Sistema automatizado para el procesamiento y análisis de documentos de proyectos de CAF (Corporación Andina de Fomento) utilizando Azure Document Intelligence y Azure OpenAI. El sistema extrae información estructurada de documentos PDF y DOCX, los procesa con modelos de IA especializados y genera reportes JSON consolidados para auditoría, productos y desembolsos.

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Documentos     │    │   Azure Document │    │   Chunking      │
│  Input (PDF/    │───▶│   Intelligence   │───▶│   Processor     │
│  DOCX)          │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Archivos JSON  │◀───│   Azure OpenAI   │◀───│   Documentos    │
│  Consolidados   │    │   (3 Prompts)    │    │   Chunkeados    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Componentes Principales

1. **Document Intelligence Processor**: Extrae texto de documentos PDF/DOCX
2. **Chunking Processor**: Divide documentos grandes en chunks manejables
3. **OpenAI Processor**: Procesa documentos con 3 prompts especializados
4. **Process and Submit Batch Controller**: Orquesta todo el flujo de procesamiento

## 🚀 Instalación

### Prerrequisitos

- Python 3.8+
- Cuenta de Azure con servicios habilitados:
  - Azure Document Intelligence
  - Azure OpenAI

### Configuración

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd Agentes_jen_rebuild
```

2. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

3. **Configurar variables de entorno**

Copiar `.env.example` a `.env` y configurar:

```env
# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your-key

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure Application Insights (Opcional)
AZURE_APP_INSIGHTS_CONNECTION_STRING=InstrumentationKey=your-key;IngestionEndpoint=https://your-region.in.applicationinsights.azure.com/
AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY=your-instrumentation-key
```

## 📁 Estructura del Proyecto

```
Agentes_jen_rebuild/
├── 📄 process_and_submit_batch.py # Controlador principal
├── 📄 document_intelligence_processor.py  # Procesador Azure DI
├── 📄 chunking_processor.py       # Procesador de chunking
├── 📄 openai_processor.py         # Procesador Azure OpenAI
├── 📁 input_docs/                 # Documentos de entrada
│   └── 📁 CFA009660/             # Proyecto específico
├── 📁 output_docs/                # Documentos procesados
│   └── 📁 CFA009660/
│       ├── 📁 DI/                # Salida Document Intelligence
│       ├── 📁 chunks/            # Documentos chunkeados
│       ├── 📁 LLM_output/        # Salidas individuales OpenAI
│       │   ├── 📁 Auditoria/
│       │   ├── 📁 Productos/
│       │   └── 📁 Desembolsos/
│       ├── 📄 auditoria.json     # Consolidado auditoría
│       ├── 📄 productos.json     # Consolidado productos
│       └── 📄 desembolsos.json   # Consolidado desembolsos
├── 📁 schemas/                    # Esquemas de validación
├── 📁 utils/                     # Utilidades
│   ├── 📄 app_insights_logger.py # Logger estructurado con Azure App Insights
│   └── 📄 jsonl_handler.py       # Manejador de archivos JSONL
├── 📁 logs/                      # Archivos de log
├── 📄 logging_config.json        # Configuración de logging
└── 📁 tests/                     # Tests y debugging
```

## 🎯 Uso del Sistema

### Ejecución Básica

```bash
python process_and_submit_batch.py
```

### Flujo de Procesamiento

1. **Extracción de Texto**: Azure Document Intelligence convierte PDF/DOCX a markdown
2. **Chunking Inteligente**: Documentos grandes se dividen en chunks de ~90k tokens
3. **Procesamiento IA**: 3 prompts especializados procesan cada documento:
   - **Prompt 1 (Auditoría)**: Solo documentos IXP
   - **Prompt 2 (Productos)**: Documentos ROP, INI, DEC, IFS
   - **Prompt 3 (Desembolsos)**: Documentos ROP, INI, DEC
4. **Consolidación**: Resultados se concatenan en archivos JSON finales

## 📋 Tipos de Documentos Soportados

### Prefijos de Documentos

| Prefijo | Descripción | Prompts que lo procesan |
|---------|-------------|------------------------|
| **IXP** | Informes de Auditoría | Auditoría |
| **ROP** | Reportes de Operación | Productos, Desembolsos |
| **INI** | Informes Iniciales | Productos, Desembolsos |
| **DEC** | Declaraciones | Productos, Desembolsos |
| **IFS** | Informes de Seguimiento | Productos |
| **FFD** | Fichas de Finalización | - |
| **IVS** | Informes de Visita | - |
| **CON** | Contratos | - |
| **CC1/CC2** | Certificados de Cumplimiento | - |
| **RAS** | Reportes de Análisis | - |

### Formatos Soportados

- ✅ PDF (.pdf)
- ✅ Word (.docx)
- ❌ Excel (.xlsx) - Solo listado, no procesamiento
- ❌ Imágenes (.jpg, .png)

## 🤖 Prompts Especializados

### 1. Prompt de Auditoría (IXP)
- **Objetivo**: Extraer información de auditorías y revisiones
- **Documentos**: Solo IXP (Informes de Auditoría)
- **Salida**: `auditoria.json`

### 2. Prompt de Productos (ROP, INI, DEC, IFS)
- **Objetivo**: Extraer metas, productos y avances de proyecto
- **Campos clave**: Código CFA, descripción, meta, unidad, fechas
- **Salida**: `productos.json`

### 3. Prompt de Desembolsos (ROP, INI, DEC)
- **Objetivo**: Extraer información financiera y desembolsos
- **Campos clave**: Fechas, montos, fuentes, códigos de operación
- **Salida**: `desembolsos.json`

## 📊 Estructura de Salida JSON

### Metadata
```json
{
  "metadata": {
    "project_name": "CFA009660",
    "concatenated_at": "2025-09-04T21:44:39.728343",
    "total_files": 15,
    "processor_version": "1.0.0"
  }
}
```

### Resultados
```json
{
  "productos_results": [
    {
      "source_file": "documento_origen.json",
      "document_name": "nombre_documento",
      "data": {
        "Código CFA": "CFA009660|EXTRAIDO_DIRECTO",
        "descripción de producto": "Descripción|EXTRAIDO_DIRECTO",
        "meta del producto": "70.85|EXTRAIDO_DIRECTO",
        "concepto_final": "Favorable",
        "concepto_rationale": "Justificación del concepto"
      }
    }
  ]
}
```

## ⚙️ Configuración Avanzada

### Límites de Tokens

```python
# chunking_processor.py
MAX_TOKENS = 90000  # Límite por chunk
OVERLAP_TOKENS = 5000  # Overlap entre chunks
```

### Filtros de Documentos

```python
# openai_processor.py
PROMPT1_PREFIXES = ['IXP']  # Solo auditoría
PROMPT2_PREFIXES = ['ROP', 'INI', 'DEC', 'IFS']  # Productos
PROMPT3_PREFIXES = ['ROP', 'INI', 'DEC']  # Desembolsos
```

## 📊 Sistema de Logging Estructurado

### Azure Application Insights Integration

El sistema incluye logging estructurado con integración opcional a Azure Application Insights:

- **Logging JSON estructurado**: Todos los eventos se registran en formato JSON
- **Métricas personalizadas**: Seguimiento de operaciones y rendimiento
- **Trazabilidad completa**: Cada operación tiene un ID único
- **Niveles de log**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Configuración de Logging

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "json": {
      "format": "{\"timestamp\": \"%(asctime)s\", \"level\": \"%(levelname)s\", \"logger\": \"%(name)s\", \"message\": \"%(message)s\", \"module\": \"%(module)s\", \"function\": \"%(funcName)s\", \"line\": %(lineno)d}"
    }
  }
}
```

### Archivos de Log

- `logs/app.log` - Log principal estructurado
- `logs/error.log` - Solo errores y warnings
- Consola - Output formateado para desarrollo

## 🧪 Testing y Debugging

### Tests Disponibles

```bash
# Test completo del flujo
python tests/test_main_debug.py

# Test de componentes individuales
python -m pytest tests/test_document_processing.py
```

### Verificación de Salidas

```bash
# Verificar estructura de archivos generados
ls -la output_docs/CFA009660/

# Verificar contenido JSON
jq '.metadata' output_docs/CFA009660/productos.json

# Ver logs estructurados
tail -f logs/app.log | jq .
```

## 🔧 Solución de Problemas

### Errores Comunes

1. **Error de autenticación Azure**
   - Verificar variables de entorno en `.env`
   - Confirmar que los servicios estén habilitados

2. **Documentos no procesados**
   - Verificar formato de archivo (PDF/DOCX)
   - Confirmar prefijo del documento
   - Revisar logs para errores específicos

3. **Chunks muy grandes**
   - Ajustar `MAX_TOKENS` en `chunking_processor.py`
   - Verificar que el overlap no sea excesivo

4. **JSON malformado**
   - Revisar respuestas de OpenAI en logs
   - Verificar prompts y esquemas de validación

### Monitoreo

```bash
# Seguir logs estructurados en tiempo real
tail -f logs/app.log | jq .

# Verificar errores específicos
tail -f logs/error.log | jq .

# Filtrar por nivel de log
grep '"level": "ERROR"' logs/app.log | jq .

# Monitorear operaciones específicas
grep 'operation_id' logs/app.log | jq .
```

## 📈 Métricas y Rendimiento

### Estadísticas Típicas

- **Documentos procesados**: 7-15 por proyecto
- **Chunks generados**: 5-20 por proyecto
- **Prompts ejecutados**: 30-60 por proyecto
- **Tiempo de procesamiento**: 5-15 minutos por proyecto
- **Uso de tokens**: 50k-200k tokens por proyecto

### Métricas de Logging

- **Operaciones trazadas**: Cada operación tiene ID único
- **Tiempo de respuesta**: Medición automática de duración
- **Tasa de errores**: Seguimiento de fallos por componente
- **Uso de recursos**: Monitoreo de memoria y CPU

### Optimizaciones

1. **Chunking inteligente** reduce llamadas a API
2. **Filtros por prefijo** evitan procesamiento innecesario
3. **Procesamiento en paralelo** de prompts independientes
4. **Reutilización de extracciones** de Document Intelligence
5. **Logging asíncrono** minimiza impacto en rendimiento

## 🔒 Seguridad

- ✅ Variables de entorno para credenciales
- ✅ No logging de información sensible
- ✅ Validación de entrada de archivos
- ✅ Manejo seguro de errores
- ✅ Logging estructurado sin exposición de datos
- ✅ Sanitización automática de logs

## 🤝 Contribución

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📝 Changelog

### v1.1.0 (2025-09-05)
- ✅ **Sistema de logging estructurado** con formato JSON
- ✅ **Integración Azure Application Insights** (opcional)
- ✅ **Trazabilidad completa** con operation_id único
- ✅ **Métricas personalizadas** y monitoreo de rendimiento
- ✅ **Configuración de logging** centralizada
- ✅ **Manejo mejorado de errores** con contexto estructurado
- ✅ **Logging asíncrono** para mejor rendimiento

### v1.0.0 (2025-09-04)
- ✅ Implementación inicial del sistema completo
- ✅ Integración Azure Document Intelligence
- ✅ Integración Azure OpenAI con 3 prompts especializados
- ✅ Sistema de chunking inteligente
- ✅ Filtros por prefijo de documento
- ✅ Concatenación automática de resultados JSON
- ✅ Sistema de logging básico
- ✅ Tests y debugging tools

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 👥 Autores

- **Equipo de Desarrollo CAF** - Desarrollo inicial

## 🙏 Agradecimientos

- Microsoft Azure por los servicios de IA
- Comunidad de Python por las librerías utilizadas
- CAF por los requerimientos y casos de uso

---

**📞 Soporte**: Para soporte técnico, crear un issue en el repositorio o contactar al equipo de desarrollo.