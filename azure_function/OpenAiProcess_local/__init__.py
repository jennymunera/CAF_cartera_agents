import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import openai
import sys
import tempfile
from pathlib import Path
import os.path
from os import path

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from document_intelligence_processor import DocumentIntelligenceProcessor
from chunking_processor import ChunkingProcessor
from openai_processor import OpenAIProcessor


def main(msg: func.ServiceBusMessage) -> None:
    """
    Azure Function con Service Bus trigger para procesamiento de documentos.
    
    Estructura del mensaje esperado:
    {
        "projectName": "nombre_del_proyecto",
        "requestId": "uuid-unico",
        "timestamp": "2024-01-15T10:30:00Z",
        "documents": ["doc1.pdf", "doc2.pdf"],  # Opcional, si no se especifica procesa todos
        "processingSteps": ["DI", "chunking", "openai"]  # Opcional, por defecto todos
    }
    """
    
    logging.info('🚀 Azure Function OpenAiProcess_local iniciada')
    # Asegurar carga de variables desde local.settings.json cuando se ejecuta localmente
    _load_local_settings_if_available()
    
    try:
        # Decodificar mensaje del Service Bus
        message_body = msg.get_body().decode('utf-8')
        message_data = json.loads(message_body)
        
        logging.info(f"📨 Mensaje recibido: {message_data}")
        
        # Validar estructura del mensaje
        project_name = message_data.get('projectName')
        request_id = message_data.get('requestId', 'unknown')
        
        if not project_name:
            raise ValueError("El campo 'projectName' es requerido en el mensaje")
        
        logging.info(f"🔄 Procesando proyecto: {project_name} (Request ID: {request_id})")
        
        # Configurar procesadores
        doc_processor = setup_document_intelligence()
        chunking_processor = setup_chunking_processor()
        openai_processor = setup_azure_openai()
        
        # Configurar cliente de Blob Storage con múltiples estrategias
        blob_service_client = _get_blob_service_client()
        
        # Obtener pasos de procesamiento
        processing_steps = message_data.get('processingSteps', ['DI', 'chunking', 'openai'])
        
        # Procesar según los pasos especificados
        results = {}
        
        if 'DI' in processing_steps:
            logging.info("📄 ETAPA 1: Procesamiento con Document Intelligence")
            di_result = process_document_intelligence(
                doc_processor, blob_service_client, project_name, message_data.get('documents')
            )
            results['document_intelligence'] = di_result
        
        if 'chunking' in processing_steps:
            logging.info("📝 ETAPA 2: Procesamiento de Chunking")
            chunking_result = process_chunking(
                chunking_processor, blob_service_client, project_name
            )
            results['chunking'] = chunking_result
        
        if 'openai' in processing_steps:
            logging.info("🤖 ETAPA 3: Procesamiento con Azure OpenAI")
            openai_result = process_openai(
                openai_processor, blob_service_client, project_name
            )
            results['openai'] = openai_result
        
        # Guardar resumen final
        save_processing_summary(blob_service_client, project_name, request_id, results)
        
        logging.info(f"✅ Proyecto {project_name} procesado exitosamente")
        
    except Exception as e:
        logging.error(f"❌ Error procesando mensaje: {str(e)}")
        # En un entorno de producción, aquí podrías enviar el mensaje a una cola de errores
        raise


def setup_document_intelligence() -> DocumentIntelligenceProcessor:
    """Configurar procesador de Document Intelligence."""
    # En entorno Azure Functions, el filesystem es read-only excepto /tmp.
    # Usar rutas efímeras seguras para evitar errores (no se usan para persistencia real).
    tmp_input = "/tmp/input_docs"
    tmp_output = "/tmp/output_docs"
    return DocumentIntelligenceProcessor(
        endpoint=os.environ['AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'],
        api_key=os.environ['AZURE_DOCUMENT_INTELLIGENCE_KEY'],
        input_dir=tmp_input,
        output_dir=tmp_output,
        auto_chunk=False
    )


