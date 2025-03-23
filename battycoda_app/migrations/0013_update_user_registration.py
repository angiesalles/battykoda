from django.db import migrations
from django.contrib.auth.models import User

def update_user_registration(apps, schema_editor):
    Team = apps.get_model('battycoda_app', 'Team')
    UserProfile = apps.get_model('battycoda_app', 'UserProfile')
    
    # The create_user_profile signal won't fire for migrations, so we don't need to disable it

def forwards_func(apps, schema_editor):
    pass  # The actual changes will be made in the model signals

class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0012_deprecate_cloudflare_fields'),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]