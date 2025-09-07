#!/usr/bin/env python3
"""
Script para configurar las variables de entorno en Azure Functions.
"""

import os
import subprocess
from dotenv import load_dotenv

def configure_azure_environment():
    """Configurar variables de entorno en Azure Functions."""
    
    # Cargar variables locales
    env_path = os.path.join('azure_functions', '.env')
    load_dotenv(env_path)
    
    print("🔧 Configurando variables de entorno en Azure Functions...")
    print("="*60)
    
    # Información de la Function App
    function_app_name = "azfunc-analisis-MVP-CARTERA-CR"
    resource_group = "RG-POC-CARTERA-CR"
    
    print(f"📱 Function App: {function_app_name}")
    print(f"📦 Resource Group: {resource_group}")
    print()
    
    # Variables de entorno necesarias
    env_vars = {
        'ServiceBusConnection': os.getenv('ServiceBusConnection'),
        'ServiceBusQueueName': os.getenv('ServiceBusQueueName'),
        'SERVICEBUS_CONNECTION_STRING': os.getenv('SERVICEBUS_CONNECTION_STRING'),
        'SERVICEBUS_QUEUE_NAME': os.getenv('SERVICEBUS_QUEUE_NAME'),
    }
    
    print("📋 Variables a configurar:")
    for key, value in env_vars.items():
        if value:
            # Mostrar solo los primeros y últimos caracteres para seguridad
            masked_value = value[:10] + "..." + value[-10:] if len(value) > 20 else "[CONFIGURADO]"
            print(f"   ✅ {key}: {masked_value}")
        else:
            print(f"   ❌ {key}: NO CONFIGURADO")
    
    print()
    
    # Generar comandos de Azure CLI
    print("🔨 Comandos de Azure CLI para configurar:")
    print("="*40)
    
    for key, value in env_vars.items():
        if value:
            # Escapar comillas en el valor
            escaped_value = value.replace('"', '\\"')
            command = f'az functionapp config appsettings set --name "{function_app_name}" --resource-group "{resource_group}" --settings "{key}={escaped_value}"'
            print(f"\n# Configurar {key}")
            print(command)
    
    print("\n" + "="*40)
    print("\n💡 Para ejecutar automáticamente, copia y pega los comandos anteriores en tu terminal.")
    print("\n⚠️  Nota: Necesitas estar autenticado en Azure CLI (az login)")
    
    # Verificar si Azure CLI está disponible
    try:
        result = subprocess.run(['az', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("\n✅ Azure CLI está disponible")
            
            # Preguntar si ejecutar automáticamente
            print("\n🤖 ¿Quieres que ejecute los comandos automáticamente? (y/n): ", end="")
            response = input().lower().strip()
            
            if response == 'y' or response == 'yes':
                execute_azure_commands(function_app_name, resource_group, env_vars)
            else:
                print("\n📋 Ejecuta manualmente los comandos mostrados arriba.")
        else:
            print("\n❌ Azure CLI no está disponible o no funciona correctamente")
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("\n❌ Azure CLI no está instalado o no está disponible")
        print("\n📥 Instala Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")

def execute_azure_commands(function_app_name, resource_group, env_vars):
    """Ejecutar comandos de Azure CLI automáticamente."""
    
    print("\n🚀 Ejecutando comandos de Azure CLI...")
    
    for key, value in env_vars.items():
        if value:
            try:
                print(f"\n⏳ Configurando {key}...")
                
                command = [
                    'az', 'functionapp', 'config', 'appsettings', 'set',
                    '--name', function_app_name,
                    '--resource-group', resource_group,
                    '--settings', f'{key}={value}'
                ]
                
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print(f"   ✅ {key} configurado exitosamente")
                else:
                    print(f"   ❌ Error configurando {key}: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                print(f"   ⏰ Timeout configurando {key}")
            except Exception as e:
                print(f"   ❌ Error ejecutando comando para {key}: {e}")
    
    print("\n🎉 Configuración completada!")
    print("\n🔄 Reinicia la Function App para aplicar los cambios:")
    print(f"   az functionapp restart --name {function_app_name} --resource-group {resource_group}")

if __name__ == "__main__":
    configure_azure_environment()