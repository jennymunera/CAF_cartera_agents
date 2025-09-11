# Azure Function - Procesamiento de Documentos con Service Bus

Esta Azure Function procesa documentos automáticamente cuando recibe mensajes de Service Bus, utilizando Azure Document Intelligence, chunking y Azure OpenAI para análisis de documentos.

## 🏗️ Arquitectura

```
Service Bus Queue → Azure Function → Blob Storage
                        ↓
                 Document Intelligence
                        ↓
                    Chunking
                        ↓
                   Azure OpenAI
                        ↓
                 Resultados en Blob
```

## 📋 Requisitos

- **Python**: 3.11
- **Azure CLI**: Instalado y autenticado
- **Recursos Azure**:
  - Resource Group
  - Storage Account
  - Service Bus Namespace con cola
  - Azure Document Intelligence
  - Azure OpenAI
  - Application Insights

## 🚀 Deployment

### 1. Configuración Inicial

1. Clona o copia los archivos de la función
2. Asegúrate de tener un archivo `.env` en el directorio padre con:

```env
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_key
AZURE_OPENAI_API_KEY=your_openai_key
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
```

### 2. Ejecutar Deployment

```powershell
# Navegar al directorio de la función
cd azure_function

# Ejecutar script de deployment
.\deploy.ps1 -SubscriptionId "your-subscription-id"
```

### 3. Parámetros del Script (Opcionales)

```powershell
.\deploy.ps1 `
    -SubscriptionId "6e30581f-5e6d-4f9f-8339-420301cce5f4" `
    -ResourceGroup "RG-POC-CARTERA-CR" `
    -FunctionAppName "azfunc-analisis-MVP-CARTERA-CR" `
    -StorageAccount "asmvpcarteracr" `
    -ServiceBusNamespace "sb-messaging-mvp-cartera-cr" `
    -QueueName "analysis-event-queue" `
    -Location "East US" `
    -AppInsightsName "ai-analisis-MVP-CARTERA-CR"
```

## 📁 Estructura del Proyecto

```
azure_function/
├── OpenAiProcess_local/          # Función principal
│   ├── __init__.py              # Código de la función
│   └── function.json            # Configuración del trigger
├── shared/                      # Código compartido
│   ├── document_intelligence_processor.py
│   ├── chunking_processor.py
│   ├── openai_processor.py
│   ├── utils/                   # Utilidades
│   ├── schemas/                 # Esquemas de datos
│   ├── prompt Auditoria.txt     # Prompts OpenAI
│   ├── prompt Desembolsos.txt
│   └── prompt Productos.txt
├── requirements.txt             # Dependencias Python
├── host.json                   # Configuración del host
├── local.settings.json         # Configuración local
├── deploy.ps1                  # Script de deployment
├── SERVICE_BUS_MESSAGE_STRUCTURE.md  # Documentación de mensajes
└── README.md                   # Esta documentación
```

## 📨 Uso

### Estructura del Mensaje Service Bus

Ver [SERVICE_BUS_MESSAGE_STRUCTURE.md](./SERVICE_BUS_MESSAGE_STRUCTURE.md) para detalles completos.

**Mensaje básico:**
```json
{
  "projectName": "mi_proyecto",
  "requestId": "req_001"
}
```

### Estructura Requerida en Blob Storage

```
input-documents/
├── {projectName}/
│   ├── auditoria/
│   │   └── *.pdf
│   ├── productos/
│   │   └── *.pdf
│   └── desembolsos/
│       └── *.pdf
```

### Resultados

Los resultados se guardan en:
```
output-results/
├── {projectName}/
│   ├── {requestId}_auditoria_results.json
│   ├── {requestId}_productos_results.json
│   ├── {requestId}_desembolsos_results.json
│   └── {requestId}_processing_log.json
```

## 🧪 Testing

### 1. Test Local

```bash
# Instalar Azure Functions Core Tools
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Navegar al directorio
cd azure_function

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar localmente
func start
```

### 2. Test con Service Bus

