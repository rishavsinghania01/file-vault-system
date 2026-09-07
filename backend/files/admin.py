from django.contrib import admin

from .models import File, StoredBlob


@admin.register(StoredBlob)
class StoredBlobAdmin(admin.ModelAdmin):
    list_display = ("sha256", "size", "content_type", "created_at", "reference_count")
    search_fields = ("sha256",)
    readonly_fields = ("id", "sha256", "created_at")

    @admin.display(description="References")
    def reference_count(self, obj):
        return obj.references.count()


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "owner", "file_type", "uploaded_at", "reused_blob")
    list_filter = ("file_type", "reused_blob")
    search_fields = ("original_filename", "blob__sha256", "owner__username")
    readonly_fields = ("id", "uploaded_at")
