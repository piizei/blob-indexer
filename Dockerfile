FROM python:3.11-bookworm

# set work directory
WORKDIR /usr/src/app

# install dependencies
COPY pyproject.toml poetry.lock README.md ./
RUN pip install poetry && \
    poetry config virtualenvs.create false
COPY blob_sync/ blob_sync/
RUN poetry install
WORKDIR /usr/src/app/blob_sync

EXPOSE 8080
CMD ["python", "sync.py" ]
