import json
import logging
import pandas as pd
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import io
import re



def process_ndjson_or_json_to_csv(        
    connection_string: str,
    container_name: str,
    source_json_blob: str,
    output_csv_blob: str
) -> int:
    """
    Detecta si el archivo es NDJSON o JSON estándar y lo procesa a CSV en Blob Storage,
    aplicando reglas de filtrado y columnas adicionales según el tipo de datos.
    """
    try:
        logging.info(f"Inicio de la función: process_ndjson_or_json_to_csv para {source_json_blob}.")
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        # Descargar el archivo
        json_blob_client = container_client.get_blob_client(source_json_blob)
        raw_data = json_blob_client.download_blob().readall().decode("utf-8").strip()

        # Detectar si es NDJSON o JSON estándar
        if "\n" in raw_data and not raw_data.strip().startswith("["):         
            logging.info("Formato detectado: NDJSON")
            records = []
            for line in raw_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    records.append(obj)
                except json.JSONDecodeError:
                    logging.warning(f"Línea ignorada (no es JSON válido): {line[:80]}...")
                    continue
        else:
            logging.info("Formato detectado: JSON estándar")
            json_content = json.loads(raw_data)
            if isinstance(json_content, dict):
                raise ValueError("El JSON es un objeto, no una lista. Se requiere clave para acceder a los registros.")
            elif isinstance(json_content, list):
                records = json_content
            else:
                raise ValueError("Formato JSON no reconocido.")

        # Determinar tipo de dataset según nombre de archivo
        filename_lower = source_json_blob.lower()
        is_producto = "producto" in filename_lower
        is_desembolso = "desembolso" in filename_lower
        is_auditoria = "auditoria" in filename_lower

        processed_rows = []
        for item in records:
            # --- FILTROS ---
            if is_producto:
                # descartar si descripcion_producto.value es null o vacío
                desc_val = item.get("descripcion_producto", {}).get("value") if isinstance(item.get("descripcion_producto"), dict) else None
                if not desc_val:
                    continue

            if is_desembolso:
                # al menos uno de monto_usd.value o monto_original.value debe tener valor
                monto_usd_val = item.get("monto_usd", {}).get("value") if isinstance(item.get("monto_usd"), dict) else None
                monto_orig_val = item.get("monto_original", {}).get("value") if isinstance(item.get("monto_original"), dict) else None
                if not monto_usd_val and not monto_orig_val:
                    continue

            if is_auditoria:
                # filtrar solo concepto_* que sean objetos y no terminen en _norm
                concepto_keys = [k for k in item.keys() if k.startswith("concepto_") and not k.endswith("_norm") and isinstance(item[k], dict)]
                # si todos esos tienen value vacío o null, descartar
                if not any(item[k].get("value") for k in concepto_keys):
                    continue

            # --- PROCESAMIENTO DE COLUMNAS ---
            row = {}
            for key, value in item.items():
                # Omitir codigo_CFX si es producto o auditoría
                if key.lower() == "codigo_cfx" and (is_producto or is_auditoria):
                   continue

                if key.lower() == "codigo_cfa": 
                    normalized_cfa = _normalizar_codigo_cfa(value)
                    # Validar que el código CFA no esté vacío después de normalizar
                    if not normalized_cfa or normalized_cfa.strip() == "":
                        logging.warning(f"Código CFA vacío o inválido en registro: {item}")
                        break  # Saltar este registro completo
                    row[key] = normalized_cfa
                elif isinstance(value, dict) and "value" in value:
                    # Filtrar valores None o vacíos en campos críticos
                    field_value = value["value"]
                    if field_value is None or (isinstance(field_value, str) and field_value.strip() == ""):
                        # Para campos críticos, usar valor por defecto o saltar
                        if key in ["descripcion_producto", "monto_usd", "monto_original"]:
                            continue  # No agregar el campo si está vacío
                    row[key] = field_value
                    # Para auditoría: si es concepto_* objeto y no termina en _norm, agregar columna evidence
                    if is_auditoria and key.startswith("concepto_") and not key.endswith("_norm"):
                        row[f"{key}_evidence"] = value.get("evidence")
                else:
                    # Filtrar valores None directos
                    if value is not None:
                        row[key] = value
            
            # Solo agregar la fila si tiene código CFA válido
            if "codigo_CFA" in row and row["codigo_CFA"]:
                processed_rows.append(row)
            else:
                logging.warning(f"Registro descartado por código CFA inválido: {item.get('codigo_CFA', 'N/A')}")

        # Crear DataFrame
        df_new = pd.DataFrame(processed_rows)
        
        # Validar que hay datos para procesar
        if df_new.empty:
            logging.warning(f"No hay registros válidos para procesar en {source_json_blob}")
            return 0
        
        # Logging detallado
        logging.info(f"📊 Procesamiento {source_json_blob}:")
        logging.info(f"   Registros originales: {len(records)}")
        logging.info(f"   Registros válidos: {len(processed_rows)}")
        logging.info(f"   Registros filtrados: {len(records) - len(processed_rows)}")

        # Manejar CSV existente con concatenación simple
        csv_blob_client = container_client.get_blob_client(output_csv_blob)
        try:
            existing_data = csv_blob_client.download_blob().readall()
            df_existing = pd.read_csv(io.BytesIO(existing_data))
            
            # Concatenar sin eliminar duplicados
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
            
        except Exception as e:
            logging.info(f"   CSV nuevo (no existía previamente): {len(df_new)} registros")
            df_final = df_new

        # Guardar CSV en memoria y subir
        output_stream = io.BytesIO()
        df_final.to_csv(output_stream, index=False, encoding="utf-8-sig")
        output_stream.seek(0)
        csv_blob_client.upload_blob(output_stream, overwrite=True)

        logging.info(f"✅ CSV actualizado en blob: {container_name}/{output_csv_blob} - Total: {len(df_final)} registros")
        return len(processed_rows)

    except Exception as e:
        logging.error(f"Error en process_ndjson_or_json_to_csv: {str(e)}")
        raise



