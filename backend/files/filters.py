import django_filters

from .models import File


class FileFilter(django_filters.FilterSet):
    """Backs the /api/files/ list endpoint's filtering options.

    All filters can be combined - e.g. ?file_type=pdf&min_size=1000&
    start_date=2024-01-01&end_date=2024-12-31&search=report
    """

    search = django_filters.CharFilter(field_name="original_filename", lookup_expr="icontains")
    file_type = django_filters.CharFilter(method="filter_file_type")
    min_size = django_filters.NumberFilter(field_name="size", lookup_expr="gte")
    max_size = django_filters.NumberFilter(field_name="size", lookup_expr="lte")
    start_date = django_filters.DateTimeFilter(field_name="uploaded_at", lookup_expr="gte")
    end_date = django_filters.DateTimeFilter(field_name="uploaded_at", lookup_expr="lte")

    class Meta:
        model = File
        fields = ["search", "file_type", "min_size", "max_size", "start_date", "end_date"]

    def filter_file_type(self, queryset, name, value):
        # Support comma separated values so the UI can offer a multi-select
        # "file type" filter, e.g. ?file_type=pdf,png,docx
        types = [t.strip().lower() for t in value.split(",") if t.strip()]
        if not types:
            return queryset
        return queryset.filter(file_type__in=types)