#### Usando Azure CLI:
```bash
az servicebus message send \
  --resource-group "RG-POC-CARTERA-CR" \
  --namespace-name "sb-messaging-mvp-cartera-cr" \
  --queue-name "analysis-event-queue" \
  --body '{"projectName": "test_project", "requestId": "test_001"}'
```

#### Usando Python:
```python
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import json

connection_str = "your_connection_string"
queue_name = "analysis-event-queue"

message = {
    "projectName": "test_project",
    "requestId": "test_001"
}

with ServiceBusClient.from_connection_string(connection_str) as client:
    with client.get_queue_sender(queue_name) as sender:
        sender.send_messages(ServiceBusMessage(json.dumps(message)))
```

### 3. Preparar Datos de Test

1. Crear estructura en Blob Storage:
```
input-documents/test_project/auditoria/test_document.pdf
input-documents/test_project/productos/test_document.pdf
input-documents/test_project/desembolsos/test_document.pdf
```

2. Enviar mensaje de test
3. Verificar resultados en `output-results/test_project/`

## 📊 Monitoreo

### Application Insights
- **Logs**: Buscar por `requestId` para seguimiento completo
- **Métricas**: Duración de ejecución, errores, throughput
- **Alertas**: Configurar para errores y timeouts

### Queries Útiles (KQL)

```kusto
// Buscar por requestId específico
traces
| where message contains "req_001"
| order by timestamp desc

// Errores en las últimas 24 horas
exceptions
| where timestamp > ago(24h)
| summarize count() by type, bin(timestamp, 1h)

// Duración promedio de procesamiento
requests
| where name == "OpenAiProcess_local"
| summarize avg(duration) by bin(timestamp, 1h)
```

## 🔧 Configuración

### Variables de Entorno

La función requiere estas variables (configuradas automáticamente por el script):

- `ServiceBusConnectionString`: Connection string del Service Bus
- `AZURE_STORAGE_ACCOUNT`: Nombre de la Storage Account
- `AZURE_STORAGE_KEY`: Key de la Storage Account
- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`: Endpoint de Document Intelligence
- `AZURE_DOCUMENT_INTELLIGENCE_KEY`: Key de Document Intelligence
- `AZURE_OPENAI_API_KEY`: Key de Azure OpenAI
- `AZURE_OPENAI_ENDPOINT`: Endpoint de Azure OpenAI
- `AZURE_OPENAI_API_VERSION`: Versión de la API
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Nombre del deployment
- `APPINSIGHTS_INSTRUMENTATIONKEY`: Key de Application Insights

### Timeouts y Límites

- **Function Timeout**: 10 minutos (configurable en host.json)
- **Service Bus Lock Duration**: 5 minutos
- **Max Retry Count**: 3 intentos
- **Batch Size**: 1 mensaje por vez

## 🚨 Troubleshooting

### Errores Comunes

1. **"Project folder not found"**
   - Verificar que existe la carpeta en Blob Storage
   - Verificar permisos de Storage Account

2. **"Document Intelligence failed"**
   - Verificar endpoint y key
   - Verificar formato de documentos (PDF soportado)

3. **"OpenAI processing failed"**
   - Verificar deployment name y endpoint
   - Verificar cuotas y límites de rate

4. **"Function timeout"**
   - Documentos muy grandes
   - Aumentar timeout en host.json
   - Considerar procesamiento en lotes

### Logs Importantes

```bash
# Ver logs en tiempo real
az functionapp log tail --name azfunc-analisis-MVP-CARTERA-CR --resource-group RG-POC-CARTERA-CR

# Ver logs específicos
az monitor activity-log list --resource-group RG-POC-CARTERA-CR
```

## 📈 Optimización

### Performance
- Usar paralelización para múltiples documentos
- Implementar caching para resultados similares
- Optimizar tamaño de chunks

### Costos
- Monitorear uso de Document Intelligence
- Optimizar prompts de OpenAI
- Usar tiers apropiados de Storage

## 🔄 Actualizaciones

Para actualizar la función:

1. Modificar código
2. Ejecutar nuevamente `deploy.ps1`
3. Verificar deployment en Azure Portal

## 📞 Soporte

Para soporte técnico:
- Revisar logs en Application Insights
- Verificar configuración en Azure Portal
- Consultar documentación de Azure Functions