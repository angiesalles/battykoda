from django.contrib import admin

from .models import UserProfile, Classifier


# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "id")
    search_fields = ("user__username", "user__email")


@admin.register(Classifier)
class ClassifierAdmin(admin.ModelAdmin):
    list_display = ("name", "response_format", "service_url", "is_active", "group")
    list_filter = ("response_format", "is_active", "group")
    search_fields = ("name", "description", "service_url")
    list_editable = ("is_active",)
