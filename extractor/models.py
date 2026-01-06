from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} Profile'

class ExtractedData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    section_name = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    validation_results = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'filename', 'section_name')

    def __str__(self):
        return f"{self.filename} - {self.section_name}"
