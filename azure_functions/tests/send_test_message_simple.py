#!/usr/bin/env python3
"""
Script para enviar un mensaje de prueba más simple al Service Bus.
"""

import os
import json
from azure.servicebus import ServiceBusClient, ServiceBusMessage, TransportType
from dotenv import load_dotenv

def send_simple_test_message():
    """Enviar mensaje de prueba simple al Service Bus."""
    # Cargar variables de entorno desde local.settings.json
    import json
    settings_path = os.path.join(os.path.dirname(__file__), '..', 'local.settings.json')
    
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            values = settings.get('Values', {})
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo local.settings.json en {settings_path}")
        return
    
    # Configuración del Service Bus usando las variables de local.settings.json
    connection_string = values.get('SERVICEBUS_CONNECTION_STRING') or values.get('ServiceBusConnection') or values.get('ServiceBusConnectionString')
    queue_name = values.get('SERVICEBUS_QUEUE_NAME') or values.get('ServiceBusQueueName', 'recoaudit-queue')
    
    if not connection_string:
        print("❌ SERVICEBUS_CONNECTION_STRING no configurado")
        return
    
    # Mensaje de prueba con proyecto real CFA009660
    test_message = {
        "project_name": "CFA------",
        "queue_type": "processing"
    }
    
    try:
        # Crear cliente del Service Bus
        # Usar AMQP over WebSockets (puerto 443) para redes restringidas
        servicebus_client = ServiceBusClient.from_connection_string(
            conn_str=connection_string,
            transport_type=TransportType.AmqpOverWebsocket
        )
        
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
