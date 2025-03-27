# Generated by Django 5.1.7 on 2025-03-26 21:19

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("battycoda_app", "0025_rename_team_to_group"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="classifier",
            name="group",
            field=models.ForeignKey(
                blank=True,
                help_text="Group that owns this classifier. If null, it's available to all groups",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="classifiers",
                to="battycoda_app.group",
            ),
        ),
        migrations.AlterField(
            model_name="groupmembership",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="group_memberships", to="battycoda_app.group"
            ),
        ),
        migrations.AlterField(
            model_name="groupmembership",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="group_memberships",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="recording",
            name="group",
            field=models.ForeignKey(
                help_text="Group that owns this recording",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="recordings",
                to="battycoda_app.group",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="is_admin",
            field=models.BooleanField(
                default=False, help_text="Designates whether this user is an administrator of their group"
            ),
        ),
        migrations.CreateModel(
            name="SegmentationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_id", models.CharField(help_text="Celery task ID", max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In Progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("progress", models.FloatField(default=0, help_text="Progress percentage (0-100)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("min_duration_ms", models.IntegerField(default=10)),
                ("smooth_window", models.IntegerField(default=3)),
                ("threshold_factor", models.FloatField(default=0.5)),
                ("segments_created", models.IntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="segmentation_jobs",
                        to="battycoda_app.recording",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
