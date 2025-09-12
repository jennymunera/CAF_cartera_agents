import logging
from typing import Set, Any, Dict, List

from .cosmo_db_client import CosmosDBClient


class PoolingEventTimerProcessor:
    """
    Lee en Cosmos DB las carpetas/proyectos con isBatchPending=true
    y devuelve el conjunto de nombres de carpeta a procesar.
    """

    def __init__(self, cosmos_db_client: CosmosDBClient) -> None:
        self.cosmos_db_client = cosmos_db_client

    def process_batch(self, cosmos_container_folder: str) -> Set[str]:
        query = """
            SELECT c.folderName
            FROM c
            WHERE c.isBatchPending = true
        """
        try:
            rows: List[Dict[str, Any]] = self.cosmos_db_client.query_items(query, cosmos_container_folder)
        except Exception as e:
            logging.warning(f"Cosmos query failed for pending folders: {e}")
            return set()

        if not rows:
            logging.info("No pending folders (isBatchPending=true) found in Cosmos")
            return set()

        folder_names: Set[str] = set()
        for row in rows:
            name = row.get("folderName") if isinstance(row, dict) else None
            if isinstance(name, str) and name:
                folder_names.add(name)
        logging.info(f"Pending folders from Cosmos: {sorted(folder_names)}")
        return folder_names

