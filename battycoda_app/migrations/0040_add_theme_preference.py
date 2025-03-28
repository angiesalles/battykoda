from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0039_finalize_detectionrun_segmentation'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='theme',
            field=models.CharField(
                choices=[('default', 'Default - Red'), ('blue', 'Blue/Green')],
                default='default',
                help_text='Color theme preference',
                max_length=20
            ),
        ),
    ]