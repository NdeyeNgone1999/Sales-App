# Generated migration

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Dataset name', max_length=255)),
                ('source_type', models.CharField(choices=[('upload', 'Upload'), ('stored', 'Stored')], default='upload', help_text='Source type: upload or stored demo', max_length=10)),
                ('file', models.FileField(blank=True, help_text='Uploaded file (for upload type)', null=True, upload_to='datasets/')),
                ('stored_key', models.CharField(blank=True, help_text='Stored dataset key (for stored type)', max_length=255, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Dataset',
                'verbose_name_plural': 'Datasets',
                'ordering': ['-created_at'],
            },
        ),
    ]
