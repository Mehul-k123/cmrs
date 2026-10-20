from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.permissions import Role

from .models import User


class UserSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)
    display_name = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "display_name", "email", "phone", "role",
                  "branch", "branch_name", "is_active", "password"]

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if role in (Role.AGENT, Role.BRANCH_MANAGER) and not branch:
            raise serializers.ValidationError({"branch": "Agents and branch managers must belong to a branch."})
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    """Returns tokens plus the user profile so the SPA can render role-based navigation immediately."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["branch"] = user.branch_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
