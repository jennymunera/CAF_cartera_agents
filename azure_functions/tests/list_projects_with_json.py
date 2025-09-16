#!/usr/bin/env python3
"""
Script para listar proyectos que tienen JSON finales disponibles para generar CSVs.
"""

import os
import sys
import json
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

def list_projects_with_json():
    """
    Listar todos los proyectos que tienen JSON finales disponibles.
    """
    print("🔍 Buscando proyectos con JSON finales...")
    print("=" * 50)
    
    try:
        from shared_code.utils.blob_storage_client import BlobStorageClient
        
        # Inicializar cliente de blob storage
        blob_client = BlobStorageClient()
        
        # Obtener lista de todos los proyectos
        all_projects = blob_client.list_projects()
        print(f"📂 Total de proyectos encontrados: {len(all_projects)}")
        print()
        
        projects_with_json = []
        
        for project in all_projects:
            print(f"🔍 Verificando proyecto: {project}")
            
            # Verificar si tiene carpeta results
            results_path = f"basedocuments/{project}/results"
            
            try:
                # Listar archivos en la carpeta results
                blobs = blob_client.list_blobs_with_prefix(prefix=results_path)
                
                if not blobs:
                    print(f"   ⚠️  Sin carpeta results")
                    continue
                
                # Buscar archivos JSON finales
                json_files = []
                for blob in blobs:
                    blob_name = blob['name']
                    if blob_name.endswith('.json'):
                        # Extraer solo el nombre del archivo
                        file_name = blob_name.split('/')[-1]
                        json_files.append(file_name)
                
                # Verificar archivos específicos
                target_files = ['auditoria.json', 'productos.json', 'desembolsos.json']
                found_files = [f for f in target_files if f in json_files]
                
                if found_files:
                    projects_with_json.append({
                        'name': project,
                        'json_files': found_files,
                        'total_json': len(json_files)
                    })
                    
                    print(f"   ✅ {len(found_files)}/3 JSON finales encontrados: {', '.join(found_files)}")
                    if len(json_files) > len(found_files):
                        print(f"   📄 Total archivos JSON: {len(json_files)}")
                else:
                    print(f"   ❌ Sin JSON finales (encontrados: {len(json_files)} otros JSON)")
                    
            except Exception as e:
                print(f"   ❌ Error verificando: {str(e)}")
            
            print()
        
        # Resumen final
        print("=" * 50)
        print(f"📊 RESUMEN:")
        print(f"   Total proyectos: {len(all_projects)}")
        print(f"   Con JSON finales: {len(projects_with_json)}")
        print()
        
        if projects_with_json:
            print("🎯 PROYECTOS LISTOS PARA GENERAR CSV:")
            print()
            
            for i, project in enumerate(projects_with_json, 1):
                print(f"{i:2d}. {project['name']}")
                print(f"    📄 Archivos: {', '.join(project['json_files'])}")
                print(f"    📊 Completitud: {len(project['json_files'])}/3 archivos")
                
                # Mostrar comando para generar CSV
                print(f"    🚀 Comando: python quick_csv_test.py {project['name']}")
                print()
            
            # Sugerir el mejor proyecto para testing
            complete_projects = [p for p in projects_with_json if len(p['json_files']) == 3]
            if complete_projects:
                best_project = complete_projects[0]['name']
                print(f"💡 RECOMENDADO PARA TESTING: {best_project}")
                print(f"   python quick_csv_test.py {best_project}")
        else:
            print("⚠️  No se encontraron proyectos con JSON finales")
            print("\n💡 Para generar JSON finales:")
            print("   1. Ejecuta un batch completo con OpenAiProcess")
            print("   2. Espera a que PoolingProcess procese los resultados")
            print("   3. Los JSON finales aparecerán en basedocuments/{proyecto}/results/")
        
        return projects_with_json
        
    except Exception as e:
        print(f"❌ Error listando proyectos: {str(e)}")
        return []

def main():
    """
    Función principal.
    """
    print("📋 List Projects with JSON - CAF Cartera Agents")
    print()
    
    projects = list_projects_with_json()
    
    # Si hay argumentos, mostrar detalles de un proyecto específico
    if len(sys.argv) > 1:
        target_project = sys.argv[1]
        
        matching_project = next((p for p in projects if p['name'] == target_project), None)
        
        if matching_project:
            print("=" * 50)
            print(f"📋 DETALLES DEL PROYECTO: {target_project}")
            print(f"📄 JSON finales: {', '.join(matching_project['json_files'])}")
            print(f"📊 Completitud: {len(matching_project['json_files'])}/3")
            print()
            print(f"🚀 Para generar CSVs:")
            print(f"   python quick_csv_test.py {target_project}")
        else:
            print(f"\n❌ Proyecto '{target_project}' no encontrado o sin JSON finales")

if __name__ == "__main__":
    main()