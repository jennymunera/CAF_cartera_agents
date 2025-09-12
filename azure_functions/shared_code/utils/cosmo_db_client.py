import os
from typing import Any, Dict, List, Optional

from azure.cosmos import CosmosClient, exceptions


class CosmosDBClient:
    """
    Pequeño wrapper sobre azure.cosmos para operaciones frecuentes.
    Lee configuración desde variables de entorno:
    - COSMOS_DB_CONNECTION_STRING
    - COSMOS_DB_DATABASENAME
    """

    def __init__(self, connection_string: str = "", database_name: str = "") -> None:
        self.connection_string = connection_string or os.environ.get("COSMOS_DB_CONNECTION_STRING", "")
        self.database_name = database_name or os.environ.get("COSMOS_DB_DATABASENAME", "")

        if not self.connection_string or not self.database_name:
            raise ValueError("Missing COSMOS_DB_CONNECTION_STRING or COSMOS_DB_DATABASENAME in environment")

        self.client = CosmosClient.from_connection_string(self.connection_string)
        self.database = self.client.get_database_client(self.database_name)

    def upsert_item(self, document: Dict[str, Any], container_name: str) -> Dict[str, Any]:
        container = self.database.get_container_client(container_name)
        return container.upsert_item(document)

    def read_item(self, item_id: str, partition_key: Any, container_name: str) -> Optional[Dict[str, Any]]:
        try:
            container = self.database.get_container_client(container_name)
            return container.read_item(item=item_id, partition_key=partition_key)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def item_exists(self, item_id: str, partition_key: Any, container_name: str) -> bool:
        try:
            container = self.database.get_container_client(container_name)
            container.read_item(item=item_id, partition_key=partition_key)
            return True
        except exceptions.CosmosResourceNotFoundError:
            return False

    def query_items(self, query: str, container_name: str, parameters: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        container = self.database.get_container_client(container_name)
        results_iter = container.query_items(query=query, parameters=parameters or [], enable_cross_partition_query=True)
        return list(results_iter)

