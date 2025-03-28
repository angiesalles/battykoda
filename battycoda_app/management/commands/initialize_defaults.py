from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError

from battycoda_app.models import Call, Project, Species


class Command(BaseCommand):
    help = "Initialize default data for BattyCoda"

    def handle(self, *args, **kwargs):
        self.stdout.write("Initializing default data...")

        # Get admin user or any user if none exists
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            # Check for any user
            admin_user = User.objects.first()

            if not admin_user:
                self.stdout.write('No users found. Creating a superuser "admin" with password "battycoda"')
                try:
                    admin_user = User.objects.create_superuser(
                        username="admin", email="admin@example.com", password="battycoda"
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error creating admin user: {e}"))
                    return

        # Create default project if it doesn't exist
        try:
            default_project, created = Project.objects.get_or_create(
                name="Default Project",
                defaults={"description": "Default project created automatically", "created_by": admin_user},
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created default project: {default_project.name}"))
            else:
                self.stdout.write(f"Default project already exists: {default_project.name}")

        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(f"Error creating default project: {e}"))

        # Create an example species if none exist
        if Species.objects.count() == 0:
            try:
                example_species = Species.objects.create(
                    name="Eptesicus fuscus",
                    scientific_name="Eptesicus fuscus",
                    description="Big Brown Bat: A common species in North America",
                    created_by=admin_user,
                )

                # Add some example calls
                call_types = [
                    ("FM", "Frequency Modulated", "Downward sweep in frequency"),
                    ("CF", "Constant Frequency", "Call with a relatively constant frequency"),
                    ("QCF", "Quasi-Constant Frequency", "Call with a section of nearly constant frequency"),
                ]

                for short_name, long_name, description in call_types:
                    Call.objects.create(
                        species=example_species, short_name=short_name, long_name=long_name, description=description
                    )

                self.stdout.write(self.style.SUCCESS(f"Created example species with {len(call_types)} call types"))
            except IntegrityError as e:
                self.stdout.write(self.style.ERROR(f"Error creating example species: {e}"))

        self.stdout.write(self.style.SUCCESS("Default data initialization complete"))
