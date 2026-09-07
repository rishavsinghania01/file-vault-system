# File Vault System

A full-stack file storage application built with **React (TypeScript)**, **Django REST Framework** and **PostgreSQL**. It keeps each user's file catalogue private, stores identical bytes once, and supports both filename filtering and embedding-based search by meaning.

## Features

- **Drag-and-drop upload** with per-file progress, multi-file support, and instant feedback on whether a file was new or a detected duplicate.
- **Content-based deduplication** – every upload is hashed with SHA-256. If identical content already exists, a lightweight reference row is created instead of writing the bytes to disk again, and the UI reports how much storage that saved.
- **Separate blob and reference storage** – `StoredBlob` owns the physical object while each `File` row is a user-owned reference with its own filename and upload time. Users can reuse the same blob without seeing one another's references.
- **Semantic search** – searchable text is extracted from text files and PDFs, encoded with a Sentence Transformers model, and ranked against the query with cosine similarity.
- **User isolation** – JWT authentication scopes listing, filtering, searching, downloading, statistics and deletion to the signed-in user.
- **Search & filtering** – search by filename and combine file type, size, and upload-date filters; owner, type, date, and filename metadata are indexed in the database.
- **Storage savings dashboard** – live stats on total files, duplicates detected, storage used, and storage saved.
- **Safe deletes** – deleting a reference leaves a shared blob intact; deleting its final reference removes the physical object.
- **Friendly downloads** – files are stored on disk under generated UUIDs, but download responses restore the original filename.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TanStack Query, Axios, Tailwind CSS |
| Backend | Django 5, Django REST Framework, django-filter |
| Database | PostgreSQL 16 (SQLite fallback for lightweight local tests) |
| Search | Sentence Transformers embeddings and cosine similarity |
| Infra | Docker & Docker Compose, Gunicorn, WhiteNoise |

## Project Structure

```
file-vault-system/
├── backend/                     # Django REST API
│   ├── core/                    # Project settings & root URLs
│   ├── files/                   # File vault app
│   │   ├── models.py            # StoredBlob and per-user File reference models
│   │   ├── services.py          # text extraction, embeddings and cosine similarity
│   │   ├── serializers.py       # DRF serializers
│   │   ├── views.py             # Upload/dedup, search/filter, stats, delete, download
│   │   ├── filters.py           # django-filter FilterSet powering search & filters
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── tests.py             # auth, isolation, dedup, search and lifecycle tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # React application
│   └── src/
│       ├── components/          # FileUpload, FileStats, FileSearch, FileList
│       ├── services/api.ts      # Axios client
│       ├── types/file.ts        # Shared TypeScript types
│       ├── hooks/                # useDebouncedValue
│       └── utils/format.ts      # Byte/date formatting helpers
├── docker-compose.yml           # frontend, backend and PostgreSQL
└── .github/workflows/ci.yml     # Backend tests + frontend build on push/PR
```

## Getting Started

### Option A: Docker (recommended)

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Django admin: http://localhost:8000/admin

### Option B: Local development

**Backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-semantic.txt
cp .env.example .env            # optional, defaults work out of the box
python manage.py migrate
python manage.py runserver
```

**Frontend** (in a separate terminal)

```bash
cd frontend
npm install
cp .env.example .env.local      # optional, defaults to http://localhost:8000/api
npm start
```

## Blob and Reference Storage

Every upload is streamed through a SHA-256 hash before it is saved (`files/models.py::compute_file_hash`). `StoredBlob.sha256` is unique, so identical content resolves to one physical object:

- **New content** → one `StoredBlob` is written to `media/blobs/<uuid>.<ext>` and a user-owned `File` reference points to it.
- **Matching content** → only another user-owned `File` reference is created; it points to the existing blob and stores no second physical copy.

The API never returns another user's reference. Blob reuse is an internal storage decision and does not reveal the other user's filename or metadata. A physical object is deleted only after its final reference is removed.

`GET /api/files/stats/` calculates storage used and saved for the signed-in user's references.

## How Semantic Search Works

For supported text formats and PDFs, the upload pipeline extracts text and creates a normalised document embedding with `sentence-transformers/all-MiniLM-L6-v2`. `GET /api/files/semantic-search/?q=payment+terms` embeds the query, computes cosine similarity against the signed-in user's indexed files, and returns the strongest matches first. Binary files without extractable text remain available through normal filename and metadata filters.

To index blobs created before semantic search was enabled, run `python manage.py reindex_file_embeddings`. Add `--force` to rebuild every existing embedding after changing models.

## How Search & Filtering Works

`GET /api/files/` accepts any combination of:

| Param | Meaning |
|---|---|
| `search` | Case-insensitive filename match |
| `file_type` | One or more extensions, comma-separated (`pdf,png`) |
| `min_size` / `max_size` | Size range in bytes |
| `start_date` / `end_date` | Upload date range (ISO 8601) |
| `ordering` | `uploaded_at`, `size`, or `original_filename`, prefix with `-` for descending |
| `page` | Page number (12 results per page) |

Filters are combinable (`?file_type=pdf&min_size=1000&search=invoice`) and implemented with `django-filter` against fields that all carry database indexes (`files/models.py::Meta.indexes`), so filtering stays fast as the file count grows.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | Create an account and receive JWT access/refresh tokens |
| `POST` | `/api/auth/token/` | Sign in and receive JWT access/refresh tokens |
| `GET` | `/api/files/` | List files (paginated, filterable, see above) |
| `POST` | `/api/files/` | Upload a file (`multipart/form-data`, field `file`) |
| `GET` | `/api/files/<id>/` | File metadata |
| `DELETE` | `/api/files/<id>/` | Delete a file (promotes a duplicate if needed) |
| `GET` | `/api/files/<id>/download/` | Download the file with its original filename |
| `GET` | `/api/files/stats/` | Aggregate storage & dedup stats |
| `GET` | `/api/files/file_types/` | Distinct file extensions currently stored (for filter UI) |
| `GET` | `/api/files/semantic-search/?q=...` | Rank the user's indexed files by semantic similarity |

## Running Tests

```bash
cd backend
python manage.py test
```

Covers: registration, authentication enforcement, user isolation, one-blob deduplication, semantic ranking, storage-savings statistics, filtering and last-reference cleanup. Embedding generation is replaced with deterministic vectors in tests, so the test suite does not download a model.

## Configuration

Both apps read configuration from environment variables (see `backend/.env.example` and `frontend/.env.example`):

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `MAX_UPLOAD_SIZE_BYTES`, `FILE_EMBEDDING_MODEL` (backend)
- `VITE_API_URL` (frontend)

## License

MIT — see [LICENSE](LICENSE).
