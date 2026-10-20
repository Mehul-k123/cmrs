from django.db import models


class MoneyField(models.DecimalField):
    """All monetary values: NUMERIC(14, 2). Never use FloatField for money."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, "apps.core.fields.MoneyField", args, kwargs
