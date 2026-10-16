# File Vault System

A file store where identical bytes are written to disk once however many people upload them. Each user still sees only their own files, and search works on what a document says as well as its filename.

React (TypeScript) · Django REST Framework · PostgreSQL · JWT · sentence-transformers

## How deduplication works

Two users uploading the same 40 MB PDF should cost 40 MB of disk. Two decisions make that work.

### Blobs and files are separate tables

The schema splits physical storage from what the user sees (`backend/files/models.py`):

```
StoredBlob: one per distinct content       File: one per user, per upload
  id             uuid  ◄──────────────────── blob               FK, on_delete=PROTECT
  file           media/blobs/<uuid>.<ext>    owner              FK → auth user
  sha256         unique, indexed             original_filename  "Q3 report.pdf"
  size           bytes                       file_type          "pdf"
  content_type                               uploaded_at
  extracted_text                             reused_blob        bool
  embedding      json (384 floats)
```

There is one `StoredBlob` per distinct content and one `File` per user per upload. When two people upload the same document they get two `File` rows, each with its own filename and timestamp and each invisible to the other, and both rows point at one object on disk.

`extracted_text` and `embedding` live on the blob, so text extraction and embedding also run once per distinct document. Deduplication saves CPU as well as bytes.

The reference's foreign key to its blob uses `on_delete=PROTECT` (`models.py:72`). The database refuses to delete a blob that still has references, so the cleanup path below cannot orphan a file someone is using.

### Postgres settles the upload race

The upload path (`backend/files/views.py:53`) streams the file through SHA-256 in 1 MB chunks (`models.py:29`), so a large upload is never held in memory. It then looks for a blob with that digest and creates one if there is none.

Lookup followed by insert is a race: two simultaneous uploads of the same new file can both find nothing. `sha256` has a unique constraint, so Postgres decides which insert wins and the code handles the loser:

```python
# views.py:89
try:
    with transaction.atomic():
        candidate.save(force_insert=True)
    blob = candidate
except IntegrityError:
    if candidate.file:
        candidate.file.delete(save=False)          # drop the object we just wrote
    blob = StoredBlob.objects.get(sha256=file_hash)  # use the winner's blob
    reused_blob = True
```

The losing upload deletes the bytes it wrote and uses the winner's blob. Both uploads succeed, both users get a reference, and one physical copy exists. Only the database constraint can guarantee that under concurrency, which is why the code leaves it to the constraint and takes no lock of its own.

Deletion works from the other end (`views.py:117`):

```python
with transaction.atomic():
    reference.delete()
    blob = StoredBlob.objects.select_for_update().filter(pk=blob_id).first()
    if blob and not blob.references.exists():
        blob.file.delete(save=False)
        blob.delete()
```

`select_for_update()` locks the blob row, so a concurrent upload cannot attach a new reference between the check for remaining references and the delete. Deleting your copy of a shared file leaves everyone else's alone. Deleting the last reference removes the object from disk.

## Features

- Content-based deduplication using the SHA-256 of the bytes and a unique constraint. The upload response says whether the file was new or a duplicate and how many bytes that saved.
- Every list, filter, search, download, stat and delete is scoped to the signed-in user by `get_queryset` (`views.py:37`). Nobody sees another user's filenames, metadata or references, although the upload response does reveal that identical content already existed (see [limitations](#limitations)).
- Semantic search: text is extracted from text formats and PDFs, embedded once per blob and ranked against the query by cosine similarity.
- Filename search combined with file type, size range and upload date range, all on indexed columns.
- A storage dashboard with total files, unique files, duplicates, storage used, storage saved and the savings percentage.
- Drag-and-drop upload of several files at once, with progress for each.
- Objects are stored under generated UUIDs so the disk never exposes a filename. Downloads restore the original name.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TanStack Query, Axios, Tailwind CSS |
| Backend | Django 5, Django REST Framework, django-filter, SimpleJWT |
| Database | PostgreSQL 16 (SQLite accepted via `DATABASE_URL` for a quick local run) |
| Search | `sentence-transformers/all-MiniLM-L6-v2`, cosine similarity |
| Infra | Docker Compose, Gunicorn, WhiteNoise, GitHub Actions |

## Getting started

### Docker

```bash
docker-compose up --build
```

Frontend `http://localhost:3000` · API `http://localhost:8000/api` · admin `http://localhost:8000/admin`

### Local

```bash
cd backend
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-semantic.txt            # torch + sentence-transformers
cp .env.example .env                                # optional, defaults work
python manage.py migrate
python manage.py runserver
```

```bash
cd frontend
npm install
cp .env.example .env.local                          # optional, defaults to localhost:8000/api
npm start
```

