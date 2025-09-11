# Estructura del Mensaje Service Bus

## Formato del Mensaje

La Azure Function espera recibir mensajes en la cola `analysis-event-queue` con el siguiente formato JSON:

### Estructura Básica

```json
{
  "projectName": "string",
  "requestId": "string",
  "timestamp": "string (ISO 8601)",
  "metadata": {
    "source": "string",
    "priority": "string",
    "retryCount": "number"
  }
}
```

### Campos Obligatorios

- **projectName** (string): Nombre del proyecto que se va a procesar. Este nombre debe corresponder a una carpeta en el Blob Storage.
- **requestId** (string): Identificador único de la solicitud para tracking y logging.

### Campos Opcionales

- **timestamp** (string): Timestamp en formato ISO 8601 de cuando se generó el mensaje.
- **metadata** (object): Información adicional del mensaje.
  - **source** (string): Origen del mensaje (ej: "web-app", "api", "scheduler").
  - **priority** (string): Prioridad del procesamiento ("high", "medium", "low").
  - **retryCount** (number): Número de reintentos (usado internamente).

### Ejemplos de Mensajes

#### Mensaje Básico
```json
{
  "projectName": "proyecto_auditoria_2024",
  "requestId": "req_20240115_001"
}
```

#### Mensaje Completo
```json
{
  "projectName": "analisis_productos_Q1",
  "requestId": "req_20240115_002",
  "timestamp": "2024-01-15T10:30:00Z",
  "metadata": {
    "source": "web-app",
    "priority": "high",
    "retryCount": 0
  }
}
```

## Estructura Esperada en Blob Storage

Para que el procesamiento sea exitoso, el Blob Storage debe tener la siguiente estructura:

```
container: input-documents/
├── {projectName}/
│   ├── auditoria/
│   │   ├── documento1.pdf
│   │   ├── documento2.pdf
│   │   └── ...
│   ├── productos/
│   │   ├── documento1.pdf
│   │   ├── documento2.pdf
│   │   └── ...
│   └── desembolsos/
│       ├── documento1.pdf
│       ├── documento2.pdf
│       └── ...
```

## Respuesta del Procesamiento

Los resultados se guardarán en:

```
container: output-results/
├── {projectName}/
│   ├── {requestId}_auditoria_results.json
│   ├── {requestId}_productos_results.json
│   ├── {requestId}_desembolsos_results.json
│   └── {requestId}_processing_log.json
```

## Manejo de Errores

En caso de error, se generará un mensaje de error en:

```
container: error-logs/
├── {projectName}/
│   └── {requestId}_error.json
```

Con el formato:
```json
{
  "requestId": "req_20240115_001",
  "projectName": "proyecto_auditoria_2024",
  "error": "Descripción del error",
  "timestamp": "2024-01-15T10:35:00Z",
  "stackTrace": "...",
  "processingStage": "document_intelligence | chunking | openai_processing"
}
```

## Validación del Mensaje

La función validará:
1. Que `projectName` y `requestId` estén presentes
2. Que `projectName` contenga solo caracteres alfanuméricos, guiones y guiones bajos
3. Que `requestId` sea único (se puede usar para evitar procesamiento duplicado)
4. Que exista la estructura de carpetas esperada en Blob Storage

## Ejemplo de Envío con Azure CLI

```bash
# Enviar mensaje a la cola
az servicebus message send \
  --resource-group "RG-POC-CARTERA-CR" \
  --namespace-name "sb-messaging-mvp-cartera-cr" \
  --queue-name "analysis-event-queue" \
  --body '{"projectName": "test_project", "requestId": "test_001"}'
```

## Ejemplo de Envío con Python

```python
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import json

connection_str = "your_service_bus_connection_string"
queue_name = "analysis-event-queue"

message_body = {
    "projectName": "proyecto_test",
    "requestId": "req_20240115_003",
    "timestamp": "2024-01-15T10:30:00Z",
    "metadata": {
        "source": "python-script",
        "priority": "medium"
    }
}

with ServiceBusClient.from_connection_string(connection_str) as client:
    with client.get_queue_sender(queue_name) as sender:
        message = ServiceBusMessage(json.dumps(message_body))
        sender.send_messages(message)
        print(f"Mensaje enviado: {message_body['requestId']}")
```