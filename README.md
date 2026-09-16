# File Vault System

A full-stack file store where identical bytes are written once no matter how many people upload them, each user still sees only their own files, and search works by meaning as well as by filename.

React (TypeScript) · Django REST Framework · PostgreSQL · JWT · sentence-transformers

---

## The part worth reading

Two users uploading the same 40 MB PDF should cost 40 MB, not 80. Getting that right is the whole design, and it lives in two decisions.

### 1. A blob is not a file

The schema splits physical storage from what the user sees (`backend/files/models.py`):

```
StoredBlob — one per distinct content      File — one per user, per upload
  id             uuid  ◄──────────────────── blob               FK, on_delete=PROTECT
  file           media/blobs/<uuid>.<ext>    owner              FK → auth user
  sha256         unique, indexed             original_filename  "Q3 report.pdf"
  size           bytes                       file_type          "pdf"
  content_type                               uploaded_at
  extracted_text                             reused_blob        bool
  embedding      json (384 floats)
```

One `StoredBlob` per distinct content. One `File` per user per upload. Two people who upload the same document get two `File` rows — their own filenames, their own timestamps, each invisible to the other — pointing at one object on disk.

Putting `extracted_text` and `embedding` on the blob rather than the reference means the text extraction and the embedding also happen **once per distinct document**, not once per upload. Deduplication saves the CPU as well as the bytes.

`on_delete=PROTECT` on the reference's blob FK (`models.py:72`) makes the database refuse to delete a blob that still has references, so the cleanup path below cannot orphan a file someone is still using.

### 2. The unique constraint decides, not the code

The upload path (`backend/files/views.py:53`) streams the upload through SHA-256 in 1 MB chunks (`models.py:29`, so a large file is never held in memory), looks for an existing blob with that digest, and creates one if there is none.

That lookup-then-insert is a race: two simultaneous uploads of the same new file can both find nothing. The code does not try to win the race with a lock — it lets Postgres settle it, because `sha256` is `unique`:

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

The loser cleans up the bytes it wrote and adopts the winner's blob. Both uploads succeed, both users get their reference, and exactly one physical copy exists. The invariant is held by the database constraint, which is the only thing that can hold it under concurrency.

Deletion is the same idea from the other end (`views.py:117`):

```python
with transaction.atomic():
    reference.delete()
    blob = StoredBlob.objects.select_for_update().filter(pk=blob_id).first()
    if blob and not blob.references.exists():
        blob.file.delete(save=False)
        blob.delete()
```

`select_for_update()` takes a row lock on the blob, so a concurrent upload cannot attach a new reference in the window between "are there any references left?" and the delete. Deleting your copy of a shared file never disturbs anyone else's; deleting the last reference is what removes the object from disk.

---

## Features

- **Content-based deduplication** — SHA-256 of the bytes, a unique constraint, and one physical copy per distinct content. The upload response says whether the file was new or a duplicate and how many bytes that saved.
- **User isolation** — every list, filter, search, download, stat and delete is scoped to the signed-in user by `get_queryset` (`views.py:37`). You never see another user's filename, metadata or reference, though the upload response does reveal that identical content already existed — see [what this does not do](#what-this-does-not-do).
- **Semantic search** — text is extracted from text formats and PDFs, embedded once per blob, and ranked against the query by cosine similarity.
- **Search and filtering** — filename search combined with file type, size range and upload-date range, all against indexed columns.
- **Storage dashboard** — total files, unique files, duplicates, storage used, storage saved, savings percentage.
- **Drag-and-drop upload** with per-file progress and multi-file support.
- **Friendly downloads** — objects are stored under generated UUIDs so the disk never exposes a filename, and the download response restores the original one.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TanStack Query, Axios, Tailwind CSS |
| Backend | Django 5, Django REST Framework, django-filter, SimpleJWT |
| Database | PostgreSQL 16 (SQLite accepted via `DATABASE_URL` for a quick local run) |
| Search | `sentence-transformers/all-MiniLM-L6-v2`, cosine similarity |
| Infra | Docker Compose, Gunicorn, WhiteNoise, GitHub Actions |

---

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

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | Create an account, receive JWT access and refresh tokens |
| `POST` | `/api/auth/token/` | Sign in, receive tokens |
| `POST` | `/api/auth/token/refresh/` | Exchange a refresh token |
| `GET` | `/api/files/` | List the caller's files — paginated, filterable, sortable |
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

Filters combine (`?file_type=pdf&min_size=1000&search=invoice`) and every column they touch is indexed, including three composite indexes on `(owner, uploaded_at)`, `(owner, original_filename)` and `(owner, file_type)` (`models.py:82`) — the owner column is in each one because every query is owner-scoped first.

---

## Semantic search

On the first upload of a given content, text is extracted — PDFs via `pypdf`, plus a whitelist of text formats (`services.py:45`) — capped at 500k characters, and embedded with `all-MiniLM-L6-v2` into a normalised 384-dimension vector stored on the blob. The model is loaded once per process (`lru_cache`, `services.py:13`).

`GET /api/files/semantic-search/?q=payment+terms` embeds the query the same way, then scores the caller's files by cosine similarity and returns the best matches. Binary files with no extractable text simply have no embedding and stay findable by filename and metadata.

To index blobs created before semantic search existed:

```bash
python manage.py reindex_file_embeddings          # --force rebuilds every embedding
```

---

## Tests

```bash
cd backend && python manage.py test
```

Twelve tests covering registration, authentication enforcement, cross-user isolation, one-blob deduplication, non-deduplication of different content, storage-savings arithmetic, semantic ranking, filename and size filtering, and both halves of the delete rule — that a shared blob survives one reference being deleted, and that the last deletion removes it.

Embeddings are replaced with deterministic vectors in the tests, so the suite never downloads a model. CI (`.github/workflows/ci.yml`) runs them against a real PostgreSQL 16 service container, which matters here: the deduplication tests are only meaningful against a database that actually enforces the unique constraint.

---

## What this does not do

**Semantic search is a linear scan, not a vector index.** Every query loads up to `SEMANTIC_SEARCH_CANDIDATE_LIMIT` (default 1000) of the caller's embeddings and scores them in Python (`views.py:147`). That is fine for a personal vault and wrong for a large one — `pgvector` with an HNSW index, and the similarity computed in the database, is the upgrade.

**Deduplication is global, and that is observable.** Blobs are shared across all users, so an upload response of `"duplicate": true` tells you that this exact content already existed somewhere in the system. That is a real side channel — it is how you could confirm a suspected file is held by someone — and it is inherent to cross-user dedup rather than a bug here. The options are to accept it, scope dedup per user, or stop reporting duplicate status to the uploader.

**Storage is the local filesystem.** `media/blobs/` via Django's default storage. S3 or another object store is a settings change plus a migration of existing objects.

**Uploads are not scanned.** Type is taken from the extension and the browser's `content_type`; nothing inspects the bytes for malware or verifies the claimed type.

**No sharing, folders, versioning or soft delete.** A delete is immediate and permanent for that reference.

---

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

Backend — `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `MAX_UPLOAD_SIZE_BYTES` (default 100 MB), `FILE_EMBEDDING_MODEL`, `MAX_EMBEDDING_CHARACTERS`, `MAX_EXTRACTED_TEXT_CHARACTERS`, `SEMANTIC_SEARCH_CANDIDATE_LIMIT`.

Frontend — `VITE_API_URL`.

## License

MIT — see [LICENSE](LICENSE).
