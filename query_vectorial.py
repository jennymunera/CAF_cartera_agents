#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simple para hacer consultas directas a la base vectorial ChromaDB en Docker
"""

import chromadb

def main():
    """Función principal para hacer query directo a ChromaDB"""
    try:
        print("🔧 Conectando a ChromaDB server (Docker)...")
        
        # Inicializar cliente ChromaDB HTTP (Docker)
        client = chromadb.HttpClient(host="localhost", port=8000)
        
        # Verificar conexión
        try:
            client.heartbeat()
            print("✅ Conexión exitosa al servidor ChromaDB")
        except Exception as e:
            print(f"❌ Error: No se pudo conectar al servidor ChromaDB en Docker")
            print(f"   Detalle: {str(e)}")
            print("💡 Asegúrate de que el contenedor Docker esté corriendo: docker-compose up -d")
            return
        
        # Obtener colección
        collection_name = "rag_documents"
        try:
            collection = client.get_collection(name=collection_name)
            print(f"📚 Usando colección: {collection_name}")
        except Exception as e:
            print(f"❌ Error: No se pudo obtener la colección '{collection_name}'")
            print(f"   Detalle: {str(e)}")
            
            # Listar colecciones disponibles
            collections = client.list_collections()
            if collections:
                print("\n📋 Colecciones disponibles:")
                for col in collections:
                    print(f"   - {col.name}")
            return
        
        # Mostrar información de la colección
        count = collection.count()
        print(f"\n📊 Información de la colección '{collection_name}':")
        print(f"   Total de documentos: {count}")
        
        # Query específico
        query = "qué documentos tienes en la base documental"
        print(f"\n🔍 Ejecutando query: '{query}'")
        print("=" * 60)
        
        # Obtener algunos documentos para mostrar qué hay en la base
        print("\n📄 Documentos en la base vectorial:")
        
        # Usar get() para obtener todos los documentos
        try:
            all_docs = collection.get(
                include=["documents", "metadatas"]
            )
            
            if all_docs and all_docs['documents']:
                documents = all_docs['documents']
                metadatas = all_docs['metadatas'] if all_docs['metadatas'] else [{}] * len(documents)
                
                print(f"\n✅ Se encontraron {len(documents)} documentos en la base:\n")
                
                for i, (doc, metadata) in enumerate(zip(documents, metadatas), 1):
                    print(f"📄 Documento {i}:")
                    # Mostrar primeros 300 caracteres del documento
                    preview = doc[:300] + "..." if len(doc) > 300 else doc
                    print(f"   Contenido: {preview}")
                    
                    # Mostrar metadata si está disponible
                    if metadata:
                        print(f"   Metadata:")
                        for key, value in metadata.items():
                            print(f"     - {key}: {value}")
                    print("-" * 40)
            else:
                print("\n⚠️  No se pudieron obtener los documentos.")
                
        except Exception as e:
            print(f"\n❌ Error al obtener documentos: {str(e)}")
            print("\n💡 Esto puede deberse a problemas con la función de embeddings.")
            print("   Los documentos están en la base pero no se pueden consultar directamente.")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Iniciando consulta a la base vectorial ChromaDB (Docker)")
    print("=" * 70)
    main()
    print("\n✨ Consulta completada")