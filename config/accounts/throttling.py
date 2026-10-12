import hashlib
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class AdminRecoveryIPRateThrottle(AnonRateThrottle):
    """Rate limit admin recovery requests per IP address."""
    scope = "admin_recovery_ip"
    rate = "10/minute"


class AdminRecoveryEmailRateThrottle(SimpleRateThrottle):
    """Rate limit admin recovery requests per target email address."""
    scope = "admin_recovery_email"
    rate = "5/minute"

    def get_cache_key(self, request, view):
        if not hasattr(request, "data") or not isinstance(request.data, dict):
            return None
        email = request.data.get("email")
        if not email or not isinstance(email, str):
            return None
        email_normalized = email.strip().lower()
        if not email_normalized:
            return None
        ident = hashlib.sha256(email_normalized.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
