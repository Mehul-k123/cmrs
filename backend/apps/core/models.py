from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Branch(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "branches"

    def __str__(self):
        return f"{self.code} - {self.name}"


class AuditLog(models.Model):
    """Append-only record of every state change on financial entities."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    action = models.CharField(max_length=60, db_index=True)
    entity_type = models.CharField(max_length=60, db_index=True)
    entity_id = models.CharField(max_length=40, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Audit log entries are immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit log entries are immutable")
