"""Authenticated file-vault API with content deduplication and vector search."""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404
from django.utils.text import get_valid_filename
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import FileFilter
from .models import File, StoredBlob, compute_file_hash
from .serializers import FileSerializer, FileStatsSerializer
from .services import (
    EmbeddingUnavailable,
    build_document_embedding,
    cosine_similarity,
    embed_text,
)


class FileViewSet(viewsets.ModelViewSet):
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = FileFilter
    ordering_fields = [
        ("uploaded_at", "uploaded_at"),
        ("blob__size", "size"),
        ("original_filename", "original_filename"),
    ]
    ordering = ["-uploaded_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return File.objects.none()
        return (
            File.objects.filter(owner=user)
            .select_related("blob")
            .annotate(
                same_owner_reference_count=Count(
                    "blob__references",
                    filter=Q(blob__references__owner=user),
                    distinct=True,
                )
            )
        )

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
        blob = StoredBlob.objects.filter(sha256=file_hash).first()
        reused_blob = blob is not None

        if blob is None:
            try:
                extracted_text, embedding = build_document_embedding(
                    file_obj,
                    file_type,
                    content_type,
                )
            except EmbeddingUnavailable as exc:
                return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            candidate = StoredBlob(
                file=file_obj,
                sha256=file_hash,
                size=file_obj.size,
                content_type=content_type,
                extracted_text=extracted_text,
                embedding=embedding,
            )
            try:
                with transaction.atomic():
                    candidate.save(force_insert=True)
                blob = candidate
            except IntegrityError:
                if candidate.file:
                    candidate.file.delete(save=False)
                blob = StoredBlob.objects.get(sha256=file_hash)
                reused_blob = True

        reference = File.objects.create(
            owner=request.user,
            blob=blob,
            original_filename=file_obj.name,
            file_type=file_type,
            reused_blob=reused_blob,
        )
        serializer = self.get_serializer(reference)
        message = (
            f"Identical content already existed; reused its stored blob and saved {file_obj.size} bytes."
            if reused_blob
            else "File uploaded and indexed successfully."
        )
        return Response(
            {"data": serializer.data, "duplicate": reused_blob, "message": message},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        reference = self.get_object()
        blob_id = reference.blob_id
        with transaction.atomic():
            reference.delete()
            blob = StoredBlob.objects.select_for_update().filter(pk=blob_id).first()
            if blob and not blob.references.exists():
                blob.file.delete(save=False)
                blob.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        reference = self.get_object()
        target = reference.effective_file()
        if not target:
            raise Http404("File content not found.")
        filename = get_valid_filename(reference.original_filename) or "download"
        return FileResponse(target.open("rb"), as_attachment=True, filename=filename)

    @action(detail=False, methods=["get"], url_path="semantic-search")
    def semantic_search(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"error": "Provide a non-empty q parameter."}, status=400)
        try:
            query_embedding = embed_text(query)
        except EmbeddingUnavailable as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        candidate_limit = getattr(settings, "SEMANTIC_SEARCH_CANDIDATE_LIMIT", 1000)
        candidates = list(
            self.filter_queryset(self.get_queryset())
            .filter(blob__embedding__isnull=False)[:candidate_limit]
        )
        for reference in candidates:
            reference.semantic_score = cosine_similarity(
                query_embedding,
                reference.blob.embedding,
            )
        candidates.sort(key=lambda item: item.semantic_score, reverse=True)

        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
        except ValueError:
            return Response({"error": "limit must be an integer."}, status=400)
        results = candidates[:limit]
        return Response(
            {
                "query": query,
                "count": len(results),
                "next": None,
                "previous": None,
                "results": self.get_serializer(results, many=True).data,
            }
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        references = self.get_queryset()
        totals = references.aggregate(
            total_files=Count("id"),
            total_uploaded_bytes=Sum("blob__size"),
        )
        blob_ids = references.values_list("blob_id", flat=True).distinct()
        unique = StoredBlob.objects.filter(id__in=blob_ids).aggregate(
            unique_files=Count("id"),
            storage_used_bytes=Sum("size"),
        )
        total_files = totals["total_files"] or 0
        unique_files = unique["unique_files"] or 0
        total_uploaded = totals["total_uploaded_bytes"] or 0
        storage_used = unique["storage_used_bytes"] or 0
        storage_saved = max(total_uploaded - storage_used, 0)
        savings_percentage = round(storage_saved * 100 / total_uploaded, 2) if total_uploaded else 0.0

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

    @action(detail=False, methods=["get"])
    def file_types(self, request):
        types = (
            self.get_queryset()
            .exclude(file_type="")
            .order_by("file_type")
            .values_list("file_type", flat=True)
            .distinct()
        )
        return Response(list(types))
