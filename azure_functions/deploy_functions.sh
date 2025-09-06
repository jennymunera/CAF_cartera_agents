#!/bin/bash

# Script para desplegar las Azure Functions migradas
# Este script empaqueta y despliega las funciones OpenAiProcess y PoolingProcess

set -e

# Variables de configuración
FUNCTION_APP_NAME="azfunc-analisis-MVP-CARTERA-CR"
RESOURCE_GROUP="RG-POC-CARTERA-CR"
FUNCTIONS_DIR="azure_functions"

echo "Iniciando despliegue de Azure Functions..."
echo "Function App: $FUNCTION_APP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -d "$FUNCTIONS_DIR" ]; then
    echo "Error: Directorio $FUNCTIONS_DIR no encontrado"
    echo "Ejecuta este script desde el directorio raíz del proyecto"
    exit 1
fi

# Cambiar al directorio de funciones
cd "$FUNCTIONS_DIR"

echo "Verificando estructura de archivos..."
echo "Archivos en el directorio:"
ls -la
echo ""

# Verificar que las funciones existen
if [ ! -d "OpenAiProcess" ]; then
    echo "Error: Función OpenAiProcess no encontrada"
    exit 1
fi

if [ ! -d "PoolingProcess" ]; then
    echo "Error: Función PoolingProcess no encontrada"
    exit 1
fi

echo "Funciones encontradas:"
echo "✓ OpenAiProcess"
echo "✓ PoolingProcess"
echo ""

# Crear archivo .funcignore si no existe
if [ ! -f ".funcignore" ]; then
    echo "Creando archivo .funcignore..."
    cat > .funcignore << EOF
.git*
.vscode
__pycache__
*.pyc
.env
local.settings.json
.DS_Store
*.log
logs/
tests/
*.md
EOF
fi

# Verificar autenticación de Azure
echo "Verificando autenticación de Azure..."
az account show --query "name" --output tsv
if [ $? -ne 0 ]; then
    echo "Error: No estás autenticado en Azure"
    echo "Ejecuta: az login"
    exit 1
fi

echo "Autenticación verificada ✓"
echo ""

# Desplegar usando Azure CLI
echo "Desplegando funciones a Azure..."
echo "Esto puede tomar varios minutos..."
echo ""

# Usar zip deploy para subir las funciones
echo "Creando paquete de despliegue..."
zip -r ../functions-deploy.zip . -x "*.git*" "*.DS_Store" "local.settings.json"

echo "Desplegando paquete..."
az functionapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --src "../functions-deploy.zip"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Despliegue completado exitosamente!"
    echo ""
    echo "Funciones desplegadas:"
    echo "- OpenAiProcess (Service Bus Trigger)"
    echo "- PoolingProcess (Timer Trigger - cada 5 minutos)"
    echo ""
    echo "URLs de la Function App:"
    echo "- Portal: https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id --output tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME"
    echo "- Logs: https://$FUNCTION_APP_NAME.scm.azurewebsites.net/api/logstream"
    echo ""
    echo "Para probar las funciones:"
    echo "1. Envía un mensaje a una de las colas del Service Bus"
    echo "2. Verifica los logs en Application Insights"
    echo "3. El PoolingProcess se ejecutará automáticamente cada 5 minutos"
else
    echo "❌ Error durante el despliegue"
    exit 1
fi

# Limpiar archivo temporal
rm -f ../functions-deploy.zip

echo ""
echo "Despliegue finalizado."