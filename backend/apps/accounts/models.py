from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.permissions import Role


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.CHOICES, default=Role.AGENT, db_index=True)
    branch = models.ForeignKey(
        "core.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    phone = models.CharField(max_length=15, blank=True)

    class Meta:
        ordering = ["username"]

    def clean(self):
        if self.role in (Role.AGENT, Role.BRANCH_MANAGER) and not self.branch_id:
            raise ValidationError({"branch": "Agents and branch managers must belong to a branch."})

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.display_name} ({self.role})"
