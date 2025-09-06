#!/usr/bin/env python3
"""
Script para enviar mensaje de prueba al Service Bus para activar OpenAiProcess
"""

import json
import os
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def send_test_message():
    """
    Envía un mensaje de prueba al Service Bus para activar la función OpenAiProcess
    """
    
    # Obtener variables de entorno
    connection_string = os.getenv('SERVICEBUS_CONNECTION_STRING')
    queue_name = os.getenv('SERVICEBUS_QUEUE_NAME', 'document-processing-queue')
    
    if not connection_string:
        print("❌ Error: SERVICEBUS_CONNECTION_STRING no está configurada")
        return False
    
    # Crear mensaje de prueba
    test_message = {
        "project_name": "CFA009660",
        "document_name": "IXP-CFA009660-2021--Informe Auditoría 2021.pdf",
        "document_type": "Auditoria",  # Puede ser: Auditoria, Desembolsos, Productos
        "queue_type": "processing"
    }
    
    try:
        # Crear cliente de Service Bus
        with ServiceBusClient.from_connection_string(connection_string) as client:
            with client.get_queue_sender(queue_name) as sender:
                # Crear mensaje
                message = ServiceBusMessage(
                    json.dumps(test_message),
                    content_type="application/json"
                )
                
                # Enviar mensaje
                sender.send_messages(message)
                
                print("✅ Mensaje enviado exitosamente al Service Bus")
                print(f"📋 Contenido del mensaje: {json.dumps(test_message, indent=2)}")
                print(f"🎯 Cola: {queue_name}")
                
                return True
                
    except Exception as e:
        print(f"❌ Error enviando mensaje: {str(e)}")
        return False

def check_service_bus_config():
    """
    Verifica la configuración del Service Bus
    """
    connection_string = os.getenv('SERVICEBUS_CONNECTION_STRING')
    queue_name = os.getenv('SERVICEBUS_QUEUE_NAME', 'document-processing-queue')
    
    print("🔍 Verificando configuración de Service Bus:")
    print(f"   Connection String: {'✅ Configurada' if connection_string else '❌ No configurada'}")
    print(f"   Queue Name: {queue_name}")
    
    return bool(connection_string)

if __name__ == "__main__":
    print("🚀 Script de prueba para OpenAiProcess")
    print("=" * 50)
    
    # Verificar configuración
    if not check_service_bus_config():
        print("\n❌ Configuración incompleta. Verifica las variables de entorno.")
        exit(1)
    
    # Enviar mensaje de prueba
    print("\n📤 Enviando mensaje de prueba...")
    success = send_test_message()
    
    if success:
        print("\n🎉 ¡Mensaje enviado! La función OpenAiProcess debería activarse automáticamente.")
        print("\n📊 Para monitorear la ejecución:")
        print("   1. Ve al portal de Azure")
        print("   2. Navega a tu Function App")
        print("   3. Revisa los logs en tiempo real")
    else:
        print("\n❌ Error enviando el mensaje. Revisa la configuración.")