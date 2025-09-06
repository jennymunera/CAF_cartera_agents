#!/bin/bash

# Script para redesplegar Azure Functions con código completo
# Autor: Sistema de migración Azure Functions
# Fecha: $(date)

set -e

echo "🚀 Iniciando redespliegue completo de Azure Functions..."

# Variables
FUNCTION_APP_NAME="azfunc-analisis-MVP-CARTERA-CR"
RESOURCE_GROUP="RG-POC-CARTERA-CR"
DEPLOYMENT_ZIP="deployment_complete.zip"

# Verificar que estamos en el directorio correcto
if [ ! -f "host.json" ]; then
    echo "❌ Error: No se encuentra host.json. Ejecuta desde el directorio azure_functions"
    exit 1
fi

# Limpiar deployment anterior si existe
if [ -f "$DEPLOYMENT_ZIP" ]; then
    echo "🧹 Eliminando deployment anterior..."
    rm "$DEPLOYMENT_ZIP"
fi

# Crear el archivo ZIP con toda la estructura
echo "📦 Creando archivo de despliegue completo..."

# Incluir archivos de configuración raíz
zip -r "$DEPLOYMENT_ZIP" host.json local.settings.json .funcignore

# Incluir OpenAiProcess con todos sus archivos
echo "📁 Agregando OpenAiProcess..."
zip -r "$DEPLOYMENT_ZIP" OpenAiProcess/

# Incluir PoolingProcess con todos sus archivos
echo "📁 Agregando PoolingProcess..."
zip -r "$DEPLOYMENT_ZIP" PoolingProcess/

# Verificar contenido del ZIP
echo "📋 Contenido del archivo de despliegue:"
zip -sf "$DEPLOYMENT_ZIP"

# Verificar autenticación Azure
echo "🔐 Verificando autenticación Azure..."
az account show --output table

if [ $? -ne 0 ]; then
    echo "❌ Error: No estás autenticado en Azure. Ejecuta 'az login'"
    exit 1
fi

# Desplegar a Azure
echo "☁️ Desplegando a Azure Function App: $FUNCTION_APP_NAME..."
az functionapp deployment source config-zip \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --src "$DEPLOYMENT_ZIP" \
    --build-remote true \
    --verbose

if [ $? -eq 0 ]; then
    echo "✅ Despliegue completado exitosamente!"
    
    # Esperar un momento para que el despliegue se complete
    echo "⏳ Esperando que el despliegue se complete..."
    sleep 30
    
    # Verificar funciones desplegadas
    echo "🔍 Verificando funciones desplegadas..."
    az functionapp function list \
        --name "$FUNCTION_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output table
    
    echo ""
    echo "🎉 ¡Redespliegue completo exitoso!"
    echo "📊 Puedes verificar el estado en:"
    echo "   - Azure Portal: https://portal.azure.com"
    echo "   - Function App: $FUNCTION_APP_NAME"
    echo "   - Resource Group: $RESOURCE_GROUP"
    echo ""
    echo "🔍 Para verificar logs:"
    echo "   az functionapp logs tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP"
    
else
    echo "❌ Error durante el despliegue"
    exit 1
fi

# Limpiar archivo temporal
echo "🧹 Limpiando archivos temporales..."
rm "$DEPLOYMENT_ZIP"

echo "✨ Proceso completado!"