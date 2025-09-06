#!/bin/bash

# Script para configurar Service Bus en Azure Function App
# Este script actualiza las configuraciones de la aplicación con las conexiones del Service Bus

set -e

# Variables de configuración
FUNCTION_APP_NAME="azfunc-analisis-MVP-CARTERA-CR"
RESOURCE_GROUP="RG-POC-CARTERA-CR"
SERVICE_BUS_CONNECTION="YOUR_SERVICE_BUS_CONNECTION_STRING_HERE"

echo "Configurando Service Bus para Azure Function App: $FUNCTION_APP_NAME"

# Configurar la cadena de conexión del Service Bus
echo "Actualizando ServiceBusConnection..."
az functionapp config appsettings set \
  --name "$FUNCTION_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings "ServiceBusConnection=$SERVICE_BUS_CONNECTION"

# Configurar los nombres de las colas disponibles
echo "Configurando nombres de colas..."
az functionapp config appsettings set \
  --name "$FUNCTION_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "ServiceBusQueueName=recoaudit-queue" \
    "ServiceBusQueueNameDesem=recodesem-queue" \
    "ServiceBusQueueNameProd=recoprod-queue"

# Verificar la configuración
echo "Verificando configuración del Service Bus..."
az functionapp config appsettings list \
  --name "$FUNCTION_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?contains(name, 'ServiceBus')].{Name:name, Value:value}" \
  --output table

echo "Configuración del Service Bus completada exitosamente!"
echo ""
echo "Colas disponibles:"
echo "- recoaudit-queue (Auditoría)"
echo "- recodesem-queue (Desembolsos)"
echo "- recoprod-queue (Productos)"
echo ""
echo "Para usar una cola específica, envía mensajes con el campo 'queue_type' en el JSON:"
echo "- 'audit' para recoaudit-queue"
echo "- 'desem' para recodesem-queue"
echo "- 'prod' para recoprod-queue"