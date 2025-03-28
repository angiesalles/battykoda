from django.db import migrations


def create_dummy_classifier(apps, schema_editor):
    """Create a dummy classifier that assigns equal probability to all call types"""
    Classifier = apps.get_model('battycoda_app', 'Classifier')
    
    # Check if the classifier already exists
    if not Classifier.objects.filter(name='Dummy Classifier').exists():
        # Create the new dummy classifier
        Classifier.objects.create(
            name='Dummy Classifier',
            description='A dummy classifier that assigns equal probability to all call types. '
                       'This is useful for testing and creating baseline results.',
            response_format='full_probability',
            celery_task='battycoda_app.audio.tasks.run_dummy_classifier',
            is_active=True,
            service_url='http://localhost',  # Set a dummy URL to avoid None errors
            endpoint='/dummy'
        )


def remove_dummy_classifier(apps, schema_editor):
    """Remove the dummy classifier"""
    Classifier = apps.get_model('battycoda_app', 'Classifier')
    Classifier.objects.filter(name='Dummy Classifier').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0040_remove_segment_call_type'),
    ]

    operations = [
        migrations.RunPython(create_dummy_classifier, remove_dummy_classifier),
    ]