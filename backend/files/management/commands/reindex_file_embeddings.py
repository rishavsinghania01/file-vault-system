from django.core.management.base import BaseCommand, CommandError

from files.models import StoredBlob
from files.services import EmbeddingUnavailable, build_document_embedding


class Command(BaseCommand):
    help = "Extract text and rebuild semantic-search embeddings for stored blobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild embeddings that already exist.",
        )

    def handle(self, *args, **options):
        queryset = StoredBlob.objects.all()
        if not options["force"]:
            queryset = queryset.filter(embedding__isnull=True)

        indexed = 0
        skipped = 0
        for blob in queryset.iterator():
            try:
                with blob.file.open("rb") as source:
                    file_type = blob.file.name.rsplit(".", 1)[-1].lower()
                    text, embedding = build_document_embedding(
                        source,
                        file_type,
                        blob.content_type,
                    )
            except EmbeddingUnavailable as exc:
                raise CommandError(str(exc)) from exc

            if embedding:
                blob.extracted_text = text
                blob.embedding = embedding
                blob.save(update_fields=["extracted_text", "embedding"])
                indexed += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"Indexed {indexed} blobs; skipped {skipped} without searchable text.")
        )
