from rest_framework import serializers

from .models import File


class FileSerializer(serializers.ModelSerializer):
    """Read/write serializer used for list, retrieve and create responses."""

    file_url = serializers.SerializerMethodField()
    is_duplicate = serializers.SerializerMethodField()
    duplicate_count = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            "id",
            "file",
            "file_url",
            "original_filename",
            "file_type",
            "content_type",
            "size",
            "uploaded_at",
            "hash",
            "original",
            "is_duplicate",
            "duplicate_count",
        ]
        read_only_fields = [
            "id",
            "uploaded_at",
            "size",
            "hash",
            "original",
            "file_url",
            "content_type",
        ]
        extra_kwargs = {
            "file": {"write_only": True, "required": False},
        }

    def get_file_url(self, obj):
        target = obj.effective_file()
        if not target:
            return None
        request = self.context.get("request")
        url = target.url
        return request.build_absolute_uri(url) if request else url

    def get_is_duplicate(self, obj):
        return obj.is_duplicate

    def get_duplicate_count(self, obj):
        # Prefer an annotated value (set by the view's queryset) to avoid
        # issuing one extra query per row when listing files.
        annotated = getattr(obj, "duplicate_count_annotated", None)
        if annotated is not None:
            return annotated
        return obj.duplicates.count() if not obj.is_duplicate else 0


class FileStatsSerializer(serializers.Serializer):
    total_files = serializers.IntegerField()
    unique_files = serializers.IntegerField()
    duplicate_files = serializers.IntegerField()
    storage_used_bytes = serializers.IntegerField()
    storage_saved_bytes = serializers.IntegerField()
    total_uploaded_bytes = serializers.IntegerField()
    savings_percentage = serializers.FloatField()
