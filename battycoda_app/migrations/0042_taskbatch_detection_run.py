from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0041_create_dummy_classifier'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskbatch',
            name='detection_run',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_batches', to='battycoda_app.detectionrun'),
        ),
    ]