#!/usr/bin/env python3
"""
Script para diagnosticar las variables de entorno de OpenAI en Azure Functions
y comparar las configuraciones entre OpenAiProcess y PoolingProcess.
"""

import os
import json
from typing import Dict, Any

def check_openai_variables() -> Dict[str, Any]:
    """
    Verifica todas las variables de entorno relacionadas con OpenAI
    """
    variables = {
        'AZURE_OPENAI_API_KEY': os.getenv('AZURE_OPENAI_API_KEY'),
        'AZURE_OPENAI_ENDPOINT': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'AZURE_OPENAI_API_VERSION': os.getenv('AZURE_OPENAI_API_VERSION'),
        'AZURE_OPENAI_DEPLOYMENT_NAME': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    }
    
    return variables

def analyze_configuration_differences():
    """
    Analiza las diferencias de configuración entre OpenAiProcess y PoolingProcess
    """
    print("=== ANÁLISIS DE CONFIGURACIÓN OPENAI ===")
    print()
    
    # Verificar variables actuales
    variables = check_openai_variables()
    
    print("Variables de entorno actuales:")
    for key, value in variables.items():
        if value:
            # Mostrar solo los primeros y últimos caracteres de valores sensibles
            if 'KEY' in key and len(value) > 10:
                display_value = f"{value[:8]}...{value[-4:]}"
            else:
                display_value = value
            print(f"  ✓ {key}: {display_value}")
        else:
            print(f"  ✗ {key}: NO DEFINIDA")
    
    print()
    print("=== DIFERENCIAS DE CONFIGURACIÓN ===")
    print()
    
    print("OpenAiProcess (openai_batch_processor.py):")
    print("  - endpoint: os.getenv('AZURE_OPENAI_ENDPOINT', 'https://oai-poc-idatafactory-cr.openai.azure.com/')")
    print("  - api_version: os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')")
    print("  - deployment_name: os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o-2')")
    print("  - api_key: os.getenv('AZURE_OPENAI_API_KEY') [REQUERIDA]")
    print()
    
    print("PoolingProcess (__init__.py):")
    print("  - endpoint: os.getenv('AZURE_OPENAI_ENDPOINT') [REQUERIDA]")
    print("  - api_version: os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')")
    print("  - api_key: os.getenv('AZURE_OPENAI_API_KEY') [REQUERIDA]")
    print()
    
    print("=== PROBLEMAS IDENTIFICADOS ===")
    print()
    
    # Verificar problemas específicos
    problems = []
    
    if not variables['AZURE_OPENAI_API_KEY']:
        problems.append("❌ AZURE_OPENAI_API_KEY no está definida")
    
    if not variables['AZURE_OPENAI_ENDPOINT']:
        problems.append("❌ AZURE_OPENAI_ENDPOINT no está definida (PoolingProcess la requiere)")
        print("   → OpenAiProcess usa valor por defecto, pero PoolingProcess requiere que esté definida")
    
    # Verificar diferencias en API version
    current_version = variables['AZURE_OPENAI_API_VERSION']
    if current_version:
        if current_version == '2024-02-15-preview':
            print("⚠️  API Version coincide con PoolingProcess pero difiere de OpenAiProcess")
        elif current_version == '2025-04-01-preview':
            print("⚠️  API Version coincide con OpenAiProcess pero difiere de PoolingProcess")
        else:
            print(f"⚠️  API Version personalizada: {current_version}")
    
    if not problems:
        print("✅ No se encontraron problemas obvios en las variables")
        print("   El problema podría estar en los valores específicos o permisos")
    else:
        for problem in problems:
            print(problem)
    
    print()
    print("=== RECOMENDACIONES ===")
    print()
    print("1. Verificar que AZURE_OPENAI_ENDPOINT esté definida explícitamente")
    print("2. Usar la misma API version en ambos procesos")
    print("3. Verificar que la API key tenga permisos para batch operations")
    print("4. Confirmar que el endpoint sea accesible desde Azure Functions")

def test_openai_connection():
    """
    Intenta conectar con OpenAI usando las variables actuales
    """
    print()
    print("=== PRUEBA DE CONEXIÓN ===")
    print()
    
    try:
        from openai import AzureOpenAI
        
        # Configuración como PoolingProcess
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
        
        if not api_key or not endpoint:
            print("❌ No se puede probar conexión: faltan credenciales")
            return
        
        print(f"Probando conexión con:")
        print(f"  Endpoint: {endpoint}")
        print(f"  API Version: {api_version}")
        print(f"  API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 10 else 'corta'}")
        print()
        
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        
        # Intentar listar batches
        print("Intentando listar batches...")
        batches = client.batches.list(limit=5)
        print(f"✅ Conexión exitosa! Encontrados {len(batches.data)} batches")
        
        for batch in batches.data:
            print(f"  - {batch.id}: {batch.status}")
            
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")
        if "401" in str(e):
            print("   → Error 401: Problema de autenticación (API key inválida o sin permisos)")
        elif "404" in str(e):
            print("   → Error 404: Endpoint incorrecto o recurso no encontrado")
        elif "403" in str(e):
            print("   → Error 403: Sin permisos para esta operación")

if __name__ == "__main__":
    analyze_configuration_differences()
    test_openai_connection()