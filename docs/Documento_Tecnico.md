# Documento Técnico — Sistema de Procesamiento de Documentos con IA

## 0. Resumen

- Solución serverless en Azure Functions para procesar documentos (PDF/DOCX) con Azure AI Document Intelligence, dividir contenido en chunks, y ejecutar análisis batch en Azure OpenAI con tres agentes (Auditoría, Productos, Desembolsos).
- Persistencia integral en Azure Blob Storage por proyecto. Orquestación de estado de batches con archivos en blob y, opcionalmente, con Cosmos DB (isBatchPending).
- Tres funciones principales:
  - OpenAiProcess (Service Bus trigger): Ingesta+DI+Chunking+Batch.
  - PoolingProcess (Timer trigger): Polling de batches, procesamiento de resultados y marcadores.
  - FinalCsvProcess (HTTP trigger): Generación de CSVs finales y notificación de éxito.

Nota clave: El análisis de IA contra OpenAI se realiza en modalidad batch (Batch API). Prepararmos un archivo JSONL con múltiples requests, lo subimos a OpenAI como input_file y creamos un job con ventana de finalización de 24h. PoolingProcess orquesta el seguimiento de estos batches y su consolidación al completarse.

---

## 1. OpenAiProcess (Service Bus trigger)

Propósito
- Orquestar el flujo completo por proyecto o por documento: Document Intelligence → chunking por documento → creación del batch en Azure OpenAI.

Entrada
- Mensaje de Service Bus (JSON):
  - Requeridos: `project_name`, `queue_type`
  - Opcionales: `document_name`, `document_type`, `operation_id`

Salida
- Archivos en Blob Storage:
  - `basedocuments/{project}/processed/DI/{documento}.json` (por doc)
  - `basedocuments/{project}/processed/chunks/{documento}_chunk_XXX.json` (si excede límite de tokens)
  - `basedocuments/{project}/processed/openai_logs/batch_info_{project}_{batch}.json`
  - `basedocuments/{project}/processed/openai_logs/batch_payload_{project}_{batch}.jsonl`

Flujo detallado
1) Validación de mensaje y parámetros.
2) Si viene `document_name`: procesa documento individual (DI → chunking → batch sobre sus chunks).
3) Si no, procesa proyecto completo:
   - Lista documentos raw (prefijos requeridos para DI: INI, IXP, DEC, ROP, IFS).
   - Ejecuta Document Intelligence por documento (markdown + metadatos), guarda en `processed/DI`.
   - Revisa documentos ya DI existentes y crea chunks solo si son necesarios; guarda en `processed/chunks/` y puede eliminar el JSON DI exitoso tras chunking.
   - Crea un batch único para el proyecto (con requests por documento/chunk y prompts aplicables), guarda `batch_info` y `batch_payload` en `openai_logs/`.
4) Manejo de errores críticos: notifica por API externa.

Prompts y filtrado por prefijos (para batch)
- Auditoría (prompt 1): `['IXP']`
- Productos (prompt 2): `['ROP', 'INI', 'DEC', 'IFS']`
- Desembolsos (prompt 3): `['ROP', 'INI', 'DEC', 'IFS']`
- Extracción de prefijo: parte anterior al primer guion o primeras 3 letras en mayúsculas.

Diagrama de flujo (OpenAiProcess)
```mermaid
flowchart TD
  A[Service Bus Message<br/>{project_name, queue_type}] --> B[Validación de entrada]
  B --> C[Listar raw y filtrar prefijos<br/>(INI/IXP/DEC/ROP/IFS)]
  C --> D[Document Intelligence<br/>(markdown + metadatos)]
  D --> E{¿excede tokens?}
  E -- Sí --> F[Chunking por documento<br/>con solapamiento]
  E -- No --> G[Usar contenido sin chunking]
  F --> H[Construir JSONL
           (requests por doc/chunk y prompt)]
  G --> H
  H --> I[Subir input_file y crear Batch<br/>en Azure OpenAI]
  I --> J[Guardar batch_info y payload
           en openai_logs/]
  J --> K[Marcar isBatchPending (Cosmos, opcional)]
```

