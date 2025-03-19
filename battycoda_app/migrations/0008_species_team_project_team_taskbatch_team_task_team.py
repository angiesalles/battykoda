# Generated by Django 5.1.7 on 2025-03-18 15:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0007_team_userprofile_team_userprofile_is_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='species',
            name='team',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='species', to='battycoda_app.team'),
        ),
        migrations.AddField(
            model_name='project',
            name='team',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='projects', to='battycoda_app.team'),
        ),
        migrations.AddField(
            model_name='taskbatch',
            name='team',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='task_batches', to='battycoda_app.team'),
        ),
        migrations.AddField(
            model_name='task',
            name='team',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='battycoda_app.team'),
        ),
    ]