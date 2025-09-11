#!/usr/bin/env python3
"""
Envia un mensaje simple a Service Bus para disparar el procesamiento
de todos los archivos en 'raw' para un proyecto dado.

Uso básico:
  python tests/send_service_bus_message.py -p <projectName>

Opcional:
  -s "DI,chunking,openai"  # pasos a ejecutar
  -q analysis-event-queue  # nombre de la cola
  -c "Endpoint=..."        # connection string explícito
  -d file1.pdf file2.pdf   # lista de documentos (si se omite, procesa todos)

El script intenta obtener la cadena de conexión en este orden:
  1) Argumento --connection
  2) Variable de entorno ServiceBusConnectionString
  3) azure_function/local.settings.json -> Values.ServiceBusConnectionString
"""

import argparse
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from azure.servicebus import ServiceBusClient, ServiceBusMessage


def load_connection_string(explicit: str | None, settings_path: str) -> str:
    if explicit:
        return explicit
    env_val = os.getenv("ServiceBusConnectionString")
    if env_val:
        return env_val
    # Intentar leer de local.settings.json
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        values = data.get("Values", {})
        cs = values.get("ServiceBusConnectionString")
        if cs:
            return cs
    except FileNotFoundError:
        pass
    raise RuntimeError(
        "No se encontró ServiceBusConnectionString. Proporcione --connection, "
        "exporte la variable de entorno o configure azure_function/local.settings.json"
    )


def build_message(project: str, request_id: str | None, steps: list[str], documents: list[str] | None) -> dict:
    if not request_id:
        request_id = f"req_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    msg: dict = {
        "projectName": project,
        "requestId": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "processingSteps": steps or ["DI", "chunking", "openai"],
    }
    if documents:
        msg["documents"] = documents
    return msg


def send_message(connection_str: str, queue_name: str, payload: dict) -> None:
    with ServiceBusClient.from_connection_string(connection_str) as client:
        with client.get_queue_sender(queue_name) as sender:
            sender.send_messages(ServiceBusMessage(json.dumps(payload)))


def main():
    parser = argparse.ArgumentParser(description="Enviar mensaje a Service Bus para procesar documentos")
    parser.add_argument("-p", "--project", required=True, help="Nombre del proyecto (carpeta en Blob)")
    parser.add_argument("-r", "--request-id", default=None, help="ID de solicitud (opcional)")
    parser.add_argument("-s", "--steps", default="DI,chunking,openai", help="Pasos a ejecutar separados por coma")
    parser.add_argument("-q", "--queue", default="analysis-event-queue", help="Nombre de la cola de Service Bus")
    parser.add_argument("-c", "--connection", default=None, help="Connection string de Service Bus")
    parser.add_argument("-d", "--documents", nargs="*", help="Lista de documentos específicos (opcional)")
    parser.add_argument("--settings", default=str(Path("azure_function/local.settings.json")), help="Ruta a local.settings.json")

    args = parser.parse_args()

    # Preparar datos
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    connection_str = load_connection_string(args.connection, args.settings)
    payload = build_message(args.project, args.request_id, steps, args.documents)

    # Enviar
    print("Enviando mensaje a Service Bus…")
    print(f"  Queue: {args.queue}")
    print(f"  Project: {args.project}")
    print(f"  Steps: {steps}")
    send_message(connection_str, args.queue, payload)
    print("✅ Mensaje enviado")
    print("Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

