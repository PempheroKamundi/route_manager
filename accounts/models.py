from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    """Model to hold user profile details"""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
