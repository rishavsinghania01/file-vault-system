import hashlib
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import files.models


def move_existing_files_into_blobs(apps, schema_editor):
    File = apps.get_model("files", "File")
    StoredBlob = apps.get_model("files", "StoredBlob")
    blobs_by_reference = {}

    for reference in File.objects.filter(original__isnull=True).iterator():
        digest = reference.hash or hashlib.sha256(str(reference.pk).encode()).hexdigest()
        blob = StoredBlob.objects.create(
            file=reference.file.name,
            sha256=digest,
            size=reference.size,
            content_type=reference.content_type,
        )
        reference.blob_id = blob.pk
        reference.reused_blob = False
        reference.save(update_fields=["blob", "reused_blob"])
        blobs_by_reference[reference.pk] = blob.pk

    for reference in File.objects.exclude(original__isnull=True).iterator():
        blob_id = blobs_by_reference.get(reference.original_id)
        if blob_id:
            reference.blob_id = blob_id
            reference.reused_blob = True
            reference.save(update_fields=["blob", "reused_blob"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("files", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoredBlob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file", models.FileField(upload_to=files.models.blob_upload_path)),
                ("sha256", models.CharField(db_index=True, max_length=64, unique=True)),
                ("size", models.BigIntegerField()),
                ("content_type", models.CharField(blank=True, max_length=150)),
                ("extracted_text", models.TextField(blank=True)),
                ("embedding", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="file",
            name="blob",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="references",
                to="files.storedblob",
            ),
        ),
        migrations.AddField(
            model_name="file",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="vault_files",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="file",
            name="reused_blob",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(move_existing_files_into_blobs, migrations.RunPython.noop),
        migrations.RemoveIndex(model_name="file", name="files_file_hash_d5ecb0_idx"),
        migrations.RemoveIndex(model_name="file", name="files_file_origina_63129f_idx"),
        migrations.RemoveIndex(model_name="file", name="files_file_file_ty_2d7e73_idx"),
        migrations.RemoveIndex(model_name="file", name="files_file_size_6009e9_idx"),
        migrations.RemoveIndex(model_name="file", name="files_file_uploade_726d10_idx"),
        migrations.RemoveField(model_name="file", name="content_type"),
        migrations.RemoveField(model_name="file", name="file"),
        migrations.RemoveField(model_name="file", name="hash"),
        migrations.RemoveField(model_name="file", name="original"),
        migrations.RemoveField(model_name="file", name="size"),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["owner", "uploaded_at"], name="files_file_owner_upl_idx"),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["owner", "original_filename"], name="files_file_owner_name_idx"),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["owner", "file_type"], name="files_file_owner_type_idx"),
        ),
    ]
