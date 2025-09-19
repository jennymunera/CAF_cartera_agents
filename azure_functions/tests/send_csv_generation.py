#!/usr/bin/env python3
"""
Script para probar la generación de CSVs directamente desde JSON finales existentes.
Este script invoca directamente FinalCsvProcess sin pasar por todo el proceso de PoolingProcess.
"""

import os
import sys
import json
import requests
from pathlib import Path

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

def test_csv_generation_local(project_name: str = None):
    """
    Probar generación de CSV localmente usando la función directamente.
    Si no se especifica proyecto, procesa TODOS los proyectos disponibles.
    
    Args:
        project_name: Nombre del proyecto específico o None para todos
    """
    if project_name:
        print(f"🧪 Probando generación CSV local para proyecto: {project_name}")
        projects_to_process = [project_name]
    else:
        print("🧪 Probando generación CSV consolidado para TODOS los proyectos")
        # Obtener todos los proyectos con JSON finales
        available_projects = list_available_projects()
        if not available_projects:
            print("❌ No se encontraron proyectos con JSON finales")
            return False
        projects_to_process = available_projects
        print(f"📂 Proyectos encontrados: {len(projects_to_process)}")
    
    try:
        # Importar la función de procesamiento CSV
        from shared_code.utils.processor_csv import process_ndjson_or_json_to_csv
        
        # Cargar configuración
        settings = load_local_settings()
        connection_string = settings.get('AZURE_STORAGE_OUTPUT_CONNECTION_STRING')
        container_name = settings.get('CONTAINER_OUTPUT_NAME', 'caf-documents')
        
        if not connection_string:
            print("❌ AZURE_STORAGE_OUTPUT_CONNECTION_STRING no configurado")
            return False
        
        # Archivos de entrada y salida
        input_files = ["auditoria.json", "productos.json", "desembolsos.json"]
        output_files = ["auditoria_cartera_consolidado.csv", "producto_cartera_consolidado.csv", "desembolso_cartera_consolidado.csv"]
        
        total_success = 0
        total_files = 0
        
        # Procesar cada tipo de archivo (auditoria, productos, desembolsos)
        for input_file, output_file in zip(input_files, output_files):
            print(f"\n📄 Procesando {input_file} de todos los proyectos -> {output_file}")
            project_success = 0
            
            for project in projects_to_process:
                input_path = f"basedocuments/{project}/results/{input_file}"
                output_path = f"outputdocuments/{output_file}"  # CSV consolidado global
                
                try:
                    result = process_ndjson_or_json_to_csv(
                        connection_string,
                        container_name,
                        input_path,
                        output_path
                    )
                    print(f"  ✅ {project}: {result} registros agregados")
                    project_success += 1
                    
                except Exception as e:
                    print(f"  ⚠️ {project}: {str(e)}")
                
                total_files += 1
            
            if project_success > 0:
                total_success += 1
                print(f"📊 {input_file}: {project_success}/{len(projects_to_process)} proyectos procesados")
        
        print(f"\n🎉 Resultado final: {total_success}/{len(input_files)} tipos de CSV consolidados generados")
        print(f"📁 CSVs consolidados disponibles en: outputdocuments/")
        return total_success > 0
        
    except Exception as e:
        print(f"❌ Error en test local: {str(e)}")
        return False

def test_csv_generation_http(project_name: str):
    """
    Probar generación de CSV via HTTP llamando a FinalCsvProcess desplegada.
    
    Args:
        project_name: Nombre del proyecto (ej: CFA009660)
    """
    print(f"🌐 Probando generación CSV via HTTP para proyecto: {project_name}")
    
    try:
        # URL de la Function desplegada
        base_url = "https://azfunc-analisis-batch-mvp-cartera-cr-a7dhbkaeeshbd3ey.eastus-01.azurewebsites.net/api/FinalCsvProcess"
        
        params = {
            "folderName": project_name
        }
        
        print(f"📡 Enviando request a: {base_url}")
        print(f"📋 Parámetros: {params}")
        
        response = requests.get(base_url, params=params, timeout=300)  # 5 minutos timeout
        
        if response.status_code == 200:
            print(f"✅ Respuesta exitosa: {response.text}")
            return True
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error en test HTTP: {str(e)}")
        return False

def list_available_projects():
    """
    Listar proyectos disponibles que tienen JSON finales.
    """
    print("📂 Buscando proyectos con JSON finales disponibles...")
    
    try:
        from shared_code.utils.blob_storage_client import BlobStorageClient
        
        blob_client = BlobStorageClient()
        projects = blob_client.list_projects()
        
        available_projects = []
        
        for project in projects:
            # Verificar si tiene archivos JSON finales
            results_path = f"basedocuments/{project}/results"
            try:
                blobs = blob_client.list_blobs_with_prefix(prefix=results_path)
                json_files = [b['name'] for b in blobs if b['name'].endswith('.json')]
                
                if any('auditoria.json' in f or 'productos.json' in f or 'desembolsos.json' in f for f in json_files):
                    available_projects.append(project)
                    print(f"✅ {project}: {len(json_files)} archivos JSON encontrados")
                    
            except Exception:
                continue
        
        if not available_projects:
            print("⚠️  No se encontraron proyectos con JSON finales")
        
        return available_projects
        
    except Exception as e:
        print(f"❌ Error listando proyectos: {str(e)}")
        return []

def main():
    """
    Función principal del test.
    """
    print("🧪 Test de Generación CSV - CAF Cartera Agents")
    print("=" * 50)
    
    # Obtener nombre del proyecto desde argumentos o usar default
    if len(sys.argv) > 1:
        project_name = sys.argv[1]
        single_project = True
    else:
        project_name = None
        single_project = False
    
    # Preguntar qué tipo de test ejecutar
    print("\n🔧 Opciones de test:")
    if single_project:
        print(f"1. Test local proyecto específico ({project_name})")
        print(f"2. Test HTTP proyecto específico ({project_name})")
        print("3. Test local TODOS los proyectos (CSV consolidado)")
        print("4. Ambos tests proyecto específico")
    else:
        print("1. Test local TODOS los proyectos (CSV consolidado)")
        print("2. Test HTTP proyecto específico (requiere nombre)")
    
    choice = input("\n📝 Selecciona una opción: ").strip()
    
    success = False
    
    if single_project:
        if choice == '1':
            print("\n" + "=" * 30)
            success = test_csv_generation_local(project_name)
        elif choice == '2':
            print("\n" + "=" * 30)
            success = test_csv_generation_http(project_name)
        elif choice == '3':
            print("\n" + "=" * 30)
            success = test_csv_generation_local(None)  # Todos los proyectos
        elif choice == '4':
            print("\n" + "=" * 30)
            success_local = test_csv_generation_local(project_name)
            print("\n" + "=" * 30)
            success_http = test_csv_generation_http(project_name)
            success = success_local and success_http
    else:
        if choice == '1':
            print("\n" + "=" * 30)
            success = test_csv_generation_local(None)  # Todos los proyectos
        elif choice == '2':
            project_name = input("\n📝 Ingresa el nombre del proyecto: ").strip()
            if project_name:
                print("\n" + "=" * 30)
                success = test_csv_generation_http(project_name)
            else:
                print("❌ Nombre de proyecto requerido")
                return
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Test completado exitosamente")
        if single_project and choice in ['1', '2', '4']:
            print(f"📁 Revisa los CSVs generados en: outputdocuments/{project_name}/")
        else:
            print("📁 Revisa los CSVs consolidados en: outputdocuments/")
    else:
        print("❌ Test falló - revisa los errores arriba")

if __name__ == "__main__":
    main()