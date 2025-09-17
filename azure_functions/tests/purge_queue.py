#!/usr/bin/env python3
"""
Script para purgar (vaciar) la cola de Service Bus desde consola local.
"""

import os
import sys
import json
from pathlib import Path
from azure.servicebus import ServiceBusClient

# Agregar el directorio padre al path para importar módulos compartidos
sys.path.append(str(Path(__file__).parent.parent))

def load_local_settings():
    """Cargar configuración desde local.settings.json"""
    settings_path = Path(__file__).parent.parent / 'local.settings.json'
    
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            return settings.get('Values', {})
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo local.settings.json en {settings_path}")
        return {}

def purge_queue():
    """
    Purgar todos los mensajes de la cola de Service Bus.
    """
    print("🗑️ Purgando cola de Service Bus...")
    print("=" * 50)
    
    try:
        # Cargar configuración
        settings = load_local_settings()
        connection_string = settings.get('SERVICEBUS_CONNECTION_STRING')
        queue_name = settings.get('SERVICEBUS_QUEUE_NAME', 'recoaudit-queue')
        
        if not connection_string:
            print("❌ SERVICEBUS_CONNECTION_STRING no configurado")
            return False
        
        print(f"📋 Cola: {queue_name}")
        print(f"🔗 Conectando a Service Bus...")
        
        # Crear cliente de Service Bus
        with ServiceBusClient.from_connection_string(connection_string) as client:
            with client.get_queue_receiver(queue_name) as receiver:
                
                print("🔄 Recibiendo y eliminando mensajes...")
                
                # Recibir mensajes en lotes y eliminarlos
                total_purged = 0
                batch_size = 100
                
                while True:
                    # Recibir lote de mensajes
                    messages = receiver.receive_messages(max_message_count=batch_size, max_wait_time=5)
                    
                    if not messages:
                        break  # No hay más mensajes
                    
                    # Completar (eliminar) todos los mensajes del lote
                    for message in messages:
                        receiver.complete_message(message)
                        total_purged += 1
                    
                    print(f"   🗑️ Eliminados {len(messages)} mensajes (Total: {total_purged})")
                
                print(f"\n✅ Purga completada: {total_purged} mensajes eliminados")
                
                # Verificar que la cola esté vacía
                print("\n🔍 Verificando estado final...")
                remaining_messages = receiver.receive_messages(max_message_count=1, max_wait_time=2)
                
                if not remaining_messages:
                    print("✅ Cola completamente vacía")
                else:
                    print(f"⚠️ Aún quedan mensajes en la cola")
                
                return True
                
    except Exception as e:
        print(f"❌ Error purgando cola: {str(e)}")
        return False

def purge_dead_letter_queue():
    """
    Purgar mensajes de la cola de dead letter.
    """
    print("\n🗑️ Purgando Dead Letter Queue...")
    print("=" * 50)
    
    try:
        # Cargar configuración
        settings = load_local_settings()
        connection_string = settings.get('SERVICEBUS_CONNECTION_STRING')
        queue_name = settings.get('SERVICEBUS_QUEUE_NAME', 'recoaudit-queue')
        
        if not connection_string:
            print("❌ SERVICEBUS_CONNECTION_STRING no configurado")
            return False
        
        print(f"📋 Dead Letter Queue: {queue_name}")
        
        # Crear cliente de Service Bus para dead letter queue
        with ServiceBusClient.from_connection_string(connection_string) as client:
            with client.get_queue_receiver(queue_name, sub_queue=ServiceBusSubQueue.DEAD_LETTER) as receiver:
                
                print("🔄 Recibiendo y eliminando mensajes de dead letter...")
                
                total_purged = 0
                batch_size = 100
                
                while True:
                    # Recibir lote de mensajes
                    messages = receiver.receive_messages(max_message_count=batch_size, max_wait_time=5)
                    
                    if not messages:
                        break  # No hay más mensajes
                    
                    # Completar (eliminar) todos los mensajes del lote
                    for message in messages:
                        receiver.complete_message(message)
                        total_purged += 1
                    
                    print(f"   🗑️ Eliminados {len(messages)} mensajes DLQ (Total: {total_purged})")
                
                print(f"\n✅ Dead Letter Queue purgada: {total_purged} mensajes eliminados")
                return True
                
    except Exception as e:
        print(f"❌ Error purgando dead letter queue: {str(e)}")
        return False

def main():
    """
    Función principal.
    """
    print("🗑️ Purge Service Bus Queue - CAF Cartera Agents")
    print()
    
    # Preguntar qué purgar
    print("🔧 Opciones de purga:")
    print("1. Purgar cola principal (Active messages)")
    print("2. Purgar Dead Letter Queue")
    print("3. Purgar ambas")
    
    choice = input("\n📝 Selecciona una opción (1-3): ").strip()
    
    success = False
    
    if choice == '1':
        success = purge_queue()
    elif choice == '2':
        # Importar ServiceBusSubQueue
        from azure.servicebus import ServiceBusSubQueue
        success = purge_dead_letter_queue()
    elif choice == '3':
        from azure.servicebus import ServiceBusSubQueue
        success1 = purge_queue()
        success2 = purge_dead_letter_queue()
        success = success1 and success2
    else:
        print("❌ Opción inválida")
        return
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Purga completada exitosamente")
        print("\n💡 Ejecuta 'python3 check_queue_size.py' para verificar")
    else:
        print("❌ Purga falló - revisa los errores arriba")

if __name__ == "__main__":
    main()