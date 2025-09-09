#!/usr/bin/env python3
"""
Chequea el número de mensajes en la cola de Azure Service Bus usando
azure_functions/local.settings.json (si existe) o variables de entorno.
"""

import json
import os
from pathlib import Path
from typing import Optional

from azure.servicebus.management import ServiceBusAdministrationClient


def load_settings() -> dict:
    # Buscar local.settings.json relativo a este archivo
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


def main() -> int:
    values = load_settings()

    connection_string = pick(
        values,
        'SERVICEBUS_CONNECTION_STRING',
        'ServiceBusConnection',
        'ServiceBusConnectionString',
    )
    queue_name = pick(values, 'SERVICEBUS_QUEUE_NAME', 'ServiceBusQueueName') or 'recoaudit-queue'

    if not connection_string:
        print('❌ No se encontró SERVICEBUS_CONNECTION_STRING / ServiceBusConnection en local.settings.json ni en el entorno')
        return 1

    admin = ServiceBusAdministrationClient.from_connection_string(connection_string)
    props = admin.get_queue_runtime_properties(queue_name)

    print(f"✅ Cola: {queue_name}")
    print("CountDetails:")
    print(f"  Active:                 {props.active_message_count}")
    print(f"  Dead-letter:            {props.dead_letter_message_count}")
    print(f"  Scheduled:              {props.scheduled_message_count}")
    print(f"  Transfer (active):      {props.transfer_message_count}")
    print(f"  Transfer dead-letter:   {props.transfer_dead_letter_message_count}")
    print(f"Total:                    {props.total_message_count}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

