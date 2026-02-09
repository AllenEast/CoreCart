from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    phone = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.username or self.phone