def setup_chunking_processor() -> ChunkingProcessor:
    """Configurar procesador de chunking."""
    # Alinear con main.py
    return ChunkingProcessor(
        max_tokens=100000,
        overlap_tokens=512,
        model_name="gpt-4",
        generate_jsonl=False
    )


def setup_azure_openai() -> OpenAIProcessor:
    """Configurar procesador de Azure OpenAI."""
    # La implementación compartida lee config desde variables de entorno
    return OpenAIProcessor()


def _blob_exists(blob_service: BlobServiceClient, container: str, blob_name: str) -> bool:
    try:
        client = blob_service.get_blob_client(container=container, blob=blob_name)
        return client.exists()
    except Exception:
        return False


def _get_blob_service_client() -> BlobServiceClient:
    """Obtiene un BlobServiceClient usando la mejor fuente disponible.

    Prioridad:
      1) AZURE_STORAGE_CONNECTION_STRING
      2) AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY
      3) AzureWebJobsStorage (de local.settings.json o App Settings)
    """
    # 1) Connection string explícita
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if conn:
        logging.info("Usando AZURE_STORAGE_CONNECTION_STRING para BlobServiceClient")
        return BlobServiceClient.from_connection_string(conn)

    # 2) Account + Key
    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    key = os.getenv("AZURE_STORAGE_KEY")
    if account and key:
        logging.info("Usando AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY para BlobServiceClient")
        return BlobServiceClient(
            account_url=f"https://{account}.blob.core.windows.net",
            credential=key
        )

    # 3) AzureWebJobsStorage (usado por Functions host)
    webjobs = os.getenv("AzureWebJobsStorage")
    if webjobs:
        logging.info("Usando AzureWebJobsStorage para BlobServiceClient")
        return BlobServiceClient.from_connection_string(webjobs)

    raise KeyError(
        "No se encontró configuración de Storage. Defina AZURE_STORAGE_CONNECTION_STRING o "
        "AZURE_STORAGE_ACCOUNT/AZURE_STORAGE_KEY o AzureWebJobsStorage en local.settings.json"
    )


def _load_local_settings_if_available() -> None:
    """Carga variables desde azure_function/local.settings.json si existen y no están en el entorno.

    Esto permite asegurar que los valores locales se apliquen cuando se usa `func start`.
    No sobrescribe variables ya definidas en el entorno.
    """
    try:
        # Ruta esperada relativa a este archivo: ../local.settings.json
        base_dir = path.abspath(path.join(path.dirname(__file__), '..'))
        candidates = [
            path.join(base_dir, 'local.settings.json'),
            path.join(os.getcwd(), 'local.settings.json')
        ]
        settings_path = next((p for p in candidates if path.isfile(p)), None)
        if not settings_path:
            return
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        values = data.get('Values', {})
        applied = []
        for k, v in values.items():
            # Functions host gestiona AzureWebJobsStorage; aún así, solo rellenamos ausentes
            if k not in os.environ:
                os.environ[k] = str(v)
                applied.append(k)
        if applied:
            logging.info(f"Variables cargadas desde local.settings.json: {', '.join(applied)}")
    except Exception as e:
        logging.debug(f"No se pudo cargar local.settings.json: {e}")


