from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.urls import reverse
from rest_framework import serializers

from .models import File


class FileSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    file_url = serializers.SerializerMethodField()
    content_type = serializers.CharField(source="blob.content_type", read_only=True)
    size = serializers.IntegerField(source="blob.size", read_only=True)
    hash = serializers.CharField(source="blob.sha256", read_only=True)
    is_duplicate = serializers.BooleanField(source="reused_blob", read_only=True)
    duplicate_count = serializers.SerializerMethodField()
    semantic_score = serializers.SerializerMethodField()

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
            "is_duplicate",
            "duplicate_count",
            "semantic_score",
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get("request")
        path = reverse("file-download", kwargs={"pk": obj.pk})
        return request.build_absolute_uri(path) if request else path

    def get_duplicate_count(self, obj):
        count = getattr(obj, "same_owner_reference_count", None)
        if count is not None:
            return max(count - 1, 0)
        if not obj.owner_id or not obj.blob_id:
            return 0
        return obj.blob.references.filter(owner_id=obj.owner_id).exclude(pk=obj.pk).count()

    def get_semantic_score(self, obj):
        score = getattr(obj, "semantic_score", None)
        return round(score, 4) if score is not None else None


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_username(self, value):
        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)


class FileStatsSerializer(serializers.Serializer):
    total_files = serializers.IntegerField()
    unique_files = serializers.IntegerField()
    duplicate_files = serializers.IntegerField()
    storage_used_bytes = serializers.IntegerField()
    storage_saved_bytes = serializers.IntegerField()
    total_uploaded_bytes = serializers.IntegerField()
    savings_percentage = serializers.FloatField()