def process_json_to_csv(        
    connection_string: str,
    container_name: str,
    source_json_blob: str,
    output_csv_blob: str,
    root_array_key: str    
) -> int:
    """
    Process JSON data from blob storage and append to CSV in blob storage.

    Args:
        connection_string: Azure blob storage connection string
        container_name: Container name in blob storage
        source_json_blob: Path to the JSON file in blob storage
        output_csv_blob: CSV file name in blob storage
        root_array_key: Key in JSON that contains the list of records (e.g., "productos_results")       
    """
    try:
        logging.info(f"Inicio de la función: process_json_to_csv para {root_array_key}.")
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        json_blob_client = container_client.get_blob_client(source_json_blob)
        json_data = json_blob_client.download_blob().readall()
        json_content = json.loads(json_data.decode("utf-8"))

        logging.info(f"Se obtuvo el JSON desde {source_json_blob}.")

        csv_blob_client = container_client.get_blob_client(output_csv_blob)
        records = json_content.get(root_array_key, [])

        processed_rows = []
        for item in records:
            data = item.get("data", {})
            row = {}

            for key, value in data.items():
                if isinstance(value, dict) and "value" in value:
                    row[key] = value["value"]
                else:
                    row[key] = value

            processed_rows.append(row)

        df_new = pd.DataFrame(processed_rows)

        try:
            existing_data = csv_blob_client.download_blob().readall()
            df_existing = pd.read_csv(io.BytesIO(existing_data))

         
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        except Exception:
            df_final = df_new

        output_stream = io.BytesIO()
        df_final.to_csv(output_stream, index=False, encoding="utf-8-sig")
        output_stream.seek(0)

        csv_blob_client.upload_blob(output_stream, overwrite=True)
        logging.info(f"CSV actualizado en blob: {container_name}/{output_csv_blob}")

        return len(processed_rows)

    except Exception as e:
        logging.error(f"Error en process_json_to_csv: {str(e)}")
        raise



def _normalizar_codigo_cfa(valor):
    """
    Normaliza el código CFA al formato 'CFA' + 6 dígitos con ceros a la izquierda.
    Ejemplos:
        'CFA 9757' -> 'CFA009757'
        '9757'     -> 'CFA009757'
        'CFA009757'-> 'CFA009757'
    """
    if not valor:
        return valor

    # Si viene como dict con 'value', tomarlo
    if isinstance(valor, dict) and "value" in valor:
        valor = valor["value"]

    if not isinstance(valor, str):
        valor = str(valor)

    # Extraer solo dígitos
    digitos = re.sub(r"\D", "", valor)

    if not digitos:
        return valor

    # Rellenar con ceros a la izquierda hasta 6 dígitos
    digitos = digitos.zfill(6)

    return f"CFA{digitos}"
