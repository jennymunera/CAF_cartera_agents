#!/usr/bin/env python3
"""
Muestra propiedades de la cola de Service Bus (sesiones, maxDeliveryCount, lockDuration, etc.)
usando azure_functions/local.settings.json.
"""

import json
import os
from pathlib import Path
from typing import Optional

from azure.servicebus.management import ServiceBusAdministrationClient


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


def main() -> int:
    values = load_settings()
    connection_string = pick(values, 'SERVICEBUS_CONNECTION_STRING', 'ServiceBusConnection', 'ServiceBusConnectionString')
    queue_name = pick(values, 'SERVICEBUS_QUEUE_NAME', 'ServiceBusQueueName') or 'recoaudit-queue'
    if not connection_string:
        print('❌ Faltan credenciales de Service Bus')
        return 1

    admin = ServiceBusAdministrationClient.from_connection_string(connection_string)
    q = admin.get_queue(queue_name)
    rp = admin.get_queue_runtime_properties(queue_name)

    print(f"Queue: {queue_name}")
    print(f"RequiresSession:           {q.requires_session}")
    print(f"LockDuration:              {q.lock_duration}")
    print(f"MaxDeliveryCount:          {q.max_delivery_count}")
    print(f"DeadLetteringOnExp:        {q.dead_lettering_on_message_expiration}")
    print(f"DuplicateDetection:        {q.requires_duplicate_detection}")
    print(f"Status:                    {q.status}")
    print("-- Counts --")
    print(f"Active:                    {rp.active_message_count}")
    print(f"Dead-letter:               {rp.dead_letter_message_count}")
    print(f"Scheduled:                 {rp.scheduled_message_count}")
    print(f"Transfer (active):         {rp.transfer_message_count}")
    print(f"Transfer dead-letter:      {rp.transfer_dead_letter_message_count}")
    print(f"Total:                     {rp.total_message_count}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

