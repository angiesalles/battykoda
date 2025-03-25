from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0024_recording_segment'),
    ]

    operations = [
        # Rename Team model to Group
        migrations.RenameModel(
            old_name='Team',
            new_name='Group',
        ),
        
        # Rename TeamInvitation model to GroupInvitation
        migrations.RenameModel(
            old_name='TeamInvitation',
            new_name='GroupInvitation',
        ),
        
        # Rename TeamMembership model to GroupMembership
        migrations.RenameModel(
            old_name='TeamMembership',
            new_name='GroupMembership',
        ),
        
        # Rename team field in GroupInvitation to group
        migrations.RenameField(
            model_name='GroupInvitation',
            old_name='team',
            new_name='group',
        ),
        
        # Rename team field in GroupMembership to group
        migrations.RenameField(
            model_name='GroupMembership',
            old_name='team',
            new_name='group',
        ),
        
        # Rename team field in UserProfile to group
        migrations.RenameField(
            model_name='UserProfile',
            old_name='team',
            new_name='group',
        ),
        
        # Rename team field in all models that reference it
        migrations.RenameField(
            model_name='Classifier',
            old_name='team',
            new_name='group',
        ),
        
        migrations.RenameField(
            model_name='DetectionRun',
            old_name='team',
            new_name='group',
        ),
        
        migrations.RenameField(
            model_name='Project',
            old_name='team',
            new_name='group',
        ),
        
        migrations.RenameField(
            model_name='Recording',
            old_name='team',
            new_name='group',
        ),
        
        migrations.RenameField(
            model_name='Species',
            old_name='team',
            new_name='group',
        ),
        
        migrations.RenameField(
            model_name='Task',
            old_name='team',
            new_name='group',
        ),
        
        migrations.RenameField(
            model_name='TaskBatch',
            old_name='team',
            new_name='group',
        ),
    ]