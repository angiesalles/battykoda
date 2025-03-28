# Generated manually to avoid interactive migration issues

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0037_add_manually_edited_flag'),
    ]

    operations = [
        # Add new field with null=True initially
        migrations.AddField(
            model_name='detectionrun',
            name='segmentation',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='detection_runs', to='battycoda_app.segmentation'),
        ),
        # Add segment field to DetectionResult with null=True initially
        migrations.AddField(
            model_name='detectionresult',
            name='segment',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='detection_results', to='battycoda_app.segment'),
        ),
        # Update Meta options for DetectionResult
        migrations.AlterModelOptions(
            name='detectionresult',
            options={'ordering': ['segment__onset']},
        ),
    ]
