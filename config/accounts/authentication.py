import hashlib
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import UserSecurityStatus


class SecureJWTAuthentication(JWTAuthentication):
    """
    Subclasses SimpleJWT's JWTAuthentication to enforce token revocation
    when an Admin or user undergoes a password reset.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        # 1. Verify password hash fingerprint if embedded in token
        token_pwd_hash = validated_token.get("pwd_hash")
        current_pwd_hash = hashlib.sha256(user.password.encode("utf-8")).hexdigest()[:16]
        if token_pwd_hash is not None and token_pwd_hash != current_pwd_hash:
            raise exceptions.AuthenticationFailed(
                "Token has been revoked due to password reset.",
                code="token_revoked"
            )

        # 2. Verify token issued-at timestamp against revocation timestamp
        token_iat = validated_token.get("iat")
        if token_iat is not None:
            security_status = getattr(user, "security_status", None)
            if not security_status:
                security_status = UserSecurityStatus.objects.filter(user=user).first()

            if security_status and security_status.jwt_revoked_before:
                revoked_ts = security_status.jwt_revoked_before.timestamp()
                if token_iat < revoked_ts:
                    raise exceptions.AuthenticationFailed(
                        "Token has been revoked due to password reset.",
                        code="token_revoked"
                    )

        return user
