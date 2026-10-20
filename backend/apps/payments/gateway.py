"""Payment gateway abstraction.

`MockGateway` simulates a provider (Razorpay/Cashfree-style) so the reconciliation flow for digital
payments can be demonstrated without real keys. A real provider only needs to implement
`create_order` and send webhooks signed with HMAC-SHA256 over the raw body."""

import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from typing import Protocol

from django.conf import settings


def sign(body: bytes, secret: str | None = None) -> str:
    secret = (secret or settings.PAYMENT_GATEWAY_WEBHOOK_SECRET).encode()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str) -> bool:
    return bool(signature) and hmac.compare_digest(sign(body), signature)


class GatewayClient(Protocol):
    """What a payment provider adapter must implement to plug into the reconciliation flow."""

    name: str

    def create_order(self, amount: Decimal, receipt: str) -> dict: ...


class MockGateway:
    """In-process stand-in for a real provider. Also builds signed events so the demo can simulate webhooks."""

    name = "mockpay"

    def create_order(self, amount: Decimal, receipt: str) -> dict:
        ref = f"mock_{uuid.uuid4().hex[:18]}"
        return {"gateway_ref": ref, "payment_url": f"https://mockpay.local/pay/{ref}", "amount": str(amount)}

    def build_event(self, event_type: str, data: dict) -> tuple[bytes, str]:
        body = json.dumps({"id": f"evt_{uuid.uuid4().hex[:18]}", "type": event_type, "data": data}).encode()
        return body, sign(body)


gateway: MockGateway = MockGateway()
