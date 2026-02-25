from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        OPERATOR = "operator", "Operator"
        ADMIN = "admin", "Admin"

    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    address = models.TextField(blank=True)

    # Chat/support role (separate from is_staff/is_superuser)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER, db_index=True)

    @property
    def is_operator(self) -> bool:
        # Operators are allowed to work support queue.
        return self.role == self.Role.OPERATOR or self.is_staff or self.is_superuser

    def __str__(self):
        # Must always return a string to avoid admin/runtime errors.
        return self.username or self.phone or f"User#{self.pk}"
