import uuid

import django.db.models.deletion
from django.db import migrations, models

import files.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="File",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("file", models.FileField(blank=True, null=True, upload_to=files.models.file_upload_path)),
                ("original_filename", models.CharField(max_length=255)),
                ("file_type", models.CharField(blank=True, max_length=100)),
                ("content_type", models.CharField(blank=True, max_length=150)),
                ("size", models.BigIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("hash", models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                (
                    "original",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="duplicates",
                        to="files.file",
                    ),
                ),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["hash"], name="files_file_hash_d5ecb0_idx"),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["original_filename"], name="files_file_origina_63129f_idx"),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["file_type"], name="files_file_file_ty_2d7e73_idx"),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["size"], name="files_file_size_6009e9_idx"),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(fields=["uploaded_at"], name="files_file_uploade_726d10_idx"),
        ),
    ]
