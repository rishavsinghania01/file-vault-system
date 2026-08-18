"""API views for the File Vault System.

Implements the two core features required by the product spec:

1. File deduplication - `FileViewSet.create` hashes every upload with
   SHA-256. If the content already exists, a lightweight "duplicate
   reference" row is created instead of storing the bytes again, and the
   `stats` action reports how much storage that has saved.
2. Search & filtering - `FileViewSet.list` (via `FileFilter`) supports
   searching by filename and filtering by file type, size range and upload
   date, all of which can be combined and are backed by database indexes.
"""
from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404
from django.utils.text import get_valid_filename
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import FileFilter
from .models import File, compute_file_hash
from .serializers import FileSerializer, FileStatsSerializer


class FileViewSet(viewsets.ModelViewSet):
    serializer_class = FileSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = FileFilter
    ordering_fields = ["uploaded_at", "size", "original_filename"]
    ordering = ["-uploaded_at"]

    def get_queryset(self):
        return File.objects.select_related("original").annotate(
            duplicate_count_annotated=Count("duplicates", distinct=True)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # -- Upload / dedup -----------------------------------------------
    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        max_upload_size = getattr(settings, "MAX_UPLOAD_SIZE", 100 * 1024 * 1024)
        if file_obj.size > max_upload_size:
            return Response(
                {"error": f"File exceeds the maximum allowed size of {max_upload_size} bytes."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_hash = compute_file_hash(file_obj)
        file_type = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
        content_type = getattr(file_obj, "content_type", "") or ""

        existing = File.objects.filter(hash=file_hash, original__isnull=True).first()

        if existing:
            duplicate = File.objects.create(
                original_filename=file_obj.name,
                file_type=file_type,
                content_type=content_type,
                size=file_obj.size,
                hash=file_hash,
                original=existing,
            )
            serializer = self.get_serializer(duplicate)
            return Response(
                {
                    "data": serializer.data,
                    "duplicate": True,
                    "message": (
                        f"Duplicate of '{existing.original_filename}' detected - "
                        f"reused the existing file and saved {file_obj.size} bytes of storage."
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        serializer = self.get_serializer(
            data={"file": file_obj, "original_filename": file_obj.name}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            hash=file_hash,
            file_type=file_type,
            content_type=content_type,
            size=file_obj.size,
        )
        return Response(
            {"data": serializer.data, "duplicate": False, "message": "File uploaded successfully."},
            status=status.HTTP_201_CREATED,
        )

    # -- Delete (with orphan promotion + physical cleanup) -------------
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._delete_instance(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _delete_instance(instance):
        """Delete a File row without ever losing a still-referenced physical
        file. If the row being deleted owns the physical file and has
        duplicate references pointing at it, ownership is promoted to the
        oldest duplicate before the row (and, if truly orphaned, the file
        on disk) is removed."""
        if instance.file:
            duplicates = instance.duplicates.all()
            promoted = duplicates.order_by("uploaded_at").first()
            if promoted:
                promoted.file.name = instance.file.name
                promoted.original = None
                promoted.save(update_fields=["file", "original"])
                duplicates.exclude(pk=promoted.pk).update(original=promoted)
                instance.file = None
                instance.delete()
            else:
                instance.file.delete(save=False)
                instance.delete()
        else:
            instance.delete()

    # -- Download (serves the correct bytes with the friendly filename) --
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        instance = self.get_object()
        target = instance.effective_file()
        if not target:
            raise Http404("File content not found.")
        filename = get_valid_filename(instance.original_filename) or "download"
        response = FileResponse(target.open("rb"), as_attachment=True, filename=filename)
        return response

    # -- Aggregate stats used to show storage savings -------------------
    @action(detail=False, methods=["get"])
    def stats(self, request):
        totals = File.objects.aggregate(
            total_files=Count("id"),
            unique_files=Count("id", filter=Q(original__isnull=True)),
            storage_used_bytes=Sum("size", filter=Q(original__isnull=True)),
            storage_saved_bytes=Sum("size", filter=Q(original__isnull=False)),
        )
        total_files = totals["total_files"] or 0
        unique_files = totals["unique_files"] or 0
        storage_used = totals["storage_used_bytes"] or 0
        storage_saved = totals["storage_saved_bytes"] or 0
        total_uploaded = storage_used + storage_saved
        savings_percentage = round((storage_saved / total_uploaded) * 100, 2) if total_uploaded else 0.0

        data = {
            "total_files": total_files,
            "unique_files": unique_files,
            "duplicate_files": total_files - unique_files,
            "storage_used_bytes": storage_used,
            "storage_saved_bytes": storage_saved,
            "total_uploaded_bytes": total_uploaded,
            "savings_percentage": savings_percentage,
        }
        return Response(FileStatsSerializer(data).data)

    # -- Distinct file types, used to populate the filter dropdown -------
    @action(detail=False, methods=["get"])
    def file_types(self, request):
        types = (
            File.objects.exclude(file_type="")
            .order_by("file_type")
            .values_list("file_type", flat=True)
            .distinct()
        )
        return Response(list(types))
