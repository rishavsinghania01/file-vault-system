"""Data models for the File Vault System.

The `File` model backs both the physical, unique files stored on disk and
the lightweight "duplicate reference" rows created when a user uploads
content that already exists in the vault (see `views.FileViewSet.create`).

A duplicate reference has no `file` of its own - it points at the original
record via the `original` foreign key and is served from the original's
physical file. This is what powers the deduplication feature: identical
content is only ever written to storage once.
"""
import hashlib
import os
import uuid

from django.db import models


def file_upload_path(instance, filename):
    """Store uploads under media/uploads/<uuid>.<ext> to avoid name clashes."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    new_name = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())
    return os.path.join("uploads", new_name)


def compute_file_hash(file_obj, chunk_size=8192):
    """Compute a SHA-256 hash of a file-like object without loading it fully
    into memory, then rewind it so it can be read again afterwards."""
    hasher = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(chunk_size), b""):
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()


class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=file_upload_path, null=True, blank=True)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100, blank=True)
    content_type = models.CharField(max_length=150, blank=True)
    size = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    # When set, this row is a duplicate reference pointing at the File that
    # actually holds the physical content. Original files leave this null.
    original = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
    )

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["hash"]),
            models.Index(fields=["original_filename"]),
            models.Index(fields=["file_type"]),
            models.Index(fields=["size"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def __str__(self):
        return self.original_filename

    @property
    def is_duplicate(self):
        return self.original_id is not None

    def effective_file(self):
        """Return the FieldFile that actually holds this record's bytes -
        its own file, or (if it's a duplicate reference) the original's."""
        if self.file:
            return self.file
        if self.original_id and self.original and self.original.file:
            return self.original.file
        return None