The backend runs without `requirements-semantic.txt`; semantic search then returns `503` with an explanation while everything else works (`services.py:13`).

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | Create an account, receive JWT access and refresh tokens |
| `POST` | `/api/auth/token/` | Sign in, receive tokens |
| `POST` | `/api/auth/token/refresh/` | Exchange a refresh token |
| `GET` | `/api/files/` | List the caller's files (paginated, filterable, sortable) |
| `POST` | `/api/files/` | Upload (`multipart/form-data`, field `file`) |
| `GET` | `/api/files/<id>/` | One file's metadata |
| `DELETE` | `/api/files/<id>/` | Delete the caller's reference; the blob goes only with its last reference |
| `GET` | `/api/files/<id>/download/` | Download, with the original filename restored |
| `GET` | `/api/files/stats/` | Storage used, storage saved, duplicate count |
| `GET` | `/api/files/file_types/` | Distinct extensions the caller has, for the filter UI |
| `GET` | `/api/files/semantic-search/?q=…` | Rank the caller's indexed files by meaning |

### Filtering

`GET /api/files/` accepts any combination:

| Param | Meaning |
|---|---|
| `search` | Case-insensitive filename match |
| `file_type` | One or more extensions, comma-separated (`pdf,png`) |
| `min_size` / `max_size` | Size in bytes |
| `start_date` / `end_date` | Upload date range, ISO 8601 |
| `ordering` | `uploaded_at`, `size`, `original_filename`; prefix `-` to reverse |
| `page` | 12 results per page |

Filters combine (`?file_type=pdf&min_size=1000&search=invoice`) and every column they touch is indexed, including three composite indexes on `(owner, uploaded_at)`, `(owner, original_filename)` and `(owner, file_type)` (`models.py:82`). The owner column leads each one because every query filters by owner first.

## Semantic search

On the first upload of a given content, the backend extracts text from PDFs with `pypdf` and from a whitelist of text formats (`services.py:45`), caps it at 500k characters, and embeds it with `all-MiniLM-L6-v2` into a normalised 384-dimension vector stored on the blob. The model loads once per process (`lru_cache`, `services.py:13`).

`GET /api/files/semantic-search/?q=payment+terms` embeds the query the same way, scores the caller's files by cosine similarity and returns the best matches. Binary files with no extractable text have no embedding and are still found by filename and metadata.

To index blobs created before semantic search existed:

```bash
python manage.py reindex_file_embeddings          # --force rebuilds every embedding
```

## Tests

```bash
cd backend && python manage.py test
```

Twelve tests cover registration, authentication, cross-user isolation, one blob for identical content, separate blobs for different content, the storage-savings arithmetic, semantic ranking, filename and size filters, and both halves of the delete rule: a shared blob survives when one reference is deleted, and the last deletion removes it.

The tests replace embeddings with deterministic vectors, so the suite never downloads a model. CI (`.github/workflows/ci.yml`) runs them against a PostgreSQL 16 service container. That matters here, because the deduplication tests only mean something against a database that enforces the unique constraint.

## Limitations

Semantic search is a linear scan. Every query loads up to `SEMANTIC_SEARCH_CANDIDATE_LIMIT` (default 1000) of the caller's embeddings and scores them in Python (`views.py:147`). That is fine for a personal vault and too slow for a large one; the upgrade is `pgvector` with an HNSW index and the similarity computed in the database.

Deduplication is global, and other users can observe it. Blobs are shared across all users, so an upload response of `"duplicate": true` tells the uploader that this exact content already exists somewhere in the system. Someone could use that to confirm that a file they suspect is stored here. Any cross-user dedup has this side channel. The fixes are to accept it, deduplicate per user, or stop reporting duplicate status to the uploader.

Storage is the local filesystem, `media/blobs/` through Django's default storage. Moving to S3 or another object store is a settings change plus a migration of existing objects.

Uploads are not scanned. The type comes from the extension and the browser's `content_type`, and nothing checks the bytes for malware or confirms the claimed type.

There is no sharing, no folders, no versioning and no soft delete. Deleting a reference is immediate and permanent.

## Project structure

```
file-vault-system/
├── backend/
│   ├── core/                     settings, root urls
│   ├── files/
│   │   ├── models.py             StoredBlob, File, compute_file_hash
│   │   ├── views.py              upload/dedup, delete, download, search, stats
│   │   ├── services.py           text extraction, embeddings, cosine similarity
│   │   ├── serializers.py        response shapes
│   │   ├── filters.py            django-filter FilterSet
│   │   ├── auth_views.py         registration
│   │   ├── tests.py              12 tests
│   │   └── management/commands/reindex_file_embeddings.py
│   ├── requirements.txt
│   └── requirements-semantic.txt
├── frontend/src/
│   ├── components/               AuthPanel, FileUpload, FileStats, FileSearch, FileList
│   ├── services/api.ts           Axios client
│   ├── hooks/                    useDebouncedValue
│   └── utils/format.ts
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Configuration

Both apps read environment variables; see `backend/.env.example` and `frontend/.env.example`.

Backend: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `MAX_UPLOAD_SIZE_BYTES` (default 100 MB), `FILE_EMBEDDING_MODEL`, `MAX_EMBEDDING_CHARACTERS`, `MAX_EXTRACTED_TEXT_CHARACTERS`, `SEMANTIC_SEARCH_CANDIDATE_LIMIT`.

Frontend: `VITE_API_URL`.

## License

MIT, see [LICENSE](LICENSE).
