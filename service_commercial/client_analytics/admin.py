from django.contrib import admin
from .models import Dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'created_at', 'updated_at']
    list_filter = ['source_type', 'created_at']
    search_fields = ['name', 'stored_key']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'source_type')
        }),
        ('Source', {
            'fields': ('file', 'stored_key'),
            'description': 'Pour upload: renseigner file. Pour stored: renseigner stored_key.'
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
