from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0039_finalize_detectionrun_segmentation'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='segment',
            name='call_type',
        ),
    ]