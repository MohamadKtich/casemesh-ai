# Phase 22 — Evidence & Document Ingestion Foundation

## Goal

Add a safe, local-first evidence ingestion pipeline before vector embeddings and Hybrid RAG.

## Flow

```text
Upload
  -> Validate extension and size
  -> Sanitize filename
  -> Stream to local storage
  -> SHA-256 checksum
  -> Persist document metadata
  -> Parse text
  -> Chunk text
  -> Persist chunks
  -> Mark document ready
```

## Supported file types

- TXT
- Markdown
- JSON
- CSV
- PDF with extractable text

Scanned PDFs are intentionally not OCR'd in this phase.

## Storage

Raw documents are stored under:

```text
data/raw/cases/<case_id>/documents/<document_id>/
```

The API does not expose local filesystem paths in document responses.

## API

```text
POST /cases/{case_id}/documents
GET  /cases/{case_id}/documents
GET  /cases/{case_id}/documents/{document_id}
POST /cases/{case_id}/documents/{document_id}/ingest
GET  /cases/{case_id}/documents/{document_id}/chunks
```

## Database

Migration `0002` adds ingestion metadata to `case_documents` and creates
`document_chunks`.

`document_chunks` intentionally has no vector column yet. Embeddings and
Hybrid RAG belong to the next milestone so the embedding dimension/provider
is not prematurely coupled to the persistence model.

## Setup

With Docker Desktop running and the Python 3.12 virtual environment active:

```powershell
.\scripts\setup_ingestion.ps1
```

Then:

```powershell
python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```
