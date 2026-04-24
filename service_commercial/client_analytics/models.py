from django.db import models
from django.utils import timezone


class Dataset(models.Model):
    """Model representing an uploaded dataset"""

    SOURCE_TYPE_CHOICES = [
        ('upload', 'Upload'),
    ]

    PROCESSING_STATUS_CHOICES = [
        ('done', 'Done'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('error', 'Error'),
    ]

    name = models.CharField(max_length=255, help_text="Dataset name")
    source_type = models.CharField(
        max_length=10,
        choices=SOURCE_TYPE_CHOICES,
        default='upload',
        help_text="Source type: upload or stored demo"
    )
    file = models.FileField(
        upload_to='datasets/',
        help_text="Uploaded Excel file"
    )
    processing_status = models.CharField(
        max_length=10,
        choices=PROCESSING_STATUS_CHOICES,
        default='done',
        help_text="File processing status"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dataset"
        verbose_name_plural = "Datasets"

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"

    def get_file_path(self):
        """Return the full path to the file"""
        if self.file:
            return self.file.path
        return None
