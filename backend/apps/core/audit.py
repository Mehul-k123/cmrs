import json
import logging

from django.core.serializers.json import DjangoJSONEncoder

from .middleware import get_request_context
from .models import AuditLog

logger = logging.getLogger("cmrs.audit")


def _jsonable(data):
    if data is None:
        return None
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def record_audit(actor, action: str, instance, before: dict | None = None, after: dict | None = None):
    ctx = get_request_context()
    entry = AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity_type=instance.__class__.__name__,
        entity_id=str(instance.pk),
        before=_jsonable(before),
        after=_jsonable(after),
        ip_address=ctx.get("ip"),
        request_id=ctx.get("request_id", ""),
    )
    logger.info("audit action=%s entity=%s#%s", action, entry.entity_type, entry.entity_id)
    return entry
