# File Vault System

A full-stack file storage application built with **React (TypeScript)** and **Django REST Framework**, focused on two things: never storing the same bytes twice, and making it fast to find a file again once it's in the vault.

## Features

- **Drag-and-drop upload** with per-file progress, multi-file support, and instant feedback on whether a file was new or a detected duplicate.
- **Content-based deduplication** – every upload is hashed with SHA-256. If identical content already exists, a lightweight reference row is created instead of writing the bytes to disk again, and the UI reports how much storage that saved.
- **Search & filtering** – search by filename and filter by file type, size range, and upload date, all combinable and backed by database indexes for fast lookups even as the vault grows.
- **Storage savings dashboard** – live stats on total files, duplicates detected, storage used, and storage saved.
- **Safe deletes** – deleting a file that other duplicate references point to promotes the oldest reference to own the physical file instead of breaking it; deleting a file's last copy removes it from disk too.
- **Friendly downloads** – files are stored on disk under generated UUIDs, but download responses restore the original filename.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, TanStack Query, Axios, Tailwind CSS, Heroicons |
| Backend | Django 5, Django REST Framework, django-filter |
| Database | SQLite |
| Infra | Docker & Docker Compose, Gunicorn, WhiteNoise |

## Project Structure

```
file-vault-system/
├── backend/                     # Django REST API
│   ├── core/                    # Project settings & root URLs
│   ├── files/                   # File vault app
│   │   ├── models.py            # File model + hashing helper
│   │   ├── serializers.py       # DRF serializers
│   │   ├── views.py             # Upload/dedup, search/filter, stats, delete, download
│   │   ├── filters.py           # django-filter FilterSet powering search & filters
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── tests.py             # Dedup, search/filter, and delete-promotion tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # React application
│   └── src/
│       ├── components/          # FileUpload, FileStats, FileSearch, FileList
│       ├── services/api.ts      # Axios client
│       ├── types/file.ts        # Shared TypeScript types
│       ├── hooks/                # useDebouncedValue
│       └── utils/format.ts      # Byte/date formatting helpers
├── docker-compose.yml
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

## How Deduplication Works

Every upload is streamed through a SHA-256 hash before it's saved (`files/models.py::compute_file_hash`). The API then checks whether a **non-duplicate** file with that hash already exists:

- **New content** → the file is written to `media/uploads/<uuid>.<ext>` and a `File` row is created with its hash.
- **Matching content** → a new `File` row is created that points at the existing row via `original` and stores **no file of its own**. The response tells the client how many bytes were saved.

Deleting a file that other rows depend on doesn't orphan them: `FileViewSet._delete_instance` promotes the oldest duplicate to own the physical file before removing the requested row, and only unlinks the file from disk when it truly has no more references.

`GET /api/files/stats/` aggregates this into `storage_used_bytes` (bytes actually on disk), `storage_saved_bytes` (bytes avoided thanks to dedup), and a `savings_percentage`.

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
| `GET` | `/api/files/` | List files (paginated, filterable, see above) |
| `POST` | `/api/files/` | Upload a file (`multipart/form-data`, field `file`) |
| `GET` | `/api/files/<id>/` | File metadata |
| `DELETE` | `/api/files/<id>/` | Delete a file (promotes a duplicate if needed) |
| `GET` | `/api/files/<id>/download/` | Download the file with its original filename |
| `GET` | `/api/files/stats/` | Aggregate storage & dedup stats |
| `GET` | `/api/files/file_types/` | Distinct file extensions currently stored (for filter UI) |

## Running Tests

```bash
cd backend
python manage.py test
```

Covers: new uploads, duplicate detection, mixed-content uploads, storage-savings stats, search, filtering (including combined filters), and delete-with-promotion behavior.

## Configuration

Both apps read configuration from environment variables (see `backend/.env.example` and `frontend/.env.example`):

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `MAX_UPLOAD_SIZE_BYTES` (backend)
- `REACT_APP_API_URL` (frontend)

## License

MIT — see [LICENSE](LICENSE).
