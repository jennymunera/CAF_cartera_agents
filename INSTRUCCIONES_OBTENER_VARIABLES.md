# Instrucciones para Obtener Variables de Entorno

## Variables Críticas Requeridas

### 1. AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
**Cómo obtenerla:**
```bash
# Listar recursos de Document Intelligence
az cognitiveservices account list --query "[?kind=='FormRecognizer'].{name:name, endpoint:properties.endpoint, resourceGroup:resourceGroup}" --output table

# O buscar por nombre específico
az cognitiveservices account show --name "your-doc-intelligence-name" --resource-group "your-rg" --query "properties.endpoint" --output tsv
```
**Formato esperado:** `https://your-doc-intelligence.cognitiveservices.azure.com/`

### 2. AZURE_DOCUMENT_INTELLIGENCE_KEY
**Cómo obtenerla:**
```bash
# Obtener las claves
az cognitiveservices account keys list --name "your-doc-intelligence-name" --resource-group "your-rg" --query "key1" --output tsv
```
**Formato esperado:** String de 32 caracteres alfanuméricos

### 3. AZURE_OPENAI_API_KEY
**Cómo obtenerla:**
```bash
# Listar recursos de OpenAI
az cognitiveservices account list --query "[?kind=='OpenAI'].{name:name, endpoint:properties.endpoint, resourceGroup:resourceGroup}" --output table

# Obtener la clave
az cognitiveservices account keys list --name "OpenAI-Tech2" --resource-group "your-rg" --query "key1" --output tsv
```
**Formato esperado:** String de 32 caracteres alfanuméricos

### 4. AZURE_STORAGE_CONNECTION_STRING
**Cómo obtenerla:**
```bash
# Obtener connection string del storage account
az storage account show-connection-string --name "asmvpcarteracr" --resource-group "your-rg" --query "connectionString" --output tsv
```
**Formato esperado:** `DefaultEndpointsProtocol=https;AccountName=asmvpcarteracr;AccountKey=...;EndpointSuffix=core.windows.net`

### 5. ServiceBusConnection
**Cómo obtenerla:**
```bash
# Listar Service Bus namespaces
az servicebus namespace list --query "[].{name:name, resourceGroup:resourceGroup}" --output table

# Obtener connection string
az servicebus namespace authorization-rule keys list --resource-group "your-rg" --namespace-name "your-servicebus-namespace" --name "RootManageSharedAccessKey" --query "primaryConnectionString" --output tsv
```
**Formato esperado:** `Endpoint=sb://your-servicebus.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=...`

## Variables Opcionales (Application Insights)

### 6. APPLICATIONINSIGHTS_CONNECTION_STRING
**Cómo obtenerla:**
```bash
# Listar recursos de Application Insights
az monitor app-insights component show --app "your-app-insights-name" --resource-group "your-rg" --query "connectionString" --output tsv
```

### 7. AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY
**Cómo obtenerla:**
```bash
# Obtener instrumentation key
az monitor app-insights component show --app "your-app-insights-name" --resource-group "your-rg" --query "instrumentationKey" --output tsv
```

## Pasos para Configurar

### Paso 1: Obtener Valores Reales
1. Ejecutar los comandos anteriores para obtener cada valor
2. Copiar los valores obtenidos

### Paso 2: Editar Script de Configuración
1. Abrir `configure_azure_variables.sh`
2. Reemplazar los valores de ejemplo con los valores reales:
   ```bash
   # Cambiar esto:
   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://your-doc-intelligence.cognitiveservices.azure.com/"
   
   # Por el valor real:
   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://real-endpoint.cognitiveservices.azure.com/"
   
   # Para Application Insights, reemplazar:
   APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=abc123...;IngestionEndpoint=https://westus2-1.in.applicationinsights.azure.com/"
   ```

### Paso 3: Ejecutar Script
```bash
# Ejecutar el script de configuración
./configure_azure_variables.sh
```

### Paso 4: Verificar Configuración
```bash
# Verificar que las variables se configuraron correctamente
az functionapp config appsettings list --name azfunc-analisis-MVP-CARTERA-CR --resource-group rg-analisis-MVP-CARTERA-CR --query "[?name=='AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT' || name=='AZURE_OPENAI_API_KEY'].{name:name, configured:value!=null}" --output table
```

## Comandos de Respaldo (Si no tienes permisos de Azure CLI)

### Opción 1: Azure Portal
1. Ir a Azure Portal → Function Apps → azfunc-analisis-MVP-CARTERA-CR
2. Ir a Settings → Configuration
3. Agregar/editar Application Settings manualmente

### Opción 2: Solicitar a Administrador
Si no tienes permisos, solicitar al administrador de Azure que:
1. Configure las variables usando los comandos de este documento
2. O proporcione acceso de "Contributor" al resource group

## Verificación Final

Después de configurar, verificar que las funciones pueden acceder a los servicios:
```bash
# Verificar logs de la función
az functionapp log tail --name azfunc-analisis-MVP-CARTERA-CR --resource-group rg-analisis-MVP-CARTERA-CR
```

---
**IMPORTANTE**: Mantener estas claves seguras y no compartirlas en repositorios públicos.