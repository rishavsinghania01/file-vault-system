"""Database models for physical blobs and user-visible file references."""

import hashlib
import os
import uuid

from django.conf import settings
from django.db import models


def _generated_upload_path(directory, filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    generated_name = str(uuid.uuid4())
    if extension:
        generated_name = f"{generated_name}.{extension}"
    return os.path.join(directory, generated_name)


def file_upload_path(instance, filename):
    """Compatibility callable used by the original migration."""
    return _generated_upload_path("uploads", filename)


def blob_upload_path(instance, filename):
    """Generate a storage name that does not expose the uploaded filename."""
    return _generated_upload_path("blobs", filename)


def compute_file_hash(file_obj, chunk_size=1024 * 1024):
    """Return a SHA-256 digest without loading the complete upload into memory."""
    hasher = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(chunk_size), b""):
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()


class StoredBlob(models.Model):
    """One physical object, shared by references with identical content."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=blob_upload_path)
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    size = models.BigIntegerField()
    content_type = models.CharField(max_length=150, blank=True)
    extracted_text = models.TextField(blank=True)
    embedding = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.sha256


class File(models.Model):
    """A user-owned filename and metadata reference to a stored blob."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="vault_files",
    )
    blob = models.ForeignKey(
        StoredBlob,
        null=True,
        on_delete=models.PROTECT,
        related_name="references",
    )
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reused_blob = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["owner", "uploaded_at"], name="files_file_owner_upl_idx"),
            models.Index(fields=["owner", "original_filename"], name="files_file_owner_name_idx"),
            models.Index(fields=["owner", "file_type"], name="files_file_owner_type_idx"),
        ]

    def __str__(self):
        return self.original_filename

    @property
    def is_duplicate(self):
        return self.reused_blob

    def effective_file(self):
        return self.blob.file if self.blob_id and self.blob else None
