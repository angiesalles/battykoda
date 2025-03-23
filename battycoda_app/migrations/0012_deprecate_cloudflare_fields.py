# Generated by Django 5.1.7 on 2025-03-22 00:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0011_auto_assign_users_to_team'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='cloudflare_id',
            field=models.CharField(blank=True, help_text='Deprecated - kept for data compatibility', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='is_cloudflare_user',
            field=models.BooleanField(default=False, help_text='Deprecated - kept for data compatibility'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='cloudflare_email',
            field=models.EmailField(blank=True, help_text='Deprecated - kept for data compatibility', max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='last_cloudflare_login',
            field=models.DateTimeField(blank=True, help_text='Deprecated - kept for data compatibility', null=True),
        ),
    ]