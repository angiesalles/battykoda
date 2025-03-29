"""User models for BattyCoda application."""

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Group(models.Model):
    """Group model for user grouping and permissions."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupInvitation(models.Model):
    """Group invitation model for inviting users via email."""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    token = models.CharField(max_length=255, unique=True, help_text="Unique token for invitation link")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"Invitation to {self.group.name} for {self.email}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return self.expires_at < timezone.now()


class GroupMembership(models.Model):
    """Model for user membership in groups."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_memberships")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_memberships")
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "group")

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({'Admin' if self.is_admin else 'Member'})"


class UserProfile(models.Model):
    """User profile extension model."""

    # Theme choices
    THEME_CHOICES = (
        ("default", "Default - Red"),
        ("blue", "Blue/Green"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members", null=True)
    is_admin = models.BooleanField(
        default=False, help_text="Designates whether this user is an administrator of their group"
    )
    # User preferences
    theme = models.CharField(
        max_length=20, choices=THEME_CHOICES, default="default", help_text="Color theme preference"
    )
    # Authentication fields (previously Cloudflare fields, kept for data compatibility)
    cloudflare_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="Deprecated - kept for data compatibility"
    )
    is_cloudflare_user = models.BooleanField(default=False, help_text="Deprecated - kept for data compatibility")
    cloudflare_email = models.EmailField(blank=True, null=True, help_text="Deprecated - kept for data compatibility")
    last_cloudflare_login = models.DateTimeField(
        blank=True, null=True, help_text="Deprecated - kept for data compatibility"
    )

    def __str__(self):
        return self.user.username

    @property
    def available_groups(self):
        """Get all groups the user is a member of through GroupMembership"""
        # Get groups from memberships
        membership_groups = Group.objects.filter(group_memberships__user=self.user).order_by("name")

        # Move current group to the front if it exists
        if self.group:
            result = list(membership_groups)
            if self.group in result:
                result.remove(self.group)
            return [self.group] + result

        return membership_groups

    @property
    def is_admin_of_group(self, group_id):
        """Check if user is admin of the specified group"""
        return GroupMembership.objects.filter(user=self.user, group_id=group_id, is_admin=True).exists()


# Create user profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        import logging

        logger = logging.getLogger("battycoda.models")

        # First create the profile
        profile = UserProfile.objects.create(user=instance)

        # Create a new group for this user with unique name based on username
        group_name = f"{instance.username}'s Group"
        group = Group.objects.create(name=group_name, description="Your personal workspace for projects and recordings")

        # Assign the user to their own group and make them an admin
        profile.group = group
        profile.is_admin = True
        profile.save()

        # Create group membership record
        GroupMembership.objects.create(user=instance, group=group, is_admin=True)

        # Create a demo project for the user
        try:
            # Import here to avoid circular imports
            Project = sender.objects.model._meta.apps.get_model("battycoda_app", "Project")

            # Create a standard demo project
            project_name = "Demo Project"

            Project.objects.create(
                name=project_name,
                description="Sample project for demonstration and practice",
                created_by=instance,
                group=group,
            )
            logger.info(f"Created demo project '{project_name}' for user {instance.username}")
        except Exception as e:
            logger.error(f"Error creating demo project for user {instance.username}: {str(e)}")

        # Import default species in a separate try block
        try:
            from ..utils import import_default_species

            created_species = import_default_species(instance)
            logger.info(f"Created {len(created_species)} default species for user {instance.username}")
        except Exception as e:
            logger.error(f"Error importing default species for user {instance.username}: {str(e)}")

        # Create a demo task batch with sample bat calls
        try:
            from ..utils import create_demo_task_batch

            batch = create_demo_task_batch(instance)
            if batch:
                logger.info(f"Created demo task batch '{batch.name}' for user {instance.username}")
            else:
                logger.warning(f"Failed to create demo task batch for user {instance.username}")
        except Exception as e:
            logger.error(f"Error creating demo task batch for user {instance.username}: {str(e)}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
