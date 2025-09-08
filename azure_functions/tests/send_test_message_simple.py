#!/usr/bin/env python3
"""
Script para enviar un mensaje de prueba más simple al Service Bus.
"""

import os
import json
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from dotenv import load_dotenv

def send_simple_test_message():
    """Enviar mensaje de prueba simple al Service Bus."""
    # Cargar variables de entorno desde el directorio azure_functions
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    
    # Configuración del Service Bus
    connection_string = os.getenv('SERVICEBUS_CONNECTION_STRING') or os.getenv('ServiceBusConnection')
    queue_name = os.getenv('SERVICEBUS_QUEUE_NAME') or os.getenv('ServiceBusQueueName', 'recoaudit-queue')
    
    if not connection_string:
        print("❌ SERVICEBUS_CONNECTION_STRING no configurado")
        return
    
    # Mensaje de prueba con proyecto real CFA009660
    test_message = {
        "project_name": "CFA009660",
        "queue_type": "processing"
    }
    
    try:
        # Crear cliente del Service Bus
        servicebus_client = ServiceBusClient.from_connection_string(connection_string)
        
        with servicebus_client:
            # Obtener sender para la cola
            sender = servicebus_client.get_queue_sender(queue_name=queue_name)
            
            with sender:
                # Crear mensaje
                message = ServiceBusMessage(json.dumps(test_message))
                
                # Enviar mensaje
                sender.send_messages(message)
                
                print("✅ Mensaje de prueba enviado exitosamente")
                print(f"📦 Cola: {queue_name}")
                print(f"📄 Contenido: {json.dumps(test_message, indent=2)}")
                print("\n🔍 Monitorea los logs de Azure Functions para ver el procesamiento")
                print("💡 Este mensaje debería generar un error controlado que nos ayude a diagnosticar")
                
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")

if __name__ == "__main__":
    send_simple_test_message()