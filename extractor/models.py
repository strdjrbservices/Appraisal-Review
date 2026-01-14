from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} Profile'

class ExtractionResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    filename = models.CharField(max_length=255)
    section_name = models.CharField(max_length=100)
    extracted_data = models.JSONField(null=True, blank=True)
    backend_validation = models.JSONField(null=True, blank=True)
    frontend_validation = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('filename', 'section_name')

    def __str__(self):
        return f"{self.filename} - {self.section_name}"
