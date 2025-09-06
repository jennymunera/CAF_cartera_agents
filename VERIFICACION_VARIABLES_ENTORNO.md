# Verificación de Variables de Entorno - Azure Functions

## Estado Actual de Configuración

### Variables Requeridas según .env.example

#### ✅ Variables Configuradas Correctamente
- `AZURE_OPENAI_ENDPOINT`: https://OpenAI-Tech2.openai.azure.com/
- `AZURE_OPENAI_API_VERSION`: 2025-04-01-preview
- `AZURE_OPENAI_DEPLOYMENT_NAME`: o4-mini-dadmi-batch
- `AZURE_STORAGE_CONTAINER_NAME`: caf-documents
- `ServiceBusQueueName`: recoaudit-queue
- `LOG_LEVEL`: INFO
- `LOG_TO_FILE`: true
- `LOG_FILE_PATH`: logs/application.log
- `LOG_TO_CONSOLE`: true
- `LOG_FORMAT`: json

#### ❌ Variables FALTANTES (Valores Vacíos)

**CRÍTICAS para el funcionamiento:**
1. `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` - **REQUERIDA**
2. `AZURE_DOCUMENT_INTELLIGENCE_KEY` - **REQUERIDA**
3. `AZURE_OPENAI_API_KEY` - **REQUERIDA**
4. `AZURE_STORAGE_CONNECTION_STRING` - **REQUERIDA**
5. `ServiceBusConnection` - **REQUERIDA**

**OPCIONALES para monitoreo:**
6. `APPLICATIONINSIGHTS_CONNECTION_STRING` - Recomendada
7. `AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY` - Recomendada

#### ➕ Variables Adicionales en Azure Functions
- `AZURE_STORAGE_OUTPUT_CONNECTION_STRING` - Vacía
- `COSMOS_DB_CONNECTION_STRING` - Vacía

## Acciones Requeridas

### 🚨 URGENTE - Variables Críticas
Estas variables DEBEN configurarse antes de ejecutar las pruebas:

```bash
# Configurar en Azure Functions App Settings
az functionapp config appsettings set \
  --name azfunc-analisis-MVP-CARTERA-CR \
  --resource-group rg-analisis-MVP-CARTERA-CR \
  --settings \
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="<endpoint>" \
    AZURE_DOCUMENT_INTELLIGENCE_KEY="<key>" \
    AZURE_OPENAI_API_KEY="<key>" \
    AZURE_STORAGE_CONNECTION_STRING="<connection_string>" \
    ServiceBusConnection="<service_bus_connection>"
```

### 📊 Recomendadas - Variables de Monitoreo
```bash
az functionapp config appsettings set \
  --name azfunc-analisis-MVP-CARTERA-CR \
  --resource-group rg-analisis-MVP-CARTERA-CR \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING="<connection_string>" \
    AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY="<key>"
```

## Impacto en las Pruebas

### ❌ SIN estas variables, las funciones FALLARÁN:
- **OpenAiProcess**: No podrá procesar documentos (Document Intelligence + OpenAI)
- **PoolingProcess**: No podrá acceder a Service Bus ni Storage

### ✅ CON estas variables configuradas:
- Procesamiento completo de documentos
- Integración con Service Bus
- Almacenamiento en Blob Storage
- Monitoreo con Application Insights

## Verificación Post-Configuración

Después de configurar las variables, verificar con:
```bash
# Verificar configuración (requiere permisos)
az functionapp config appsettings list --name azfunc-analisis-MVP-CARTERA-CR --resource-group rg-analisis-MVP-CARTERA-CR

# Verificar logs de la función
az functionapp log tail --name azfunc-analisis-MVP-CARTERA-CR --resource-group rg-analisis-MVP-CARTERA-CR
```

---
**CONCLUSIÓN**: Se requiere configurar 5 variables críticas antes de proceder con las pruebas de OpenAiProcess.