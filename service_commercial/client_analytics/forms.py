from django import forms
from django.core.exceptions import ValidationError
from .models import Dataset
import os
from django.core.files.base import ContentFile
from io import BytesIO

# Workaround: openpyxl bug with 'biltinId' typo in some Excel files
from openpyxl.styles.named_styles import _NamedCellStyle
_original_ncs_init = _NamedCellStyle.__init__
def _patched_ncs_init(self, *args, **kwargs):
    if 'biltinId' in kwargs:
        kwargs['builtinId'] = kwargs.pop('biltinId')
    _original_ncs_init(self, *args, **kwargs)
_NamedCellStyle.__init__ = _patched_ncs_init


class UploadDatasetForm(forms.ModelForm):
    """Form for uploading a new dataset"""

    class Meta:
        model = Dataset
        fields = ['name', 'file']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du dataset'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.xlsx,.xls'
            })
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file extension
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ['.xlsx', '.xls']:
                raise ValidationError("Seuls les fichiers Excel (.xlsx, .xls) sont acceptés.")

            # Check file size (50MB max)
            if file.size > 50 * 1024 * 1024:
                raise ValidationError("Le fichier ne doit pas dépasser 50MB.")

        return file

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.source_type = 'upload'
        instance.processing_status = 'pending'

        if commit:
            instance.save()
        return instance


class SelectDatasetForm(forms.Form):
    """Form for selecting an existing dataset"""

    existing_dataset = forms.ModelChoiceField(
        queryset=Dataset.objects.all(),
        required=True,
        empty_label="Sélectionner un dataset...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Dataset existant'
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('existing_dataset'):
            raise ValidationError("Veuillez sélectionner un dataset existant.")
        return cleaned_data
