#!/usr/bin/env python3
"""
Peek de los primeros N mensajes de la cola (sin bloquear ni borrar),
usando azure_functions/local.settings.json.
"""

import json
import os
from pathlib import Path
from typing import Optional

from azure.servicebus import ServiceBusClient, ServiceBusReceiveMode


def load_settings() -> dict:
    settings_path = Path(__file__).resolve().parents[1] / 'local.settings.json'
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('Values', {}) or {}
    return {}


def pick(varmap: dict, *keys: str) -> Optional[str]:
    for k in keys:
        v = varmap.get(k) or os.environ.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def main(count: int = 5) -> int:
    values = load_settings()

    connection_string = pick(
        values,
        'SERVICEBUS_CONNECTION_STRING',
        'ServiceBusConnection',
        'ServiceBusConnectionString',
    )
    queue_name = pick(values, 'SERVICEBUS_QUEUE_NAME', 'ServiceBusQueueName') or 'recoaudit-queue'

    if not connection_string:
        print('❌ Faltan credenciales de Service Bus')
        return 1

    with ServiceBusClient.from_connection_string(connection_string) as client:
        with client.get_queue_receiver(queue_name=queue_name, receive_mode=ServiceBusReceiveMode.PEEK_LOCK) as receiver:
            # peek no cambia el estado del mensaje
            msgs = receiver.peek_messages(max_message_count=count)
            if not msgs:
                print('ℹ️  No hay mensajes para peek')
                return 0
            print(f'🔎 Mostrando hasta {len(msgs)} mensajes (PEEK):')
            for i, m in enumerate(msgs, 1):
                try:
                    body = b"".join([s for s in m.body])
                    meta = []
                    if getattr(m, 'sequence_number', None) is not None:
                        meta.append(f"seq={m.sequence_number}")
                    if getattr(m, 'enqueued_time_utc', None) is not None:
                        meta.append(f"enq={m.enqueued_time_utc}")
                    prefix = f"[{i}] " + ("(" + ", ".join(meta) + ") " if meta else "")
                    print(prefix + body.decode('utf-8', errors='replace'))
                except Exception:
                    print(f"[{i}] <no decodificable>")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
