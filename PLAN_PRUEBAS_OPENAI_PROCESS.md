# Plan de Pruebas - OpenAiProcess en Azure

## Estado Actual Verificado ✅

### 1. Azure Blob Storage
- **Storage Account**: `asmvpcarteracr` ✅
- **Container**: `caf-documents` ✅
- **Documentos disponibles**: 19 documentos en proyecto `CFA009660` ✅
- **Estructura**: `basedocuments/CFA009660/raw/` ✅

### 2. Azure Functions
- **Function App**: `azfunc-analisis-MVP-CARTERA-CR` ✅
- **Funciones desplegadas**: `OpenAiProcess` y `PoolingProcess` ✅
- **Variables de entorno configuradas**:
  - `AZURE_STORAGE_CONNECTION_STRING` ✅
  - `AZURE_STORAGE_CONTAINER_NAME` ✅
  - Otras variables pendientes de verificación ⚠️

### 3. Documentos de Prueba
- **Proyecto CFA009660**: 19 documentos reales
- **Tipos**: PDF, DOCX (contratos, informes, auditorías)
- **Ubicación**: `basedocuments/CFA009660/raw/`

## Plan de Pruebas Estructurado

### Fase 1: Verificación Previa
1. **Confirmar configuración de Service Bus**
   - Queue: `recoaudit-queue`
   - Connection string configurado

2. **Verificar variables de OpenAI**
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_DEPLOYMENT_NAME`

3. **Confirmar Document Intelligence**
   - `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`
   - `AZURE_DOCUMENT_INTELLIGENCE_KEY`

### Fase 2: Preparación del Mensaje de Prueba
1. **Crear mensaje Service Bus** con estructura:
   ```json
   {
     "project_name": "CFA009660",
     "document_names": ["FFD-CFA009660--CFA 9660 Ficha Finalizacion Desembolsos_Tarata  Anzaldo  Rio Caine GR_Final.pdf"],
     "analysis_type": "desembolsos",
     "timestamp": "2025-01-06T22:15:00Z"
   }
   ```

### Fase 3: Ejecución de Pruebas
1. **Enviar mensaje a Service Bus**
2. **Monitorear ejecución de OpenAiProcess**
3. **Verificar logs en Application Insights**
4. **Confirmar procesamiento en Blob Storage**

### Fase 4: Verificación de Resultados
1. **Documentos procesados en**: `basedocuments/CFA009660/processed/`
   - Subcarpeta `DI/` (Document Intelligence)
   - Subcarpeta `chunks/` (Chunking)
2. **Resultados finales en**: `basedocuments/CFA009660/results/`
3. **Logs de ejecución**

## Documentos de Prueba Recomendados

### Documento Principal (Desembolsos)
- **Archivo**: `FFD-CFA009660--CFA 9660 Ficha Finalizacion Desembolsos_Tarata  Anzaldo  Rio Caine GR_Final.pdf`
- **Tipo**: Ficha de Finalización de Desembolsos
- **Análisis**: Desembolsos

### Documentos Alternativos
1. **Auditoría**: `IXP-CFA009660-2021--Informe Auditoría 2021.pdf`
2. **Contrato**: `con-cfa009660--CONTRATO DE PRESTAMO_ suscrito.pdf`
3. **Informe**: `IFS-CFA009660-2025-TRIM1--CONST INFORME TRISMESTRAL KM 25 - RIO CAINE.pdf`

## Comandos de Monitoreo

### 1. Verificar mensajes en Service Bus
```bash
az servicebus queue show --resource-group rg-analisis-MVP-CARTERA-CR --namespace-name sb-analisis-MVP-CARTERA-CR --name recoaudit-queue
```

### 2. Monitorear logs de Function
```bash
az functionapp logs tail --name azfunc-analisis-MVP-CARTERA-CR --resource-group rg-analisis-MVP-CARTERA-CR
```

### 3. Verificar resultados en Blob Storage
```python
from utils.blob_storage_client import BlobStorageClient
client = BlobStorageClient()
# Verificar documentos procesados
processed = client.list_processed_documents('CFA009660')
print(f"Documentos procesados: {len(processed)}")
```

## Criterios de Éxito

✅ **Función se ejecuta sin errores**
✅ **Documento se procesa con Document Intelligence**
✅ **Chunks se generan correctamente**
✅ **Resultados se guardan en Blob Storage**
✅ **Logs muestran ejecución completa**

## Riesgos y Mitigaciones

### Riesgo 1: Permisos de Azure
- **Problema**: Error de autorización en comandos Azure CLI
- **Mitigación**: Usar Azure Portal para monitoreo manual

### Riesgo 2: Variables de entorno faltantes
- **Problema**: Función falla por configuración incompleta
- **Mitigación**: Verificar todas las variables antes de ejecutar

### Riesgo 3: Límites de OpenAI
- **Problema**: Cuotas o límites de API
- **Mitigación**: Usar documento pequeño para primera prueba

## Próximos Pasos

1. **Solicitar autorización** para ejecutar el plan
2. **Verificar configuración** de Service Bus y OpenAI
3. **Preparar mensaje** de prueba
4. **Ejecutar prueba** controlada
5. **Analizar resultados** y optimizar si es necesario

---

**Fecha**: 2025-01-06
**Estado**: Listo para autorización
**Documentos**: 19 disponibles en CFA009660
**Función**: OpenAiProcess desplegada y configurada