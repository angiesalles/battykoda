import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from battycoda_app.utils_modules.species_utils import import_default_species


class Command(BaseCommand):
    help = "Import default species for all users or a specific user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            dest="username",
            help="Username to import species for (if not specified, imports for all users)",
        )
        parser.add_argument(
            "--verbose", action="store_true", dest="verbose", default=False, help="Enable verbose output"
        )

    def handle(self, *args, **options):
        # Set up logging
        if options["verbose"]:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        else:
            logging.basicConfig(level=logging.WARNING)

        logger = logging.getLogger("import_species")

        self.stdout.write("Starting default species import...")

        # Filter users based on username argument
        username = options.get("username")
        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f"User {username} not found"))
                return
        else:
            # Get all users
            users = User.objects.all()

        self.stdout.write(f"Found {users.count()} users to process")

        # Import species for each user
        success_count = 0
        for user in users:
            self.stdout.write(f"Processing user: {user.username}")

            # Skip if user has no group
            if not hasattr(user, "profile") or not user.profile.group:
                self.stdout.write(self.style.WARNING(f"User {user.username} has no profile or group, skipping"))
                continue

            # Import default species
            try:
                created_species = import_default_species(user)
                if created_species:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created {len(created_species)} species for user {user.username}")
                    )

                    # Log created species
                    for species in created_species:
                        self.stdout.write(f"  - {species.name} with {species.calls.count()} call types")
                    success_count += 1
                else:
                    self.stdout.write(f"No new species created for user {user.username}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error importing species for user {user.username}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"Species import complete. Successfully processed {success_count} users."))
