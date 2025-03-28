from django.core.management.base import BaseCommand
from django.db import transaction

from battycoda_app.models import GroupMembership, UserProfile


class Command(BaseCommand):
    help = "Populate the GroupMembership model with existing user-group relationships"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help='Force recreation of memberships even if they already exist'
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting GroupMembership population...")
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Get all user profiles
        profiles = UserProfile.objects.select_related('user', 'group').all()
        
        with transaction.atomic():
            for profile in profiles:
                if profile.group:
                    # Create membership record if the user has a group
                    if options['force']:
                        # If force flag is used, we update or create
                        membership, created = GroupMembership.objects.update_or_create(
                            user=profile.user,
                            group=profile.group,
                            defaults={'is_admin': profile.is_admin}
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                f"Created membership for {profile.user.username} in group {profile.group.name}"
                            )
                        else:
                            updated_count += 1
                            self.stdout.write(
                                f"Updated membership for {profile.user.username} in group {profile.group.name}"
                            )
                    else:
                        # Otherwise, only create if it doesn't exist
                        membership, created = GroupMembership.objects.get_or_create(
                            user=profile.user,
                            group=profile.group,
                            defaults={'is_admin': profile.is_admin}
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                f"Created membership for {profile.user.username} in group {profile.group.name}"
                            )
                        else:
                            skipped_count += 1
                            self.stdout.write(
                                f"Membership already exists for {profile.user.username} in group {profile.group.name}"
                            )
        
        self.stdout.write(self.style.SUCCESS(
            f"Finished! Created {created_count} GroupMembership records, "
            f"updated {updated_count}, skipped {skipped_count}."
        ))