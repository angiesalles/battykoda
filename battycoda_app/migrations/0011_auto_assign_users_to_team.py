from django.db import migrations

def assign_users_to_team(apps, schema_editor):
    """Assign all existing users to the SallesLab team"""
    # Get the historical models
    UserProfile = apps.get_model('battycoda_app', 'UserProfile')
    Team = apps.get_model('battycoda_app', 'Team')
    
    # Get the SallesLab team (created in a previous migration)
    try:
        salles_lab = Team.objects.get(name="SallesLab")
        
        # Get all user profiles that don't have a team
        profiles = UserProfile.objects.filter(team__isnull=True)
        
        # Assign each profile to the SallesLab team
        for profile in profiles:
            profile.team = salles_lab
            profile.save()
    except Team.DoesNotExist:
        # If SallesLab team doesn't exist, we can't proceed
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0010_remove_existing_taskbatches'),
    ]

    operations = [
        migrations.RunPython(assign_users_to_team),
    ]