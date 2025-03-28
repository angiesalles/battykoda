# Generated manually

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('battycoda_app', '0045_add_recording_sample_rate'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='recording',
            unique_together=set(),
        ),
    ]