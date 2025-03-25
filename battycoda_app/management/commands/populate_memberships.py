from django.core.management.base import BaseCommand
from django.db import transaction

from battycoda_app.models import UserProfile, TeamMembership

class Command(BaseCommand):
    help = "Populate the TeamMembership model with existing user-team relationships"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help='Force recreation of memberships even if they already exist'
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting TeamMembership population...")
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Get all user profiles
        profiles = UserProfile.objects.select_related('user', 'team').all()
        
        with transaction.atomic():
            for profile in profiles:
                if profile.team:
                    # Create membership record if the user has a team
                    if options['force']:
                        # If force flag is used, we update or create
                        membership, created = TeamMembership.objects.update_or_create(
                            user=profile.user,
                            team=profile.team,
                            defaults={'is_admin': profile.is_admin}
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                f"Created membership for {profile.user.username} in team {profile.team.name}"
                            )
                        else:
                            updated_count += 1
                            self.stdout.write(
                                f"Updated membership for {profile.user.username} in team {profile.team.name}"
                            )
                    else:
                        # Otherwise, only create if it doesn't exist
                        membership, created = TeamMembership.objects.get_or_create(
                            user=profile.user,
                            team=profile.team,
                            defaults={'is_admin': profile.is_admin}
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                f"Created membership for {profile.user.username} in team {profile.team.name}"
                            )
                        else:
                            skipped_count += 1
                            self.stdout.write(
                                f"Membership already exists for {profile.user.username} in team {profile.team.name}"
                            )
        
        self.stdout.write(self.style.SUCCESS(
            f"Finished! Created {created_count} TeamMembership records, "
            f"updated {updated_count}, skipped {skipped_count}."
        ))