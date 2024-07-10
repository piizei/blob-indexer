import logging
import os
from typing import Dict

from dotenv import load_dotenv

from blob_sync import otel
from blob_sync.azure_document_intelligence import doc_intelligence_from_config
from blob_sync.blob import blob_client_from_config
from blob_sync.config import get_config
from blob_sync.search import search_indexer_from_config


def sync(config: Dict[str, str] = None, blob_client=None, search=None):
    load_dotenv()
    otel.setup()
    logging.getLogger().setLevel(level=os.getenv('LOG_LEVEL', 'WARNING').upper())
    logging.info("Indexing started")
    if not config:
        config = get_config()
    if not blob_client:
        blob_client = blob_client_from_config(config)
        blob_client.media_handler = doc_intelligence_from_config(config)

    if not search:
        search = search_indexer_from_config(config)
    blob_client.list_blobs()
    # blobs that are not deleted
    current = [blob for blob in blob_client.blobs if not blob.deleted]
    archived = [blob for blob in blob_client.blobs if blob.deleted]

    search.create_or_update_index()
    search.blob_client = blob_client

    search.index(changeset={"upsert": current, "remove": archived})

    logging.info("Indexing complete")
    logging.debug(search.diagnostics)
    return search.diagnostics


# main
if __name__ == "__main__":
    print(sync())
