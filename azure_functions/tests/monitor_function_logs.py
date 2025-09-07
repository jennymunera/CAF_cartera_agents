#!/usr/bin/env python3
"""
Script para monitorear los logs de Azure Functions en tiempo real
"""

import subprocess
import time
import json
from datetime import datetime, timedelta

def get_recent_function_executions():
    """
    Obtiene las ejecuciones recientes de la función OpenAiProcess
    """
    try:
        # Obtener logs de los últimos 10 minutos
        cmd = [
            "az", "monitor", "activity-log", "list",
            "--resource-group", "RG-POC-CARTERA-CR",
            "--start-time", (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
            "--query", "[?contains(resourceId, 'azfunc-analisis-MVP-CARTERA-CR')]",
            "--output", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logs = json.loads(result.stdout)
            return logs
        else:
            print(f"❌ Error obteniendo logs: {result.stderr}")
            return []
            
    except Exception as e:
        print(f"❌ Error ejecutando comando: {str(e)}")
        return []

def check_function_status():
    """
    Verifica el estado actual de las funciones
    """
    try:
        cmd = [
            "az", "functionapp", "function", "list",
            "--name", "azfunc-analisis-MVP-CARTERA-CR",
            "--resource-group", "RG-POC-CARTERA-CR",
            "--output", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            functions = json.loads(result.stdout)
            print("\n📊 Estado de las funciones:")
            for func in functions:
                name = func.get('name', 'Unknown')
                status = 'Activa' if not func.get('config', {}).get('disabled', False) else 'Deshabilitada'
                print(f"   • {name}: {status}")
            return True
        else:
            print(f"❌ Error obteniendo estado de funciones: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando funciones: {str(e)}")
        return False

def check_service_bus_messages():
    """
    Verifica el estado de los mensajes en Service Bus
    """
    try:
        cmd = [
            "az", "servicebus", "queue", "show",
            "--resource-group", "RG-POC-CARTERA-CR",
            "--namespace-name", "sb-messaging-mvp-cartera-cr",
            "--name", "recoaudit-queue",
            "--query", "{activeMessageCount:countDetails.activeMessageCount,deadLetterMessageCount:countDetails.deadLetterMessageCount}",
            "--output", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            queue_info = json.loads(result.stdout)
            active_count = queue_info.get('activeMessageCount', 0)
            dead_letter_count = queue_info.get('deadLetterMessageCount', 0)
            
            print("\n📬 Estado de Service Bus (recoaudit-queue):")
            print(f"   • Mensajes activos: {active_count}")
            print(f"   • Mensajes en dead letter: {dead_letter_count}")
            
            if dead_letter_count > 0:
                print("   ⚠️  Hay mensajes en dead letter - posible error en procesamiento")
            elif active_count == 0:
                print("   ✅ Cola vacía - mensaje procesado exitosamente")
            else:
                print("   🔄 Mensaje en procesamiento...")
                
            return True
        else:
            print(f"❌ Error obteniendo estado de Service Bus: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando Service Bus: {str(e)}")
        return False

def main():
    print("🔍 Monitor de Azure Functions - OpenAiProcess")
    print("=" * 50)
    print(f"⏰ Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar estado de funciones
    print("\n1️⃣ Verificando estado de funciones...")
    check_function_status()
    
    # Verificar Service Bus
    print("\n2️⃣ Verificando Service Bus...")
    check_service_bus_messages()
    
    # Monitorear por 2 minutos
    print("\n3️⃣ Monitoreando ejecución (2 minutos)...")
    
    for i in range(8):  # 8 iteraciones de 15 segundos = 2 minutos
        print(f"\n⏱️  Verificación {i+1}/8 ({datetime.now().strftime('%H:%M:%S')})")
        
        # Verificar Service Bus cada 15 segundos
        check_service_bus_messages()
        
        if i < 7:  # No esperar en la última iteración
            print("   ⏳ Esperando 15 segundos...")
            time.sleep(15)
    
    print("\n✅ Monitoreo completado")
    print("\n📋 Recomendaciones:")
    print("   • Si hay mensajes en dead letter, revisa los logs de Application Insights")
    print("   • Si la cola está vacía, el mensaje se procesó correctamente")
    print("   • Para logs detallados, ve al portal de Azure > Function App > Monitor")

if __name__ == "__main__":
    main()