#!/usr/bin/env python3
"""
Envía un mensaje al Service Bus por cada proyecto encontrado en Blob Storage.

Basado en send_test_message_simple.py, pero automatizando el descubrimiento
de proyectos mediante BlobStorageClient.list_projects().

Notas sobre la lógica actual:
- La función Service Bus `OpenAiProcess` espera {"project_name", "queue_type"}.
- Un mensaje por proyecto dispara el pipeline completo del proyecto
  (Document Intelligence -> Chunking -> OpenAI Batch) según OpenAiProcess.
- IMPORTANTE: Cada procesamiento toma ~5-7 minutos. El delay por defecto de 7 minutos
  evita saturar la cola y permite que cada mensaje se procese completamente
  antes de enviar el siguiente.
- Si tu Function App tiene alta concurrencia, podrías saturar cuotas externas;
  usa `--limit` o ajusta `--delay` para regular la carga.
"""

import os
import json
import time
import argparse
import sys
from pathlib import Path

from azure.servicebus import ServiceBusClient, ServiceBusMessage, TransportType

# Asegurar que se pueda importar shared_code/*
sys.path.append(str(Path(__file__).resolve().parents[1]))
from shared_code.utils.blob_storage_client import BlobStorageClient  # noqa: E402


def load_settings() -> dict:
    settings_path = Path(__file__).resolve().parents[1] / 'local.settings.json'
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('Values', {}) or {}
    return {}


def pick(varmap: dict, *keys: str) -> str | None:
    for k in keys:
        v = varmap.get(k) or os.environ.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def send_message(servicebus_connection: str, queue_name: str, payload: dict) -> None:
    client = ServiceBusClient.from_connection_string(
        conn_str=servicebus_connection,
        transport_type=TransportType.AmqpOverWebsocket,  # puerto 443
    )
    with client:
        sender = client.get_queue_sender(queue_name=queue_name)
        with sender:
            sender.send_messages(ServiceBusMessage(json.dumps(payload)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enviar mensajes por proyecto al Service Bus")
    parser.add_argument(
        "--projects",
        help="Lista separada por comas para forzar proyectos (si no se setea, se listan del Blob)",
        default=None,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de proyectos a enviar (útil para pruebas)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=420.0,  # 7 minutos por defecto para evitar saturar la cola
        help="Segundos a esperar entre envíos para regular carga (default: 420s = 7min)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No envía mensajes; solo muestra lo que enviaría",
    )
    args = parser.parse_args(argv)

    values = load_settings()

    # Service Bus
    connection_string = pick(
        values,
        'SERVICEBUS_CONNECTION_STRING',
        'ServiceBusConnection',
        'ServiceBusConnectionString',
    )
    queue_name = pick(values, 'SERVICEBUS_QUEUE_NAME', 'ServiceBusQueueName') or 'recoaudit-queue'
    if not connection_string:
        print("❌ SERVICEBUS_CONNECTION_STRING no configurado en local.settings.json ni en entorno")
        return 1

    # Blob Storage (para list_projects)
    # BlobStorageClient lee AZURE_STORAGE_CONNECTION_STRING desde entorno; popular desde local.settings.json
    storage_conn = pick(values, 'AZURE_STORAGE_CONNECTION_STRING')
    if storage_conn and not os.environ.get('AZURE_STORAGE_CONNECTION_STRING'):
        os.environ['AZURE_STORAGE_CONNECTION_STRING'] = storage_conn

    # Obtener lista de proyectos
    if args.projects:
        projects = [p.strip() for p in args.projects.split(',') if p.strip()]
    else:
        try:
            blob_client = BlobStorageClient()
            projects = blob_client.list_projects()
        except Exception as e:
            print(f"❌ Error obteniendo proyectos desde Blob Storage: {e}")
            return 1

    if not projects:
        print("⚠️  No se encontraron proyectos para enviar")
        return 0

    if args.limit is not None:
        projects = projects[: args.limit]

    print(f"🔎 Proyectos a enviar: {len(projects)} -> {projects}")

    sent = 0
    for idx, project in enumerate(projects, start=1):
        payload = {"project_name": project, "queue_type": "processing"}
        if args.dry_run:
            print(f"DRY-RUN [{idx}/{len(projects)}] -> {payload}")
        else:
            try:
                send_message(connection_string, queue_name, payload)
                sent += 1
                print(f"✅ Enviado [{idx}/{len(projects)}] proyecto={project}")
            except Exception as e:
                print(f"❌ Error enviando proyecto {project}: {e}")

        if args.delay and idx < len(projects):
            time.sleep(args.delay)

    if not args.dry_run:
        print(f"\n📦 Cola: {queue_name}")
        print(f"📊 Mensajes enviados: {sent}/{len(projects)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

