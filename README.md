# Index documents from Azure Storage

## Quick intro

### What can I use this for?

The indexer is a component in a Retrieval Augmented Generation (RAG) application. One example of such application is a chatbot that can answer questions from the documents.

It uses Azure Document Intelligence first to turn the docs into text, and then vector indexes them to Azure Search.


## Usage
This application is intended to be used as a batch run. It should figure out itself what assets need to be updated.

You need to set plenty of environment variables to make this work. See the .env.example file for a list of them.

## Running
You can run it with docker:
`docker run --env-file .env ghcr.io/piizei/blob-indexer:latest`

## Configuration
Check .env.example for values
table of configuration (environment) values

| Name                         | Description                                                                             | Default                |
|------------------------------|-----------------------------------------------------------------------------------------|------------------------|
| AZURE_SEARCH_ENDPOINT        | the URL of azure ai search                                                              |                        |
| AZURE_SEARCH_KEY=            | Admin key for search. If not specified, should use managed identity.                    |                        |
| AZURE_SEARCH_API_VERSION     | Version of azure ai search api (2023-11-01 or later from rel1.0)                        | 2023-11-01             |
| AZURE_SEARCH_EMBEDDING_MODEL | The deployment name in Azure OpenAi or model name, usually text-embedding-ada-002       | text-embedding-ada-002 |
| AZURE_SEARCH_FULL_REINDEX    | (true, false) Reindex every page (normally just the ones that changed after last index) | false                  |
| OPENAI_API_KEY               | Key to openai service (no managed identity support as now)                              |                        |
| OPENAI_API_VERSION           | The api version (2023-05-15 for example)                                                |                        |
| OPENAI_API_TYPE              | azure or none, the none is not tested.                                                  |                        |
| OPENAI_API_BASE              | Azure open-ai service full url (https://myazureopenai.openai.azure.com/)                |                        |
| LOG_LEVEL                    | one of DEBUG, INFO, WARNING                                                             | WARNING                |
| STORAGE_CONTAINER_NAME       | The name of the container in the storage account where documents are                    | files                  |

# Updates & Upgrades
The Git tags match with the docker-container tags. The releases are not guaranteed to be backward compatible.
Example of breaking change is the update of AI Search API version from preview to GA (rel-0.6 to rel-1.0).
The indexed fields are compatible (but more maybe added). This means the Chat application using the index should not break,
but you would need to reindex the storage. If it works, no need to update.

# DEV
## Prerequisites
- poetry
- For Azure AI Search, you need to have an Azure account and access to Azure OpenAI

## Testing
To run regression test, just `poetry run pytest`

## Improvements
The indexer has to read all metadata from the storage. This is due limitations of azure api.
It would be possible to add last-modification-dates as metadata to the blobs, and execute a query based on that.
This however would need user to manage the metadata (with policy or from client).



