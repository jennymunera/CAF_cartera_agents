#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simple para listar colecciones en ChromaDB
"""

import chromadb

def main():
    """Función principal para listar colecciones"""
    try:
        print("🔧 Conectando a ChromaDB server (Docker)...")
        
        # Inicializar cliente ChromaDB HTTP (Docker)
        client = chromadb.HttpClient(host="localhost", port=8000)
        
        # Verificar conexión
        try:
            client.heartbeat()
            print("✅ Conexión exitosa al servidor ChromaDB")
        except Exception as e:
            print(f"❌ Error de conexión: {str(e)}")
            return
        
        # Listar colecciones
        print("\n📚 Listando colecciones disponibles...")
        collections = client.list_collections()
        
        if collections:
            print(f"\n✅ Se encontraron {len(collections)} colecciones:\n")
            
            for i, collection in enumerate(collections, 1):
                print(f"📄 Colección {i}:")
                print(f"   Nombre: {collection.name}")
                print(f"   ID: {collection.id}")
                
                # Obtener información adicional
                try:
                    count = collection.count()
                    print(f"   Documentos: {count}")
                except Exception as e:
                    print(f"   Documentos: Error al obtener count - {str(e)}")
                
                print("-" * 40)
        else:
            print("\n⚠️  No se encontraron colecciones en la base vectorial.")
            print("💡 La base vectorial está vacía. Necesitas indexar documentos primero.")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Listando colecciones en ChromaDB")
    print("=" * 50)
    main()
    print("\n✨ Consulta completada")