# Configuración de Azure Application Insights

Este documento describe cómo configurar Azure Application Insights para el sistema de procesamiento de documentos.

## Requisitos Previos

1. Una suscripción activa de Azure
2. Permisos para crear recursos en Azure
3. Azure CLI instalado (opcional)

## Pasos de Configuración

### 1. Crear un Recurso de Application Insights

#### Opción A: Portal de Azure
1. Inicia sesión en el [Portal de Azure](https://portal.azure.com)
2. Haz clic en "Crear un recurso"
3. Busca "Application Insights"
4. Selecciona "Application Insights" y haz clic en "Crear"
5. Completa los campos:
   - **Suscripción**: Selecciona tu suscripción
   - **Grupo de recursos**: Crea uno nuevo o selecciona uno existente
   - **Nombre**: Elige un nombre único (ej: `document-processor-insights`)
   - **Región**: Selecciona la región más cercana
   - **Modo de recurso**: Selecciona "Basado en área de trabajo"

#### Opción B: Azure CLI
```bash
# Crear grupo de recursos (si no existe)
az group create --name myResourceGroup --location "East US"

# Crear Application Insights
az monitor app-insights component create \
  --app document-processor-insights \
  --location "East US" \
  --resource-group myResourceGroup \
  --application-type web
```

### 2. Obtener las Credenciales

Después de crear el recurso:

1. Ve al recurso de Application Insights en el portal
2. En el menú izquierdo, selecciona "Información esencial"
3. Copia los siguientes valores:
   - **Connection String** (Cadena de conexión)
   - **Instrumentation Key** (Clave de instrumentación)

### 3. Configurar Variables de Entorno

1. Copia el archivo `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env` y actualiza las siguientes variables:
   ```env
   # Azure Application Insights
   AZURE_APP_INSIGHTS_CONNECTION_STRING=InstrumentationKey=tu-instrumentation-key;IngestionEndpoint=https://tu-region.in.applicationinsights.azure.com/;LiveEndpoint=https://tu-region.livediagnostics.monitor.azure.com/
   AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY=tu-instrumentation-key
   
   # Configuración de Logging
   LOG_LEVEL=INFO
   LOG_TO_FILE=true
   LOG_FILE_PATH=logs/application.log
   LOG_TO_CONSOLE=true
   LOG_FORMAT=json
   ```

### 4. Instalar Dependencias

Si no están instaladas, instala las dependencias necesarias:

```bash
pip install opencensus-ext-azure opencensus-ext-logging
```

## Características del Sistema de Logging

### Logging Estructurado
- **Formato JSON**: Todos los logs se generan en formato JSON para facilitar el análisis
- **Metadatos Enriquecidos**: Cada log incluye información contextual como operation_id, timestamps, y propiedades personalizadas
- **Correlación de Operaciones**: Las operaciones se pueden rastrear a través de múltiples componentes

### Tipos de Eventos Registrados

1. **Operaciones**:
   - Inicio y fin de operaciones
   - Duración y estado de éxito
   - Metadatos de resultado

2. **Procesamiento de Documentos**:
   - Documentos procesados
   - Tokens contados
   - Chunks generados

3. **Batch Jobs**:
   - Creación de trabajos batch
   - Estado de procesamiento
   - Resultados de análisis

4. **Errores**:
   - Excepciones capturadas
   - Contexto del error
   - Stack traces

### Archivos de Log

- **Ubicación**: `logs/application.log`
- **Rotación**: Automática cuando el archivo supera 10MB
- **Retención**: Se mantienen 5 archivos de respaldo
- **Formato**: JSON estructurado

## Monitoreo en Azure Portal

### Dashboards Recomendados

1. **Vista General de Operaciones**:
   - Número total de documentos procesados
   - Tiempo promedio de procesamiento
   - Tasa de éxito/error

2. **Análisis de Performance**:
   - Duración de operaciones por tipo
   - Cuellos de botella en el procesamiento
   - Uso de recursos

3. **Monitoreo de Errores**:
   - Errores por tipo
   - Tendencias de errores
   - Alertas automáticas

### Consultas KQL Útiles

```kusto
// Documentos procesados en las últimas 24 horas
customEvents
| where timestamp > ago(24h)
| where name == "document_processed"
| summarize count() by bin(timestamp, 1h)

// Errores por tipo
exceptions
| where timestamp > ago(24h)
| summarize count() by type
| order by count_ desc

// Duración promedio de operaciones
customEvents
| where name == "operation_end"
| where customDimensions.success == "true"
| extend duration = todouble(customDimensions.duration_ms)
| summarize avg(duration) by customDimensions.operation_name
```

## Solución de Problemas

### Problemas Comunes

1. **No se envían logs a Application Insights**:
   - Verifica que la connection string sea correcta
   - Asegúrate de que las dependencias estén instaladas
   - Revisa los permisos de red/firewall

2. **Logs no aparecen en tiempo real**:
   - Application Insights puede tener un retraso de 1-2 minutos
   - Usa Live Metrics para monitoreo en tiempo real

3. **Errores de autenticación**:
   - Verifica que la instrumentation key sea válida
   - Asegúrate de que el recurso esté activo

### Logs de Depuración

Para habilitar logs de depuración del sistema de logging:

```env
LOG_LEVEL=DEBUG
```

## Mejores Prácticas

1. **Seguridad**:
   - No incluyas información sensible en los logs
   - Usa variables de entorno para credenciales
   - Implementa rotación de claves regularmente

2. **Performance**:
   - Usa sampling para aplicaciones de alto volumen
   - Configura filtros para reducir ruido
   - Monitorea el costo de ingesta de datos

3. **Mantenimiento**:
   - Revisa y limpia logs antiguos regularmente
   - Actualiza dashboards según necesidades del negocio
   - Configura alertas proactivas

## Recursos Adicionales

- [Documentación oficial de Application Insights](https://docs.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)
- [Guía de KQL](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/)
- [Mejores prácticas de logging](https://docs.microsoft.com/en-us/azure/azure-monitor/app/api-custom-events-metrics)