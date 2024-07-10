import os
# All the different handlers must be imported so that the dynamic loading works
# Todo: Find a better way to do this
from blob_sync.gpt_vision import GPTVisionMediaHandler
from blob_sync.azure_document_intelligence import AzureDocumentIntelligenceMediaHandler


def get_config():
    return {
        "search_type": os.getenv("SEARCH_TYPE", "AZURE_COGNITIVE_SEARCH"),
        "azure_search_endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
        "azure_search_key": os.getenv("AZURE_SEARCH_KEY"),
        "azure_search_full_reindex": os.getenv("AZURE_SEARCH_FULL_REINDEX", "false").lower() == "true",
        "azure_search_embedding_model": os.getenv("AZURE_SEARCH_EMBEDDING_MODEL", "text-embedding-ada-002"),
        "azure_search_api_version": os.getenv("AZURE_SEARCH_API_VERSION", "2023-11-01"),
        "azure_search_index": os.getenv("AZURE_SEARCH_INDEX", "default"),
        "account_name": os.getenv("STORAGE_ACCOUNT_NAME", None),
        "account_key": os.getenv("STORAGE_ACCOUNT_KEY", None),
        "document_intelligence_endpoint": os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT"),
        "document_intelligence_key": os.getenv("DOCUMENT_INTELLIGENCE_API_KEY"),
        "container_name": os.getenv("STORAGE_CONTAINER_NAME", "files")
    }