Detalles del algoritmo
- Evita re-procesado: si existe DI válido o si ya existen chunks `{doc}_chunk_000.json`, el documento se salta.
- Chunking: división por secciones/párrafos/oraciones, con solapamiento configurable (`overlap_tokens`).
- Selección de prompts: basada en prefijo del nombre del documento (IXP/ROP/INI/DEC/IFS).
- Límite de tokens: parámetros configurables por `ChunkingProcessor` (p. ej., 100k tokens por chunk).
- Persistencia: todos los artefactos intermedios se guardan en `processed/` para trazabilidad y reproceso si fuese necesario.

Variables de entorno (mínimas)
- Document Intelligence: `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY`
- Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- Blob Storage: `AZURE_STORAGE_CONNECTION_STRING`
- Notificaciones: `NOTIFICATIONS_API_URL_BASE`, `SHAREPOINT_FOLDER`
- (Opcional) Cosmos: `COSMOS_DB_CONNECTION_STRING`, `COSMOS_DB_DATABASENAME`, `COSMOS_CONTAINER_FOLDER`

Shared/Utils usados por OpenAiProcess
- Procesadores:
  - DocumentIntelligenceProcessor: Azure DI, genera markdown y metadatos por documento; evita reprocesar si ya existe DI válido o chunks previos.
  - ChunkingProcessor: tokeniza (tiktoken), divide por secciones/párrafos/oraciones, crea solapamiento y guarda chunks a Blob.
  - OpenAIBatchProcessor: arma JSONL para Batch API, aplica prompts por prefijo, crea batch y guarda logs/manifest.
- Utilidades:
  - BlobStorageClient: listado, descarga, subida, borrado; rutas canónicas y normalizaciones Unicode.
  - AppInsightsLogger: logging estructurado (consola en Functions).
  - NotificationsService + build_email_payload: envío de notificaciones (error crítico).
  - (Opcional) CosmosDBClient: marca `isBatchPending` para `project` si está configurado.

Rutas en Blob Storage
- Raw: `basedocuments/{project}/raw/`
- DI: `basedocuments/{project}/processed/DI/`
- Chunks: `basedocuments/{project}/processed/chunks/`
- OpenAI logs: `basedocuments/{project}/processed/openai_logs/`

Manejo de errores/notificaciones (OpenAiProcess)
- Errores críticos (falla al crear batch, problemas de autenticación/conexión/llaves): envía `ERROR_FINALLY_PROCESS`.
- Errores no críticos: solo log.

Archivos relevantes
- Función: `azure_functions/OpenAiProcess/__init__.py`
- Procesadores: `azure_functions/shared_code/processors/{document_intelligence_processor.py, chunking_processor.py, openai_batch_processor.py}`
- Utils: `azure_functions/shared_code/utils/{blob_storage_client.py, app_insights_logger.py, notifications_service.py, build_email_payload.py, cosmo_db_client.py}`

---

## 2. PoolingProcess (Timer trigger)

Propósito
- Verificar periódicamente el estado de batches en Azure OpenAI, procesar resultados completados, y crear marcadores de batch procesado. Manejar notificaciones para estados críticos (failed/expired).

Entrada
- Sin entrada externa; se ejecuta por tiempo. Fuente de verdad:
  - Cosmos DB (opcional): consulta de carpetas con `isBatchPending=true`.
  - Archivos en `processed/openai_logs/` del Blob para detectar batches “huérfanos” (completados sin marcador).

Salida
- Resultados finales por proyecto en `basedocuments/{project}/results/` (p.ej., `auditoria.json`, `productos.json`, `desembolsos.json`).
- Marcador por batch: `basedocuments/{project}/results/batches/{batch_id}/processed.json`.
- Notificaciones de error para `failed/expired`.

Flujo detallado
1) Determina proyectos a revisar:
   - Si hay Cosmos configurado: `PoolingEventTimerProcessor` lista `folderName` con `isBatchPending=true`.
   - Busca también “batches huérfanos” leyendo `openai_logs/` y verificando estado en OpenAI.
2) Para cada batch (pending/completed/failed/expired):
   - `completed`: descarga NDJSON, parsea línea por línea, normaliza por prompt y organiza por documento; guarda JSON finales y marca batch procesado.
   - `validating/in_progress/finalizing`: registra y continua.
   - `failed/expired`: envía `ERROR_FINALLY_PROCESS` con contexto.
3) Log de cierre con conteos de procesados/completados.

