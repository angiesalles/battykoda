"""
Merge migration for potentially conflicting migrations.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0047_merge_recording_uniqueness'),
        ('battycoda_app', '0046_create_source_segments_for_tasks'),
    ]

    operations = [
    ]