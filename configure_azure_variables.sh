#!/bin/bash

# Script para configurar variables de entorno en Azure Functions
# Ejecutar este script después de obtener los valores reales de las variables

echo "Configurando variables de entorno en Azure Functions..."

# Nombre de la Function App y Resource Group
FUNCTION_APP_NAME="azfunc-analisis-MVP-CARTERA-CR"
RESOURCE_GROUP="rg-analisis-MVP-CARTERA-CR"

# IMPORTANTE: Reemplazar estos valores con los reales antes de ejecutar
echo "⚠️  IMPORTANTE: Reemplazar los valores de ejemplo con los reales antes de ejecutar"

# Variables críticas que DEBEN configurarse
echo "Configurando variables críticas..."

az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://docintel-cartera-cr.cognitiveservices.azure.com/" \
    AZURE_DOCUMENT_INTELLIGENCE_KEY="your_document_intelligence_key_here" \
    AZURE_OPENAI_API_KEY="your_openai_api_key_here" \
    AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=asmvpcarteracr;AccountKey=your_storage_key_here;EndpointSuffix=core.windows.net" \
    ServiceBusConnection="Endpoint=sb://your-servicebus.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=your_servicebus_key_here"

if [ $? -eq 0 ]; then
    echo "✅ Variables críticas configuradas exitosamente"
else
    echo "❌ Error configurando variables críticas"
    exit 1
fi

# Variables opcionales de Application Insights
echo "Configurando variables de Application Insights (opcionales)..."

az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=your_instrumentation_key;IngestionEndpoint=https://your-region.in.applicationinsights.azure.com/" \
    AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY="your_app_insights_instrumentation_key_here"

if [ $? -eq 0 ]; then
    echo "✅ Variables de Application Insights configuradas exitosamente"
else
    echo "⚠️  Error configurando variables de Application Insights (no crítico)"
fi

# Verificar configuración
echo "Verificando configuración..."
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[?name=='AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT' || name=='AZURE_OPENAI_API_KEY' || name=='AZURE_STORAGE_CONNECTION_STRING' || name=='ServiceBusConnection'].{name:name, configured:value!=null}" \
  --output table

echo "✅ Configuración completada. Verificar que todas las variables críticas estén configuradas."
echo "📋 Consultar VERIFICACION_VARIABLES_ENTORNO.md para más detalles."