from rest_framework import serializers

from .models import AuditLog, Branch


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "code", "name", "address", "is_active"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_name", "action", "entity_type", "entity_id", "before", "after",
                  "ip_address", "request_id", "created_at"]
