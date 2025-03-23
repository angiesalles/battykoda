from django.db import migrations

def populate_team_memberships(apps, schema_editor):
    """Create TeamMembership records for all existing users based on their profiles."""
    UserProfile = apps.get_model('battycoda_app', 'UserProfile')
    TeamMembership = apps.get_model('battycoda_app', 'TeamMembership')
    
    # Get all user profiles
    profiles = UserProfile.objects.select_related('user', 'team').all()
    
    # Create membership records
    for profile in profiles:
        if profile.team:
            # Create a membership record if the user has a team and it doesn't exist already
            if not TeamMembership.objects.filter(user=profile.user, team=profile.team).exists():
                TeamMembership.objects.create(
                    user=profile.user,
                    team=profile.team,
                    is_admin=profile.is_admin
                )
                
def reverse_migration(apps, schema_editor):
    """Do nothing on reverse migration."""
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('battycoda_app', '0016_teammembership'),
    ]

    operations = [
        migrations.RunPython(populate_team_memberships, reverse_migration),
    ]