from django.db import migrations, models
import django.db.models.deletion


def migrate_segmentations(apps, schema_editor):
    """
    For each recording with a segmentation, we need to:
    1. Create a new segmentation with ForeignKey
    2. Set the same attributes as the old segmentation
    3. Link all segments to the new segmentation
    """
    Recording = apps.get_model('battycoda_app', 'Recording')
    Segmentation = apps.get_model('battycoda_app', 'Segmentation')
    Segment = apps.get_model('battycoda_app', 'Segment')
    DetectionRun = apps.get_model('battycoda_app', 'DetectionRun')
    
    # For each recording, find the existing one-to-one segmentation
    for recording in Recording.objects.all():
        try:
            # Try to get the existing segmentation (from the old OneToOneField)
            old_segmentation = Segmentation.objects.get(recording_id=recording.id)
            
            # Update the recording_fk field to point to the recording
            old_segmentation.recording_fk_id = recording.id
            old_segmentation.is_active = True
            old_segmentation.save()
            
            # Find all segments for this recording and link them to the segmentation
            segments = Segment.objects.filter(recording=recording)
            for segment in segments:
                segment.segmentation = old_segmentation
                segment.save()
                
        except Segmentation.DoesNotExist:
            # No old segmentation exists, nothing to migrate
            pass
    
    # Update DetectionRun references
    for run in DetectionRun.objects.all():
        if hasattr(run, 'segmentation_id') and run.segmentation_id:
            # The segmentation_id is maintained during the migration
            # No need to change DetectionRun references
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0043_merge_20250327_1442'),
    ]

    operations = [
        # Step 1: Add new fields to Segmentation
        migrations.AddField(
            model_name='segmentation',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether this is the currently active segmentation for the recording'),
        ),
        migrations.AddField(
            model_name='segmentation',
            name='name',
            field=models.CharField(default='Default Segmentation', help_text='Descriptive name for this segmentation run', max_length=255),
        ),
        
        # Step 2: Create a new field for the ForeignKey relationship
        migrations.AddField(
            model_name='segmentation',
            name='recording_fk',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='segmentations_new', to='battycoda_app.recording'),
        ),
        
        # Step 3: Add field to Segment for segmentation relationship (nullable temporarily)
        migrations.AddField(
            model_name='segment',
            name='segmentation',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='segments', to='battycoda_app.segmentation'),
        ),
        
        # Step 4: Run custom migration to copy data
        migrations.RunPython(
            code=migrate_segmentations,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Step 5: Make the segmentation field non-nullable
        migrations.AlterField(
            model_name='segment',
            name='segmentation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segments', to='battycoda_app.segmentation'),
        ),
        
        # Step 6: Make recording_fk non-null
        migrations.AlterField(
            model_name='segmentation',
            name='recording_fk',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segmentations', to='battycoda_app.recording'),
        ),
        
        # Step 7: Remove the original OneToOneField
        migrations.RemoveField(
            model_name='segmentation',
            name='recording',
        ),
        
        # Step 8: Rename recording_fk to recording
        migrations.RenameField(
            model_name='segmentation',
            old_name='recording_fk',
            new_name='recording',
        ),
    ]