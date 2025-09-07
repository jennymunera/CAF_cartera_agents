#!/bin/bash

# Script para configurar una variable individual en Azure Functions
# Uso: ./configure_single_variable.sh VARIABLE_NAME "VARIABLE_VALUE"

FUNCTION_APP_NAME="azfunc-analisis-MVP-CARTERA-CR"
RESOURCE_GROUP="rg-analisis-MVP-CARTERA-CR"

if [ $# -ne 2 ]; then
    echo "Uso: $0 VARIABLE_NAME \"VARIABLE_VALUE\""
    echo "Ejemplo: $0 AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT \"https://docintel-cartera-cr.cognitiveservices.azure.com/\""
    exit 1
fi

VARIABLE_NAME=$1
VARIABLE_VALUE=$2

echo "Configurando variable: $VARIABLE_NAME"
echo "Valor: $VARIABLE_VALUE"
echo "Function App: $FUNCTION_APP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Configurar la variable
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings "$VARIABLE_NAME=$VARIABLE_VALUE"

if [ $? -eq 0 ]; then
    echo "✅ Variable $VARIABLE_NAME configurada exitosamente"
    
    # Verificar la configuración
    echo "Verificando configuración..."
    az functionapp config appsettings list \
      --name $FUNCTION_APP_NAME \
      --resource-group $RESOURCE_GROUP \
      --query "[?name=='$VARIABLE_NAME'].{name:name, configured:value!=null}" \
      --output table
else
    echo "❌ Error configurando variable $VARIABLE_NAME"
    exit 1
fi