def _concatenate_llm_outputs_for_area(
    blob_client: BlobServiceClient,
    container_name: str,
    project_name: str,
    area: str,
    results_base: str
) -> Optional[str]:
    """Concatena archivos JSON de un área (Auditoria/Productos/Desembolsos) y sube un JSON final a results/.

    Retorna la ruta del blob destino si se generó, o None si no hay archivos.
    """
    try:
        area_dir = f"{results_base}{area}/"
        container_client = blob_client.get_container_client(container_name)
        blobs = [b for b in container_client.list_blobs(name_starts_with=area_dir) if b.name.endswith('.json')]

        if not blobs:
            logging.warning(f"⚠️ No se encontraron archivos en {area_dir}")
            return None

        # Filtrado por patrones por área
        def include_filename(fn: str) -> bool:
            if area == 'Auditoria':
                return fn.endswith('_auditoria.json')
            if area == 'Productos':
                return fn.endswith('_productos.json') or ('_producto_' in fn and fn.endswith('.json'))
            if area == 'Desembolsos':
                return fn.endswith('_desembolsos.json') or ('_desembolso_' in fn and fn.endswith('.json'))
            return False

        selected = []
        for b in blobs:
            fname = os.path.basename(b.name)
            if include_filename(fname):
                selected.append((fname, b.name))

        if not selected:
            logging.warning(f"⚠️ No se encontraron archivos válidos para {area} en {area_dir}")
            return None

        # Construir JSON concatenado
        meta = {
            "project_name": project_name,
            "concatenated_at": datetime.now().isoformat(),
            "total_files": len(selected),
            "processor_version": "1.0.0"
        }

        key = {
            'Auditoria': 'auditoria_results',
            'Productos': 'productos_results',
            'Desembolsos': 'desembolsos_results'
        }[area]

        concatenated = {
            "metadata": meta,
            key: []
        }

        for fname, blob_name in sorted(selected):
            try:
                blob_cli = blob_client.get_blob_client(container=container_name, blob=blob_name)
                data = json.loads(blob_cli.download_blob().readall())

                # Derivar document_name según sufijo por área
                if area == 'Auditoria':
                    document_name = fname.replace('_auditoria.json', '')
                elif area == 'Productos':
                    document_name = fname.replace('_productos.json', '')
                else:  # Desembolsos
                    document_name = fname.replace('_desembolsos.json', '')

                entry = {
                    "source_file": fname,
                    "document_name": document_name,
                    "data": data
                }
                concatenated[key].append(entry)
            except Exception as e:
                logging.error(f"❌ Error leyendo {blob_name}: {e}")
                continue

        # Subir archivo concatenado a results/
        out_name = {
            'Auditoria': 'auditoria.json',
            'Productos': 'productos.json',
            'Desembolsos': 'desembolsos.json'
        }[area]
        dest_blob = f"basedocuments/{project_name}/results/{out_name}"
        dest_cli = blob_client.get_blob_client(container=container_name, blob=dest_blob)
        dest_cli.upload_blob(json.dumps(concatenated, indent=2, ensure_ascii=False), overwrite=True)

        logging.info(f"✅ Concatenación {area} subida a: {dest_blob} ({len(concatenated[key])} archivos)")
        return dest_blob

    except Exception as e:
        logging.error(f"❌ Error concatenando resultados de {area}: {e}")
        return None


