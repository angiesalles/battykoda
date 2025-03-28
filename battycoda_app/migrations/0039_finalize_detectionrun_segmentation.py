# Generated manually for the second part of the migration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0038_update_detectionrun_for_segments'),
    ]

    operations = [
        # Since this is a new feature implementation, we can remove the old fields
        # In a real migration with data, we would add a data migration to copy data
        migrations.RemoveField(
            model_name='detectionresult',
            name='task',
        ),
        migrations.RemoveField(
            model_name='detectionrun',
            name='batch',
        ),
    ]
