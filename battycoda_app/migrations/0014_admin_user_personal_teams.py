from django.db import migrations

def make_users_admins_in_own_teams(apps, schema_editor):
    """Make sure all users are admins in their personal teams"""
    UserProfile = apps.get_model('battycoda_app', 'UserProfile')
    User = apps.get_model('auth', 'User')
    
    # Iterate over all user profiles
    for user in User.objects.all():
        try:
            profile = UserProfile.objects.get(user=user)
            
            # If user has a team and it's their personal team, make them an admin
            if profile.team and profile.team.name.startswith(f"{user.username}'s Team"):
                profile.is_admin = True
                profile.save()
        except UserProfile.DoesNotExist:
            # Skip if profile doesn't exist
            pass

class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0013_update_user_registration'),
    ]

    operations = [
        migrations.RunPython(make_users_admins_in_own_teams),
    ]