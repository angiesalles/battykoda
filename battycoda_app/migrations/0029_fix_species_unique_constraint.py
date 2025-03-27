from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battycoda_app', '0028_create_default_segmentation_algorithms'),
    ]

    operations = [
        # Remove the unique constraint from the name field
        migrations.AlterField(
            model_name='species',
            name='name',
            field=models.CharField(max_length=100),
        ),
        # Add a unique_together constraint for name and group
        migrations.AlterUniqueTogether(
            name='species',
            unique_together={('name', 'group')},
        ),
    ]