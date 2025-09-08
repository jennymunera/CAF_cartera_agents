#!/bin/bash

# Script para corregir la configuración de Azure OpenAI en Azure Functions
# Este script debe ejecutarse con permisos de administrador en Azure

echo "🔧 Corrigiendo configuración de Azure OpenAI..."

# Configuración de Azure Functions
FUNCTION_APP_NAME="asafunctaimvpcarteracr"
RESOURCE_GROUP="rg-mvp-cartera-cr"

# Valores correctos basados en local.settings.json
AZURE_OPENAI_ENDPOINT="https://oai-poc-idatafactory-cr.openai.azure.com/"
AZURE_OPENAI_API_KEY="dc1b72e6efdb4ca98f7c3b07fbb2ce58"
AZURE_OPENAI_API_VERSION="2025-04-01-preview"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-2"

echo "📋 Configurando variables de Azure OpenAI..."
echo "   - Endpoint: $AZURE_OPENAI_ENDPOINT"
echo "   - API Version: $AZURE_OPENAI_API_VERSION"
echo "   - Deployment: $AZURE_OPENAI_DEPLOYMENT_NAME"

# Actualizar configuración en Azure Functions
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
    AZURE_OPENAI_DEPLOYMENT_NAME="$AZURE_OPENAI_DEPLOYMENT_NAME"

if [ $? -eq 0 ]; then
    echo "✅ Configuración de Azure OpenAI actualizada exitosamente"
    
    echo "🔍 Verificando configuración..."
    az functionapp config appsettings list \
      --name $FUNCTION_APP_NAME \
      --resource-group $RESOURCE_GROUP \
      --query "[?starts_with(name, 'AZURE_OPENAI')].{name:name, value:value}" \
      --output table
    
    echo "🔄 Reiniciando Azure Functions para aplicar cambios..."
    az functionapp restart \
      --name $FUNCTION_APP_NAME \
      --resource-group $RESOURCE_GROUP
    
    if [ $? -eq 0 ]; then
        echo "✅ Azure Functions reiniciado exitosamente"
        echo "⏱️  Esperar 2-3 minutos para que el PoolingProcess use la nueva configuración"
    else
        echo "⚠️  Error reiniciando Azure Functions"
    fi
else
    echo "❌ Error actualizando configuración de Azure OpenAI"
    echo "💡 Verificar permisos de Azure CLI y credenciales"
    exit 1
fi

echo "📝 Problema identificado:"
echo "   - El PoolingProcess estaba usando endpoint: openai-tech2.openai.azure.com (incorrecto)"
echo "   - Ahora debería usar: oai-poc-idatafactory-cr.openai.azure.com (correcto)"
echo "   - Error 401 debería resolverse después del reinicio"