def _analyze_document_bytes(processor: DocumentIntelligenceProcessor, data: bytes, filename: str) -> Dict[str, Any]:
    """Escribe bytes a un archivo temporal y usa el procesador local para analizarlo."""
    # Crear archivo temporal con misma extensión
    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        result = processor.process_single_document(tmp_path)
        return result
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def process_document_intelligence(
    processor: DocumentIntelligenceProcessor,
    blob_client: BlobServiceClient,
    project_name: str,
    specific_documents: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Procesar documentos con Document Intelligence desde Blob Storage."""
    
    container_name = "caf-documents"
    raw_path = f"basedocuments/{project_name}/raw/"
    processed_path = f"basedocuments/{project_name}/processed/DI/"
    
    # Listar documentos en la carpeta raw
    container_client = blob_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=raw_path)
    
    processed_count = 0
    skipped_count = 0
    errors = []
    
    supported_exts = ('.pdf', '.docx', '.doc', '.xlsx', '.xls')
    required_prefixes = ['INI', 'IXP', 'DEC', 'ROP', 'IFS']
    chunks_path = f"basedocuments/{project_name}/processed/chunks/"
    for blob in blobs:
        document_name = os.path.basename(blob.name)
        if not document_name.lower().endswith(supported_exts):
            continue
        # Filtrar por prefijos requeridos (como en main.py)
        doc_upper = document_name.upper()
        if not any(doc_upper.startswith(prefix) for prefix in required_prefixes):
            # No coincide con prefijos requeridos: saltar
            skipped_count += 1
            logging.info(f"⏭️ Documento sin prefijo requerido, saltando: {document_name}")
            continue

        # Si se especificaron documentos específicos, filtrar
        if specific_documents and document_name not in specific_documents:
            continue

        try:
            # Saltar si ya existe el resultado DI
            result_name = f"{os.path.splitext(document_name)[0]}.json"
            result_blob_name = f"{processed_path}{result_name}"
            if _blob_exists(blob_client, container_name, result_blob_name):
                skipped_count += 1
                logging.info(f"⏭️ Ya existe DI para {document_name}, saltando")
                continue

            # Saltar si ya existen chunks para este documento
            doc_stem = os.path.splitext(document_name)[0]
            chunk_prefix = f"{chunks_path}{doc_stem}_chunk_"
            chunk_exists = any(True for _ in container_client.list_blobs(name_starts_with=chunk_prefix))
            if chunk_exists:
                skipped_count += 1
                logging.info(f"⏭️ Documento ya chunkeado, saltando DI: {document_name}")
                continue

            logging.info(f"📄 Procesando documento: {document_name}")
            # Descargar blob
            blob_client_doc = blob_client.get_blob_client(
                container=container_name, blob=blob.name
            )
            blob_data = blob_client_doc.download_blob().readall()

            # Procesar con Document Intelligence (bytes → temp file → process)
            result = _analyze_document_bytes(processor, blob_data, document_name)
            # Normalizar metadata y filename con el nombre real del documento
            result['filename'] = document_name  # evitar nombres de archivo temporales
            result.setdefault('metadata', {})
            result['metadata']['project_name'] = project_name
            result['metadata']['original_filename'] = document_name

            # Guardar resultado en processed/DI/
            result_blob_client = blob_client.get_blob_client(
                container=container_name, blob=result_blob_name
            )
            result_blob_client.upload_blob(
                json.dumps(result, indent=2, ensure_ascii=False),
                overwrite=True
            )

            processed_count += 1
            logging.info(f"✅ Documento {document_name} procesado y guardado")

        except Exception as e:
            error_msg = f"Error procesando {document_name}: {str(e)}"
            logging.error(error_msg)
            errors.append(error_msg)
    
    return {
        "processed_documents": processed_count,
        "skipped_documents": skipped_count,
        "errors": errors,
        "timestamp": datetime.now().isoformat()
    }


def process_chunking(
    processor: ChunkingProcessor,
    blob_client: BlobServiceClient,
    project_name: str
) -> Dict[str, Any]:
    """Procesar chunking desde Blob Storage."""
    
    container_name = "caf-documents"
    di_path = f"basedocuments/{project_name}/processed/DI/"
    chunks_path = f"basedocuments/{project_name}/processed/chunks/"
    
    container_client = blob_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=di_path)
    
    processed_count = 0
    documents_chunked = 0
    documents_no_chunking = 0
    total_chunks_created = 0
    errors = []
    
    for blob in blobs:
        if blob.name.endswith('.json'):
            try:
                # Descargar resultado de DI
                blob_client_doc = blob_client.get_blob_client(
                    container=container_name, blob=blob.name
                )
                di_result = json.loads(blob_client_doc.download_blob().readall())
                
                # Procesar chunking
                content = di_result.get('content', '')
                if not content:
                    processed_count += 1
                    documents_no_chunking += 1
                    continue

                chunks_result = processor.process_document_content(content, project_name)

                # Guardar chunks individuales si requiere
                document_name = Path(di_result.get('filename', os.path.basename(blob.name))).stem

                if chunks_result and chunks_result.get('requires_chunking') and 'chunks' in chunks_result:
                    for chunk in chunks_result['chunks']:
                        chunk_index = int(chunk.get('index', 0))
                        chunk_name = f"{document_name}_chunk_{chunk_index:03d}.json"
                        chunk_blob_name = f"{chunks_path}{chunk_name}"

                        # Normalizar estructura similar a main.py
                        chunk_data = {
                            'document_name': document_name,
                            'chunk_index': chunk_index,
                            'content': chunk.get('content', ''),
                            'tokens': chunk.get('tokens', 0),
                            'sections_range': chunk.get('sections_range', ''),
                            'metadata': {
                                'created_at': datetime.now().isoformat(),
                                'project_name': project_name,
                                'total_chunks': len(chunks_result.get('chunks', []))
                            }
                        }

                        chunk_blob_client = blob_client.get_blob_client(
                            container=container_name, blob=chunk_blob_name
                        )
                        chunk_blob_client.upload_blob(
                            json.dumps(chunk_data, indent=2, ensure_ascii=False),
                            overwrite=True
                        )
                        total_chunks_created += 1

                    documents_chunked += 1

                    # Eliminar el archivo DI original después de chunking exitoso
                    try:
                        di_blob_client = blob_client.get_blob_client(
                            container=container_name, blob=blob.name
                        )
                        di_blob_client.delete_blob()
                        logging.info(f"🗑️ DI eliminado tras chunking: {os.path.basename(blob.name)}")
                    except Exception as del_err:
                        logging.warning(f"⚠️ No se pudo eliminar DI {blob.name}: {del_err}")
                else:
                    documents_no_chunking += 1
                
                processed_count += 1
                
            except Exception as e:
                error_msg = f"Error en chunking {blob.name}: {str(e)}"
                logging.error(error_msg)
                errors.append(error_msg)
    
    return {
        "processed_documents": processed_count,
        "documents_chunked": documents_chunked,
        "documents_no_chunking": documents_no_chunking,
        "total_chunks_created": total_chunks_created,
        "errors": errors,
        "timestamp": datetime.now().isoformat()
    }


def process_openai(
    processor: OpenAIProcessor,
    blob_client: BlobServiceClient,
    project_name: str
) -> Dict[str, Any]:
    """Procesar con Azure OpenAI leyendo de Blob y subiendo resultados a Blob.

    Reglas:
      - Cada prompt procesa TODOS los documentos que cumplan sus prefijos, estén en DI o en chunks.
      - Prompt 1 (Auditoría): prefijo IXP
      - Prompt 2 (Productos): prefijos ROP, INI, DEC, IFS
      - Prompt 3 (Desembolsos): prefijos ROP, INI, DEC
    """

    container_name = "caf-documents"
    chunks_path = f"basedocuments/{project_name}/processed/chunks/"
    di_path = f"basedocuments/{project_name}/processed/DI/"
    results_base = f"basedocuments/{project_name}/results/LLM_output/"

    container_client = blob_client.get_container_client(container_name)

    chunk_blobs = [b for b in container_client.list_blobs(name_starts_with=chunks_path) if b.name.endswith('.json')]
    di_blobs = [b for b in container_client.list_blobs(name_starts_with=di_path) if b.name.endswith('.json')]

    def _prefix_from_name(name: str) -> str:
        base = os.path.basename(name).replace('.json', '')
        # If chunk, take base before _chunk_
        if '_chunk_' in base:
            base = base.split('_chunk_')[0]
        # Split by '-' if present, else first 3 chars
        return base.split('-')[0].upper() if '-' in base else base[:3].upper()

    total_units = 0
    errors: List[str] = []
    counts = {
        'prompt1_auditoria': 0,
        'prompt2_productos': 0,
        'prompt3_desembolsos': 0
    }

    # Helper: subida a blob
    def _upload_json(dest_rel_path: str, payload: Any):
        out_cli = blob_client.get_blob_client(container=container_name, blob=dest_rel_path)
        out_cli.upload_blob(json.dumps(payload, indent=2, ensure_ascii=False), overwrite=True)

    # 1) DI -> todos los prompts según prefijo
    for b in di_blobs:
        try:
            blob_cli = blob_client.get_blob_client(container=container_name, blob=b.name)
            data = json.loads(blob_cli.download_blob().readall())
            filename = data.get('filename', Path(b.name).name.replace('.json', ''))
            prefix = _prefix_from_name(filename)

            document_content = {
                'filename': filename,
                'content': data.get('content', ''),
                'project_name': project_name,
                'pages': data.get('metadata', {}).get('pages')
            }

            # Auditoría (IXP)
            if prefix == 'IXP':
                try:
                    r1 = processor.process_document_with_prompt1(document_content)
                    if r1 and r1.get('parsed_json'):
                        counts['prompt1_auditoria'] += 1
                        name = os.path.basename(r1.get('json_saved_path', f"{filename}_auditoria.json"))
                        _upload_json(f"{results_base}Auditoria/{name}", r1['parsed_json'])
                except Exception as e:
                    errors.append(f"Prompt1 (DI) {b.name}: {e}")

            # Productos (ROP/INI/DEC/IFS)
            if prefix in ['ROP', 'INI', 'DEC', 'IFS']:
                try:
                    r2 = processor.process_document_with_prompt2(document_content)
                    if r2:
                        if r2.get('all_products'):
                            for pr in r2['all_products']:
                                if pr.get('parsed_json'):
                                    counts['prompt2_productos'] += 1
                                    name = os.path.basename(pr.get('json_output_path', 'producto.json'))
                                    _upload_json(f"{results_base}Productos/{name}", pr['parsed_json'])
                        elif r2.get('parsed_json'):
                            counts['prompt2_productos'] += 1
                            name = os.path.basename(r2.get('json_output_path', 'productos.json'))
                            _upload_json(f"{results_base}Productos/{name}", r2['parsed_json'])
                except Exception as e:
                    errors.append(f"Prompt2 (DI) {b.name}: {e}")

            # Desembolsos (ROP/INI/DEC)
            if prefix in ['ROP', 'INI', 'DEC']:
                try:
                    r3 = processor.process_document_with_prompt3(
                        document_content,
                        document_name=filename,
                        chunk_index=None,
                    )
                    if r3:
                        if r3.get('all_disbursements'):
                            for dr in r3['all_disbursements']:
                                if dr.get('parsed_json'):
                                    counts['prompt3_desembolsos'] += 1
                                    name = os.path.basename(dr.get('json_output_path', 'desembolso.json'))
                                    _upload_json(f"{results_base}Desembolsos/{name}", dr['parsed_json'])
                        elif r3.get('parsed_json'):
                            counts['prompt3_desembolsos'] += 1
                            name = os.path.basename(r3.get('json_output_path', 'desembolsos.json'))
                            _upload_json(f"{results_base}Desembolsos/{name}", r3['parsed_json'])
                except Exception as e:
                    errors.append(f"Prompt3 (DI) {b.name}: {e}")

            total_units += 1
        except Exception as e:
            errors.append(f"Error DI {b.name}: {e}")

    # 2) Chunks -> todos los prompts según prefijo
    for b in chunk_blobs:
        try:
            blob_cli = blob_client.get_blob_client(container=container_name, blob=b.name)
            data = json.loads(blob_cli.download_blob().readall())
            base_doc = data.get('document_name') or Path(b.name).name.split('_chunk_')[0]
            prefix = _prefix_from_name(base_doc)

            document_content = {
                'document_name': base_doc,
                'chunk_index': data.get('chunk_index'),
                'content': data.get('content', ''),
                'project_name': project_name,
                'pages': data.get('metadata', {}).get('pages')
            }

            # Auditoría (IXP)
            if prefix == 'IXP':
                try:
                    r1 = processor.process_document_with_prompt1(document_content)
                    if r1 and r1.get('parsed_json'):
                        counts['prompt1_auditoria'] += 1
                        name = os.path.basename(r1.get('json_saved_path', f"{base_doc}_auditoria.json"))
                        _upload_json(f"{results_base}Auditoria/{name}", r1['parsed_json'])
                except Exception as e:
                    errors.append(f"Prompt1 (Chunk) {b.name}: {e}")

            # Productos (ROP/INI/DEC/IFS)
            if prefix in ['ROP', 'INI', 'DEC', 'IFS']:
                try:
                    r2 = processor.process_document_with_prompt2(document_content)
                    if r2:
                        if r2.get('all_products'):
                            for pr in r2['all_products']:
                                if pr.get('parsed_json'):
                                    counts['prompt2_productos'] += 1
                                    name = os.path.basename(pr.get('json_output_path', 'producto.json'))
                                    _upload_json(f"{results_base}Productos/{name}", pr['parsed_json'])
                        elif r2.get('parsed_json'):
                            counts['prompt2_productos'] += 1
                            name = os.path.basename(r2.get('json_output_path', 'productos.json'))
                            _upload_json(f"{results_base}Productos/{name}", r2['parsed_json'])
                except Exception as e:
                    errors.append(f"Prompt2 (Chunk) {b.name}: {e}")

            # Desembolsos (ROP/INI/DEC)
            if prefix in ['ROP', 'INI', 'DEC']:
                try:
                    r3 = processor.process_document_with_prompt3(
                        document_content,
                        document_name=base_doc,
                        chunk_index=data.get('chunk_index'),
                    )
                    if r3:
                        if r3.get('all_disbursements'):
                            for dr in r3['all_disbursements']:
                                if dr.get('parsed_json'):
                                    counts['prompt3_desembolsos'] += 1
                                    name = os.path.basename(dr.get('json_output_path', 'desembolso.json'))
                                    _upload_json(f"{results_base}Desembolsos/{name}", dr['parsed_json'])
                        elif r3.get('parsed_json'):
                            counts['prompt3_desembolsos'] += 1
                            name = os.path.basename(r3.get('json_output_path', 'desembolsos.json'))
                            _upload_json(f"{results_base}Desembolsos/{name}", r3['parsed_json'])
                except Exception as e:
                    errors.append(f"Prompt3 (Chunk) {b.name}: {e}")

            total_units += 1
        except Exception as e:
            errors.append(f"Error Chunk {b.name}: {e}")

    sources = []
    if di_blobs:
        sources.append('DI')
    if chunk_blobs:
        sources.append('chunks')

    summary = {
        'project_name': project_name,
        'total_units': total_units,
        'processed_sources': ' & '.join(sources) if sources else 'none',
        'counts': counts,
        'errors': errors,
        'timestamp': datetime.now().isoformat()
    }

    # Guardar resumen en Blob
    summary_blob_name = f"basedocuments/{project_name}/results/processing_summary.json"
    summary_blob_client = blob_client.get_blob_client(
        container=container_name, blob=summary_blob_name
    )
    summary_blob_client.upload_blob(
        json.dumps(summary, indent=2, ensure_ascii=False),
        overwrite=True
    )

    # Concatenar resultados por área en results/
    try:
        _concatenate_llm_outputs_for_area(blob_client, container_name, project_name, 'Auditoria', results_base)
        _concatenate_llm_outputs_for_area(blob_client, container_name, project_name, 'Productos', results_base)
        _concatenate_llm_outputs_for_area(blob_client, container_name, project_name, 'Desembolsos', results_base)
    except Exception as e:
        errors.append(f"Concatenation error: {e}")

    return summary


def save_processing_summary(
    blob_client: BlobServiceClient,
    project_name: str,
    request_id: str,
    results: Dict[str, Any]
) -> None:
    """Guardar resumen final del procesamiento."""
    
    summary = {
        "project_name": project_name,
        "request_id": request_id,
        "processing_timestamp": datetime.now().isoformat(),
        "results": results,
        "status": "completed"
    }
    
    container_name = "caf-documents"
    summary_blob_name = f"basedocuments/{project_name}/results/final_summary_{request_id}.json"
    
    summary_blob_client = blob_client.get_blob_client(
        container=container_name, blob=summary_blob_name
    )
    summary_blob_client.upload_blob(
        json.dumps(summary, indent=2, ensure_ascii=False),
        overwrite=True
    )
    
    logging.info(f"📊 Resumen final guardado: {summary_blob_name}")
