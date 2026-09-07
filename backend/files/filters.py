import django_filters

from .models import File


class FileFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(field_name="original_filename", lookup_expr="icontains")
    file_type = django_filters.CharFilter(method="filter_file_type")
    min_size = django_filters.NumberFilter(field_name="blob__size", lookup_expr="gte")
    max_size = django_filters.NumberFilter(field_name="blob__size", lookup_expr="lte")
    start_date = django_filters.DateTimeFilter(field_name="uploaded_at", lookup_expr="gte")
    end_date = django_filters.DateTimeFilter(field_name="uploaded_at", lookup_expr="lte")

    class Meta:
        model = File
        fields = ["search", "file_type", "min_size", "max_size", "start_date", "end_date"]

    def filter_file_type(self, queryset, name, value):
        types = [item.strip().lower() for item in value.split(",") if item.strip()]
        return queryset.filter(file_type__in=types) if types else queryset
