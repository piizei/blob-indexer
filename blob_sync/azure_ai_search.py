import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict
import hashlib


import requests
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobProperties
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings


class AzureAISearchIndexer:
    datetime_format = '%Y-%m-%dT%H:%M:%S.%fZ'

    def __init__(self, config):
        self.attachment_cache = {}
        self.diagnostics = None
        self.headers = {'Content-Type': 'application/json', 'api-key': config["azure_search_key"]}
        self.params = {'api-version': config["azure_search_api_version"]}
        self.endpoint = config["azure_search_endpoint"]
        self.index_name = config["azure_search_index"]
        self.full_reindex = config["azure_search_full_reindex"]
        # Check if env value contains 'azure'
        if os.getenv("OPENAI_API_BASE", "").find("azure") > -1 or os.getenv("AZURE_OPENAI_ENDPOINT", None) is not None:
            if os.getenv("AZURE_OPENAI_ENDPOINT ", None) is None:
                os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("OPENAI_API_BASE")
                del os.environ["OPENAI_API_BASE"]
            self.embedder = AzureOpenAIEmbeddings(azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                                                  deployment=config["azure_search_embedding_model"],
                                                  chunk_size=1)
        else:
            self.embedder = OpenAIEmbeddings(deployment=config["azure_search_embedding_model"],
                                             chunk_size=1,
                                             )
        self.now = datetime.utcnow().strftime(self.datetime_format)
        self.credential = AzureKeyCredential(config["azure_search_key"]) if config[
            "azure_search_key"] else DefaultAzureCredential()
        self.client = SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=self.credential)
        self.blob_client = None
        self.reset()

    def index(self, changeset: Dict[str, List]):
        """List all documents in the index and map to spaces with their pages"""
        # First go through all upserts and update latest_updates for each new space
        # Sor them by date first
        create = []
        update = []
        upserts = sorted(changeset["upsert"], key=lambda x: x["last_modified"], reverse=True)
        for upsert in upserts:
            page_id = upsert.name
            # Check if document exists (the first chunk)
            last_indexed_date, last_modified_date_in_index = self.get_indexing_metadata(page_id)
            if last_indexed_date is None:
                create.append(upsert)
            else:
                modified_in_storage = upsert["last_modified"]
                if last_modified_date_in_index < modified_in_storage or self.full_reindex:
                    update.append(upsert)
                if last_indexed_date > modified_in_storage and not self.full_reindex:
                    # break from the loop, as the rest are older
                    break

        # remove items in changeset remove
        for item in changeset["remove"]:
            count = self.remove_item(item)
            if count > 0:  # The count is number of chunks, not documents
                self.diagnostics["counts"]["remove"] += 1
        # remove items that need to be updated ->
        # document is split in multiple search entries and we dont know how its going to chuck this time ->
        # easier to remove existing chunks and reindex
        for item in update:
            self.diagnostics["counts"]["update"] += 1
            self.remove_item(item)
            self.create_item(item)
        # create new items
        for item in create:
            self.diagnostics["counts"]["create"] += 1
            self.create_item(item)

    def get_indexing_metadata(self, page_id):
        # not found, set olden times
        last_modified_date_in_index = datetime(1900, 1, 1, 1, 1, tzinfo=timezone.utc)
        last_indexed_date = None
        try:
            doc = self.client.get_document(key=create_md5_hash(f"{page_id}_0"),
                                           selected_fields=["id", "last_indexed_date", "last_modified_date"])
            last_modified_date_in_index = datetime.fromisoformat(doc["last_modified_date"])
            last_indexed_date = datetime.fromisoformat(doc["last_indexed_date"])
        except:
            # not found in ai-search
            pass
        return last_indexed_date, last_modified_date_in_index

    def remove_item(self, item):
        # Get all documents that match the document_id
        results = list(self.client.search(search_text="*",
                                          filter="document_id eq '" + item["name"] + "'"))
        to_be_deleted = list(map(lambda x: {'id': x['id']}, results))
        if len(to_be_deleted) > 0:
            self.client.delete_documents(documents=to_be_deleted)
        return len(to_be_deleted)

    def create_item(self, item):
        # Handle attachments
        docs = []
        # Create a new document
        page_chunks = self.blob_client.chunk_document(item)
        docs.extend(self.chunks_to_documents(page_chunks, item))
        try:
            for doc in docs:
                resp = self.client.upload_documents(documents=[doc])
                if not resp[0].succeeded:
                    logging.warning(f"Could not index document {doc['url']} to Azure Search: {resp[0].errors}")
        except Exception as e:
            logging.warning(f"Could not index documents to Azure Search: {e}")

    def chunks_to_documents(self,
                            chunks: List[Dict],
                            item: BlobProperties
                            ) -> List[Dict]:
        docs = []
        item_type = item.content_settings.content_type
        url = f'{self.blob_client.container.url}/{item.name}'

        last_modified_date = item.last_modified.strftime(self.datetime_format)

        for i, chunk in enumerate(chunks):
            # Different chunkers return different type of objects :rolleyes:
            if isinstance(chunk, dict):
                chunk_text = chunk.page_content if chunk.page_content else "-------"
            else:
                chunk_text = chunk
            document_id = f'{item.name}_{i}'
            docs.append({
                "id": create_md5_hash(document_id),
                "document_id": item.name,
                "item_type": item_type,
                "chunk": chunk_text,
                "chunkVector": self.embedder.embed_query(chunk_text),
                "last_modified_date": last_modified_date,
                "last_indexed_date": self.now,
                "url": url
            })
        return docs

    def create_or_update_index(self):
        """Create or update the index with the latest schema
            the operation is idempotent and can be invoked multiple times without any side effects
        """
        schema = {
            "name": self.index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": "true", "searchable": "false", "retrievable": "true",
                 "filterable": "true"},
                {"name": "document_id", "type": "Edm.String", "key": "false", "searchable": "false",
                 "retrievable": "true", "filterable": "true"},
                {"name": "item_type", "type": "Edm.String", "searchable": "false", "retrievable": "true",
                 "filterable": "true"},
                {"name": "name", "type": "Edm.String", "searchable": "true", "retrievable": "true"},
                {"name": "chunk", "type": "Edm.String", "searchable": "true", "retrievable": "true"},
                {"name": "chunkVector", "type": "Collection(Edm.Single)", "searchable": "true", "retrievable": "true",
                 "dimensions": 1536, "vectorSearchProfile": "default-vector-profile"},
                {"name": "last_modified_date", "type": "Edm.DateTimeOffset", "searchable": "false",
                 "retrievable": "true", "filterable": "true"},
                {"name": "last_indexed_date", "type": "Edm.DateTimeOffset", "searchable": "false",
                 "retrievable": "true", "filterable": "true"},
                {"name": "url", "type": "Edm.String", "searchable": "false", "retrievable": "true"}
            ],
            "vectorSearch": {
                "algorithms": [
                    {
                        "name": "hnsw-config-1",
                        "kind": "hnsw"
                    }],
                "profiles": [
                    {
                        "name": "default-vector-profile",
                        "algorithm": "hnsw-config-1"
                    }
                ]
            },
            "semantic": {
                "configurations": [
                    {
                        "name": "my-semantic-config",
                        "prioritizedFields": {
                            "prioritizedContentFields": [
                                {
                                    "fieldName": "chunk"
                                }
                            ],
                            "prioritizedKeywordsFields": []
                        }
                    }
                ]
            }
        }
        resp = requests.put(self.endpoint + "/indexes/" + self.index_name, data=json.dumps(schema),
                            headers=self.headers, params=self.params)

        if resp.status_code > 299:
            print(f'Could not create or update index, error {resp.text}')
            logging.error(f'Could not create or update index, error {resp.text}')
            exit(-1)

    def drop_index(self):
        resp = requests.delete(self.endpoint + "/indexes/" + self.index_name, headers=self.headers, params=self.params)

    def reset(self):
        self.spaces_indexed = []
        self.diagnostics = {"counts": {"create": 0,
                                       "update": 0,
                                       "remove": 0,
                                       "attachment-create": 0,
                                       "attachment-update": 0}
                            }

def create_md5_hash(input_string):
    # Step 2: Encode the input string to bytes
    input_bytes = input_string.encode('utf-8')

    # Step 3: Create a new md5 hash object and hash the input bytes
    hash_object = hashlib.md5(input_bytes)

    # Step 4: Get the hexadecimal representation of the digest
    hash_hex = hash_object.hexdigest()

    return hash_hex
