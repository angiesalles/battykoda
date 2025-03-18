from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Cloudflare fields
    cloudflare_id = models.CharField(max_length=255, blank=True, null=True)
    is_cloudflare_user = models.BooleanField(default=False)
    cloudflare_email = models.EmailField(blank=True, null=True)
    last_cloudflare_login = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return self.user.username

# Create user profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
