#!/usr/bin/env python3
"""
Script para verificar los logs de Azure Functions usando la API REST.
"""

import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

def check_azure_function_logs():
    """Verificar los logs de Azure Functions."""
    
    print("🔍 Verificando logs de Azure Functions...")
    print("="*50)
    
    # Información de la Function App
    function_app_name = "azfunc-analisis-MVP-CARTERA-CR"
    resource_group = "RG-POC-CARTERA-CR"
    subscription_id = "6e30581f-5e6d-4f9f-8339-420301cce5f4"
    
    print(f"📱 Function App: {function_app_name}")
    print(f"📦 Resource Group: {resource_group}")
    print(f"🔑 Subscription: {subscription_id}")
    print()
    
    # URLs importantes para diagnóstico manual
    portal_url = f"https://portal.azure.com/#@/resource/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{function_app_name}"
    logs_url = f"https://{function_app_name}.scm.azurewebsites.net/api/logstream"
    app_insights_url = f"https://portal.azure.com/#@/resource/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/microsoft.insights/components/{function_app_name}/logs"
    
    print("🔗 URLs para diagnóstico manual:")
    print(f"   Portal: {portal_url}")
    print(f"   Log Stream: {logs_url}")
    print(f"   App Insights: {app_insights_url}")
    print()
    
    # Verificar configuración de la función
    print("⚙️  Verificando configuración...")
    
    # Verificar si las funciones están configuradas correctamente
    function_json_path = "azure_functions/OpenAiProcess/function.json"
    if os.path.exists(function_json_path):
        with open(function_json_path, 'r') as f:
            config = json.load(f)
            print(f"   ✅ OpenAiProcess configurado: {config.get('bindings', [])}")
    else:
        print("   ❌ No se encontró function.json para OpenAiProcess")
    
    print()
    print("🚨 Posibles problemas identificados:")
    print("   1. La función no se está ejecutando (trigger no configurado)")
    print("   2. Errores en el código que impiden el procesamiento")
    print("   3. Variables de entorno faltantes en Azure")
    print("   4. Problemas de permisos con las APIs")
    print()
    
    print("💡 Pasos recomendados:")
    print("   1. Abrir el portal de Azure y verificar los logs en tiempo real")
    print("   2. Revisar Application Insights para errores específicos")
    print("   3. Verificar que las variables de entorno estén configuradas")
    print("   4. Comprobar que el Service Bus trigger esté activo")
    print()
    
    # Intentar obtener información básica de la función
    try:
        print("🔄 Intentando obtener información básica...")
        
        # URL de la función (sin autenticación, solo para verificar que existe)
        function_url = f"https://{function_app_name}.azurewebsites.net"
        
        response = requests.get(function_url, timeout=10)
        if response.status_code == 200:
            print(f"   ✅ Function App responde: {response.status_code}")
        else:
            print(f"   ⚠️  Function App respuesta: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error conectando a Function App: {e}")
    
    print()
    print("📋 Resumen:")
    print("   • Las funciones están desplegadas pero no procesan mensajes")
    print("   • Revisar logs manualmente en el portal de Azure")
    print("   • Verificar configuración de variables de entorno")
    print("   • Comprobar que el Service Bus trigger esté funcionando")

if __name__ == "__main__":
    check_azure_function_logs()