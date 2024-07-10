import logging
from pathlib import Path
from typing import List, Dict

from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class AzureDocumentIntelligenceMediaHandler:
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("===", "Page Break"),
    ]

    chunk_size = 2000
    chunk_overlap = 500

    def __init__(self, api_endpoint: str, api_key: str, chunking_strategy: str = "text"):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.api_model = "prebuilt-layout"
        self.chunking_strategy = chunking_strategy

    def handle(self, file_path: str) -> List[Document]:
        try:
            file_format = file_path.split(".")[-1].lower()
            if file_format not in ["pdf", "docx", "doc", "png", "jpg", "jpeg", "bmp", "tiff", "heif", "pptx"]:
                logging.info("Treating file as text")
                docs_string = Path(file_path).read_text()
            else:
                # TODO: if pdf is over 2000 pages, we wound need to split it into smaller chunks
                # Currently this is not handled
                loader = AzureAIDocumentIntelligenceLoader(
                    api_endpoint=self.api_endpoint,
                    api_key=self.api_key,
                    file_path=file_path,
                    api_model=self.api_model
                )
                try:
                    documents = loader.load()
                except Exception as e:
                    logging.ERROR(f"Error loading document {file_path}: {e}")
                    return []
                docs_string = documents[0].page_content

            if self.chunking_strategy == "text":
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap
                )
            else:
                text_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.headers_to_split_on)

            return text_splitter.split_text(docs_string)
        except Exception as e:
            logging.error(f"Error splitting text: {e}")
            return []


def doc_intelligence_from_config(config: Dict[str, str]) -> AzureDocumentIntelligenceMediaHandler:
    """Creates a Azure Blob client wrapper from a config"""
    return AzureDocumentIntelligenceMediaHandler(
        config["document_intelligence_endpoint"],
        config["document_intelligence_key"]
    )
