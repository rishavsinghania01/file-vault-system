from django.contrib import admin

from .models import File


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "file_type", "size", "uploaded_at", "is_duplicate")
    list_filter = ("file_type",)
    search_fields = ("original_filename", "hash")
    readonly_fields = ("id", "hash", "uploaded_at")

    @admin.display(boolean=True)
    def is_duplicate(self, obj):
        return obj.original_id is not None
