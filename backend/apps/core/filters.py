import django_filters


class DateRangeFilterSet(django_filters.FilterSet):
    """Adds ?date_from=&date_to= on the model's `date_field` (a DateTimeField or DateField)."""

    date_field = "created_at"
    is_datetime = True

    date_from = django_filters.DateFilter(method="filter_date_from")
    date_to = django_filters.DateFilter(method="filter_date_to")

    def _lookup(self, op):
        return f"{self.date_field}__date__{op}" if self.is_datetime else f"{self.date_field}__{op}"

    def filter_date_from(self, qs, name, value):
        return qs.filter(**{self._lookup("gte"): value})

    def filter_date_to(self, qs, name, value):
        return qs.filter(**{self._lookup("lte"): value})
