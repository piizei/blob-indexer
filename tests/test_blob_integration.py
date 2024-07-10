import logging
import random
import string
import time

import pytest

from blob_sync.azure_ai_search import create_md5_hash
from blob_sync.azure_document_intelligence import doc_intelligence_from_config
from blob_sync.blob import blob_client_from_config
from blob_sync.config import get_config
from dotenv import load_dotenv

from blob_sync.search import search_indexer_from_config
from blob_sync.sync import sync


@pytest.fixture
def config():
    load_dotenv()
    config = get_config()
    return config


@pytest.fixture
def client(config):
    client = blob_client_from_config(config)
    client.media_handler = doc_intelligence_from_config(config)
    client.create_test_container()
    yield client
    client.remove_test_container()


@pytest.fixture
def search(config, client):
    config["azure_search_index"] = config["azure_search_index"] + "_test"
    search = search_indexer_from_config(config)
    search.blob_client = client
    yield search
    # search.drop_index()


def test_crud(search, client, config):
    # First run on fresh index
    diagnostics = sync(config, client, search)
    assert_diagnostics(diagnostics, count_create=None)
    search.reset()
    # Run the indexer once, and then assert that nothing changed
    # If something changed on wiki, then it got indexed and next time the test should work again :)
    diagnostics = sync(config, client, search)
    assert_diagnostics(diagnostics)
    search.reset()
    test_page = client.create_or_update_test_blob("<p>Test page</p>")
    diagnostics = sync(config, client, search)
    assert_diagnostics(diagnostics, count_create=1)
    search.reset()
    # Check that it was actually put into search index
    # Note that this only works with Azure Cognitive Search as it's using it's client directly
    # Also sleep a bit before searching, it takes few seconds for the index to update
    time.sleep(5)
    page_id = create_md5_hash(f"test_blob.html_0")
    search.client.get_document(key=page_id, selected_fields=["id"])
    # Update
    random_str = get_random_string()
    client.create_or_update_test_blob(f"<p>Test page updated {random_str}</p>")
    diagnostics = sync(config, client, search)
    assert_diagnostics(diagnostics, count_update=1)
    search.reset()
    time.sleep(5)
    doc = search.client.search(search_text=random_str,
                               include_total_count=True,
                               filter=f"document_id eq 'test_blob.html'")
    assert doc.get_count() == 1
    client.delete_test_blob()
    diagnostics = sync(config, client, search)
    assert_diagnostics(diagnostics, count_remove=1)
    search.reset()
    try:
        doc = search.client.get_document(key=page_id)
        assert False  # Should not get here
    except Exception as e:
        assert e.status_code == 404

# This test is disabled by default as it costs a lot.
# add test_ in front of the big to enable it (test_big)
def big(search, client, config):
    client.container.get_blob_client(blob="microsoft-copilot-studio.pdf").upload_blob(
        open("./microsoft-copilot-studio.pdf", "rb"), overwrite=True)
    diagnostics = sync(config, client, search)

def assert_diagnostics(diagnostics, count_create=0, count_update=0, count_remove=0):
    print("Diagnostics: ", diagnostics)
    if count_create is not None:
        assert diagnostics["counts"]["create"] == count_create
    assert diagnostics["counts"]["update"] == count_update
    assert diagnostics["counts"]["remove"] == count_remove


def get_random_string():
    return ''.join(random.choice(string.ascii_lowercase) for i in range(5))
