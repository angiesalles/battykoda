import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Recording, UserProfile
from .tasks import calculate_audio_duration

logger = logging.getLogger("battycoda.signals")

# NOTE: These signals are commented out because they duplicate functionality in models.py
# @receiver(post_save, sender=User)
# def create_profile(sender, instance, created, **kwargs):
#     if created:
#         UserProfile.objects.create(user=instance)

# @receiver(post_save, sender=User)
# def save_profile(sender, instance, **kwargs):
#     instance.profile.save()


@receiver(post_save, sender=Recording)
def trigger_audio_info_calculation(sender, instance, **kwargs):
    """
    Signal handler to asynchronously calculate audio duration and sample rate after a recording is saved

    This ensures the file is fully committed to disk before trying to access it.
    """
    # Skip if both duration and sample rate are already set
    if instance.duration and instance.sample_rate:
        return

    logger.info(f"Triggering audio info calculation for recording {instance.id}: {instance.name}")

    # Trigger the Celery task
    calculate_audio_duration.delay(instance.id)
