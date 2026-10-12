from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class AdminRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'confirm_password',
        ]
        read_only_fields = ['id']

    def validate_username(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Username is required.")
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required.")
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        if not password:
            raise serializers.ValidationError({"password": "Password is required."})

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        username = attrs.get('username', '')
        email = attrs.get('email', '')
        first_name = attrs.get('first_name', '')
        last_name = attrs.get('last_name', '')

        user_temp = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        try:
            validate_password(password, user=user_temp)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')

        # Create staff Admin user, not superuser
        user = User.objects.create_user(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=password,
            is_staff=True,
            is_superuser=False
        )
        return user


class AdminForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required.")
        return value.strip().lower()


class AdminVerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required.")
        return value.strip().lower()

    def validate_otp(self, value):
        value = value.strip()
        if len(value) != 6 or not value.isdigit():
            raise serializers.ValidationError("OTP must be a 6-digit numeric code.")
        return value


class AdminResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField(required=True, trim_whitespace=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_reset_token(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Reset token is required.")
        return value.strip()

    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        return attrs


class AdminResendResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required.")
        return value.strip().lower()

from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer as BaseTokenObtainPairSerializer,
    TokenRefreshSerializer as BaseTokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from .models import UserSecurityStatus
import hashlib


class SecureTokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    """
    JWT obtain pair serializer that embeds a password hash fingerprint
    in the access token for immediate revocation upon password changes.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["pwd_hash"] = hashlib.sha256(user.password.encode("utf-8")).hexdigest()[:16]
        return token
class SecureTokenRefreshSerializer(BaseTokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        try:
            refresh_token = RefreshToken(attrs["refresh"])
            user_id = refresh_token.payload.get("user_id")
            token_iat = refresh_token.payload.get("iat")
            token_pwd_hash = refresh_token.payload.get("pwd_hash")
            if user_id:
                user = User.objects.filter(id=user_id).first()
                if user and token_pwd_hash:
                    current_pwd_hash = hashlib.sha256(user.password.encode("utf-8")).hexdigest()[:16]
                    if token_pwd_hash != current_pwd_hash:
                        raise InvalidToken("Token has been revoked due to password reset.")

                if token_iat:
                    security_status = UserSecurityStatus.objects.filter(user_id=user_id).first()
                    if security_status and security_status.jwt_revoked_before:
                        if token_iat < security_status.jwt_revoked_before.timestamp():
                            raise InvalidToken("Token has been revoked due to password reset.")
        except Exception as e:
            if isinstance(e, InvalidToken):
                raise e
        return data

