# Generated by Django 5.1.7 on 2025-03-27 01:40

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("battycoda_app", "0033_update_taskbatch_uniqueness"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Segmentation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "task_id",
                    models.CharField(
                        blank=True, help_text="Celery task ID for automated segmentation", max_length=100, null=True
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In Progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="completed",
                        max_length=20,
                    ),
                ),
                ("progress", models.FloatField(default=100, help_text="Progress percentage (0-100)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("min_duration_ms", models.IntegerField(default=10)),
                ("smooth_window", models.IntegerField(default=3)),
                ("threshold_factor", models.FloatField(default=0.5)),
                ("segments_created", models.IntegerField(default=0)),
                (
                    "algorithm",
                    models.ForeignKey(
                        blank=True,
                        help_text="The algorithm used for this segmentation, if any",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="segmentations",
                        to="battycoda_app.segmentationalgorithm",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
                (
                    "recording",
                    models.OneToOneField(
                        help_text="The recording this segmentation belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="segmentation",
                        to="battycoda_app.recording",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.DeleteModel(
            name="SegmentationJob",
        ),
    ]
