import os
import tempfile
from typing import Dict, List

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobProperties


class BlobWrapper:
    """Wrapper around Azure Blob Storage"""

    def __init__(self, account_name: str, account_key: str, container_name: str):
        self.container_name = container_name
        if not account_key:
            creds = DefaultAzureCredential()
            self.blob_client = BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net",
                                                 credential=creds)
        else:
            self.blob_client = BlobServiceClient.from_connection_string(
                conn_str=f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net")
        self.container = self.blob_client.get_container_client(container_name)
        self.blobs = []
        self.media_handler = None

    def list_blobs(self):
        continuation_token = None
        while True:
            blobs = (self.container.list_blobs(include=['deleted'], results_per_page=5000)
                     .by_page(continuation_token=continuation_token))
            self.blobs.extend([blob for blob in list(next(blobs))])
            continuation_token = blobs.continuation_token
            if not continuation_token:
                break
        return self.blobs

    def chunk_document(self, blob: BlobProperties) -> List[Dict]:
        """Chunks a doc into smaller pieces"""
        try:
            blob_client = self.container.get_blob_client(blob.name)
            # create tmp dir
            tmp_dir = tempfile.mkdtemp()
            with open(file=os.path.join(tmp_dir, blob.name), mode="wb") as dl_blob:
                download_stream = blob_client.download_blob()
                dl_blob.write(download_stream.readall())
                dl_blob.close()
                chunks = self.media_handler.handle(os.path.join(tmp_dir, blob.name))
                os.remove(os.path.join(tmp_dir, blob.name))
                return chunks
        except:
            return []

    def create_test_container(self):
        """Creates a test container"""
        random_postfix = os.urandom(4).hex()
        self.container = self.blob_client.create_container(f"test{random_postfix}")

    def remove_test_container(self):
        """Removes a test container"""
        return self.blob_client.delete_container(self.container.container_name)

    def create_or_update_test_blob(self, data: str) -> dict:
        """Creates a test blob"""
        blob_client = self.container.get_blob_client(blob="test_blob.html")

        return blob_client.upload_blob(data, overwrite=True, content_type="text/html")



    def delete_test_blob(self):
        """deletes a test blob"""
        blob_client = self.container.get_blob_client(blob="test_blob.html")
        blob_client.delete_blob(delete_snapshots="include")


def blob_client_from_config(config: Dict[str, str]) -> BlobWrapper:
    """Creates a Azure Blob client wrapper from a config"""
    return BlobWrapper(
        config["account_name"],
        config["account_key"],
        config["container_name"]
    )