Diagrama de flujo (PoolingProcess)
```mermaid
flowchart TD
  A[Timer Trigger] --> B[Obtener carpetas pendientes<br/>(Cosmos isBatchPending)]
  B --> C[Descubrir batches huérfanos<br/>en openai_logs/]
  C --> D[Unificar lista de batches a revisar]
  D --> E[Consultar estado en Azure OpenAI]
  E -->|completed| F[Descargar resultados NDJSON]
  F --> G[Parsear líneas, normalizar por prompt]
  G --> H[Guardar resultados finales en results/]
  H --> I[Crear marcador results/batches/{id}/processed.json]
  E -->|failed/expired| J[Notificar ERROR_FINALLY_PROCESS]
  E -->|validating/in_progress/finalizing| K[Registrar y continuar]
```

Variables de entorno (mínimas)
- Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`
- Blob Storage: `AZURE_STORAGE_CONNECTION_STRING`
- Cosmos (opcional): `COSMOS_DB_CONNECTION_STRING`, `COSMOS_DB_DATABASENAME`, `COSMOS_CONTAINER_FOLDER`
- Notificaciones: `NOTIFICATIONS_API_URL_BASE`, `SHAREPOINT_FOLDER`

Shared/Utils usados por PoolingProcess
- `BatchResultsProcessor` (definido en el mismo módulo de la Function):
  - Cliente de AzureOpenAI.
  - `BlobStorageClient` para listar/descargar blobs.
  - Parsing de NDJSON: extrae `custom_id`, mapea a `prompt_type` y `document_name`, tolera múltiples objetos JSON o bloques, y produce estructuras por documento/prompt.
  - Guardado de resultados finales y marcador por `batch_id`.
  - (Opcional) invoca `final_output_process.invoke_download_final_output(folder)` para disparar HTTP de CSVs (si se usa este camino).
- Utilidades:
  - `PoolingEventTimerProcessor` + `CosmosDBClient` para carpetas pendientes.
  - `NotificationsService` + `build_email_payload` para notificaciones de error.
  - `AppInsightsLogger` para logging estructurado.

Rutas en Blob Storage
- Logs de batch: `basedocuments/{project}/processed/openai_logs/`
- Resultados finales: `basedocuments/{project}/results/`
- Marcador: `basedocuments/{project}/results/batches/{batch_id}/processed.json`

Manejo de errores/notificaciones (PoolingProcess)
- `failed/expired`: envía `ERROR_FINALLY_PROCESS` con `project_name` y `batch_id`.
- Fallos de parsing/descarga por línea: contabiliza y prosigue; se preserva fallback si no se puede materializar contenido estructurado.

Archivos relevantes
- Función y procesador: `azure_functions/PoolingProcess/__init__.py`
- Utils: `azure_functions/shared_code/utils/{blob_storage_client.py, app_insights_logger.py, pooling_event_timer_processor.py, notifications_service.py, build_email_payload.py, final_output_process.py, cosmo_db_client.py}`

---

## 3. FinalCsvProcess (HTTP trigger)

Propósito
- Convertir los JSON finales de un proyecto en tres CSVs (`auditoria_cartera.csv`, `producto_cartera.csv`, `desembolso_cartera.csv`) y enviar notificación de éxito al completar.

Entrada (HTTP)
- Query param: `folderName=<CFA...>`

Salida (Blob)
- `outputdocuments/auditoria_cartera.csv`
- `outputdocuments/producto_cartera.csv`
- `outputdocuments/desembolso_cartera.csv`

Flujo detallado
1) Lee variables de entorno de salida (storage/contenerdor) y de notificaciones.
2) Para cada archivo esperado de entrada en `basedocuments/{folder}/results/{auditoria|productos|desembolsos}.json`:
   - Llama `process_ndjson_or_json_to_csv(...)` que detecta NDJSON vs JSON estándar, aplica filtros mínimos por dataset y normaliza `CFA`.
   - Append-safe: si existe CSV, concatena filas nuevas y sobrescribe el blob.
3) Construye payload de notificación de éxito y lo envía.

Diagrama de flujo (FinalCsvProcess)
```mermaid
flowchart TD
  A[HTTP GET folderName] --> B[Resolver paths de entrada resultados/]
  B --> C[Procesar NDJSON/JSON a DataFrame]
  C --> D[Filtrado y normalización (CFA)]
  D --> E[Concatenar con CSV existente si aplica]
  E --> F[Subir CSV a outputdocuments/]
  F --> G[Enviar notificación SUCCESS_FINALLY_PROCESS]
```

Variables de entorno (mínimas)
- `AZURE_STORAGE_OUTPUT_CONNECTION_STRING`, `CONTAINER_OUTPUT_NAME`
- `NOTIFICATIONS_API_URL_BASE`, `SHAREPOINT_FOLDER`

Shared/Utils usados por FinalCsvProcess
- `processor_csv.process_ndjson_or_json_to_csv`: lógica de conversión/filtrado y escritura de CSV en Blob.
- `NotificationsService` + `build_email_payload`: notificación `SUCCESS_FINALLY_PROCESS`.

Rutas en Blob Storage
- Entradas: `basedocuments/{folder}/results/{auditoria|productos|desembolsos}.json`
- Salidas: `outputdocuments/{auditoria_cartera|producto_cartera|desembolso_cartera}.csv`

Archivos relevantes
- Función: `azure_functions/FinalCsvProcess/__init__.py`
- Utilidad CSV: `azure_functions/shared_code/utils/processor_csv.py`
- Notificaciones: `azure_functions/shared_code/utils/{notifications_service.py, build_email_payload.py}`

---

## 4. Componentes comunes (Shared)

BlobStorageClient
- Contenedor por defecto: `caf-documents` (configurable por connection string).
- Helper de rutas: `basedocuments/{project}/raw|processed|results`.
- Listar/descargar/subir/borrar blobs; normalizaciones Unicode para nombres de archivo; utilidades de prefijos/descarga de bytes y JSON.

AppInsightsLogger
- Logging estructurado (JSON) a consola; helpers: `log_operation_start`, `log_operation_end`, `log_document_processing`, `log_batch_operation`, `log_error`, `log_metric`.

DocumentIntelligenceProcessor
- Usa `azure.ai.documentintelligence` (modelo `prebuilt-layout`) y produce contenido en markdown + metadatos por documento; evita reprocesos si ya existe DI válido o chunks del documento.
- Filtra documentos a procesar por prefijos: INI, IXP, DEC, ROP, IFS.

ChunkingProcessor
- Cuenta tokens con `tiktoken`, divide por secciones/párrafos/oraciones, crea solapamiento, y guarda chunks como JSON por documento (`{doc}_chunk_XXX.json`).

OpenAIBatchProcessor
- Carga prompts (Auditoría, Productos, Desembolsos), decide prompts por prefijo, crea JSONL de requests y batch en Azure OpenAI, guarda `batch_info` y `batch_payload` en `openai_logs/`. Best-effort: marca `isBatchPending` en Cosmos si está configurado.

Formato de request (JSONL, Batch API)
- Por cada documento/chunk y prompt aplicable, se construye una línea JSON con:
  - `custom_id`: identifica `project/document/prompt[_chunk_XXX]`.
  - `method`: POST.
  - `url`: `/chat/completions`.
  - `body`: `{ model, messages:[{role:system},{role:user(prompt+contexto)}], max_completion_tokens, temperature }`.
- El archivo `.jsonl` se sube con `files.create(purpose="batch")` y se crea un batch con `batches.create(...)` (`completion_window="24h"`).
- Estados típicos: `validating` → `in_progress` → `finalizing` → `completed` (o `failed/expired`).
- Persistencia: `batch_info_{project}_{batch}.json` y `batch_payload_{project}_{batch}.jsonl` en `processed/openai_logs/`.

PoolingEventTimerProcessor + CosmosDBClient
- Consulta `isBatchPending=true` en la colección indicada para decidir qué proyectos revisar en el ciclo del timer.

NotificationsService + build_email_payload
- Envío de POST a `{NOTIFICATIONS_API_URL_BASE}/email-notification` con payload basado en tipo (`ERROR_FINALLY_PROCESS` o `SUCCESS_FINALLY_PROCESS`) y `folderName`.

---

## 5. Configuración y dependencias

Variables de entorno (resumen)
- Document Intelligence: `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY`
- Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- Blob Storage (documentos): `AZURE_STORAGE_CONNECTION_STRING`
- Blob Storage (CSV, FinalCsvProcess): `AZURE_STORAGE_OUTPUT_CONNECTION_STRING`, `CONTAINER_OUTPUT_NAME`
- Cosmos DB (opcional): `COSMOS_DB_CONNECTION_STRING`, `COSMOS_DB_DATABASENAME`, `COSMOS_CONTAINER_FOLDER`
- Notificaciones: `NOTIFICATIONS_API_URL_BASE`, `SHAREPOINT_FOLDER`
- Functions runtime: `FUNCTIONS_WORKER_RUNTIME=python`, `FUNCTIONS_EXTENSION_VERSION=~4`

Dependencias (Functions)
- `azure-functions`, `azure-ai-documentintelligence`, `azure-storage-blob`, `azure-cosmos`, `openai`, `tiktoken`, `pandas`, `requests`

---

## 6. Pruebas y operación

Pruebas (scripts en `azure_functions/tests/`)
- Service Bus / Diagnóstico: `check_queue_size.py`, `get_queue_info.py`, `peek_queue_messages.py`, `purge_queue.py`.
- Mensajería: `send_test_message_simple.py`, `send_test_messages_for_projects.py`.
- Listado de resultados y CSVs: `list_projects_with_json.py`, `send_csv_generation.py`.

Despliegue y ejecución
- Despliegue: `cd azure_functions && ./redeploy_complete_functions.sh` (o CLI zip deploy).
- Procesamiento: enviar mensaje a Service Bus: `{ "project_name": "CFA009660", "queue_type": "processing" }`.
- Generación CSVs: invocar HTTP `FinalCsvProcess` con `folderName` (o usar `send_csv_generation.py`).

Runbook operativo (alta nivel)
- Previa
  - Verificar App Settings: claves DI/OpenAI/Storage (y Cosmos/notificaciones si aplica).
  - Validar estructura en Blob: `basedocuments/{proyecto}/raw/` poblado y permisos.
- Ejecución
  - Enviar mensaje a Service Bus (OpenAiProcess).
  - Confirmar `openai_logs/batch_info_*.json` creado y `isBatchPending` (si Cosmos).
  - Dejar que el timer ejecute PoolingProcess y espere estado `completed`.
  - Verificar `results/` y el marcador por `batch_id`.
  - Invocar `FinalCsvProcess` para generar CSVs (o dejar que un orquestador externo lo haga).
- Post
  - Validar CSVs en `outputdocuments/`.
  - Auditar logs y métricas clave.

---

## 7. Consideraciones y mejoras

Limitaciones
- OpenAI Batch: ventana de 24h, límites de requests y rate limits.
- DI: límites de tamaño y latencia variable.
- Azure Functions: timeouts/cold starts.

Posibles mejoras
- Paralelización de DI y chunking; particionamiento de batches grandes.
- Métricas/alertas adicionales (Application Insights); dashboard.
- Retries robustos y manejo de documentos corruptos; DLQ para mensajes fallidos.
- Throttling inteligente y control de uso de tokens.

---

## 8. Solución de problemas (Troubleshooting)

Síntomas y causas comunes
- Error al crear batch (`Failed to create batch job`): revisar `AZURE_OPENAI_API_KEY`, endpoint y `AZURE_OPENAI_API_VERSION`; confirmar permisos del deployment (`AZURE_OPENAI_DEPLOYMENT_NAME`).
- Batch `failed/expired`: exceso de tamaño del JSONL, límites de cuota o errores en requests; revisar `batch_payload_*.jsonl` y logs de OpenAI.
- Documentos no procesados en DI: verificar prefijos (INI/IXP/DEC/ROP/IFS) y existencia real en `raw/`; revisar normalización Unicode del nombre.
- Chunks no generados: documento dentro de límite de tokens o ya existe `{doc}_chunk_000.json`.
- Resultados vacíos: revisar mapeo de `custom_id` y `prompt_type` en el parser; verificar que los prompts aplican al prefijo del documento.
- CSVs sin filas: filtros de `processor_csv` descartaron registros (p. ej., falta `descripcion_producto.value`).

Pasos de diagnóstico
1) Confirmar Service Bus message recibido en OpenAiProcess (logs).
2) Verificar `processed/DI/` y `processed/chunks/` según corresponda.
3) Revisar `processed/openai_logs/batch_info_*.json` y `batch_payload_*.jsonl`.
4) Comprobar en `PoolingProcess` el estado actual del batch y si existe marcador en `results/batches/{id}/processed.json`.
5) Abrir `results/{auditoria|productos|desembolsos}.json` y verificar contenido.
6) Disparar `FinalCsvProcess` y validar CSVs generados.
