import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import GroupForm
from .models import Project, Species, TaskBatch, Group, GroupMembership, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_group")


@login_required
def group_list_view(request):
    """Display list of groups"""
    # Get all groups the user is a member of through GroupMembership

    # Get user's memberships and related groups
    user_groups = Group.objects.filter(group_memberships__user=request.user).select_related().distinct().order_by("name")

    # Debug output
    print(f"Found {user_groups.count()} groups for user {request.user.username}")
    for group in user_groups:
        print(f" - Group: {group.name} (ID: {group.id})")

    context = {
        "groups": user_groups,
    }

    return render(request, "groups/group_list.html", context)


@login_required
def group_detail_view(request, group_id):
    """Display details of a group"""
    # Get the group
    group = get_object_or_404(Group, id=group_id)

    # Check if the user is a member of this group via GroupMembership
    membership_exists = GroupMembership.objects.filter(user=request.user, group=group).exists()

    # Debug output
    print(
        f"GroupMembership check: User {request.user.username}, Group {group.name} (ID: {group.id}), Membership exists: {membership_exists}"
    )
    if not membership_exists:
        print(f"  - User's active group: {request.user.profile.group.name if request.user.profile.group else 'None'}")
        print(
            f"  - User's memberships: {list(GroupMembership.objects.filter(user=request.user).values_list('group__name', flat=True))}"
        )

    if membership_exists:
        # Get group with members preloaded
        group = Group.objects.prefetch_related("group_memberships", "group_memberships__user").get(id=group_id)

        # Get projects for this group
        projects = Project.objects.filter(group=group)

        # Get species for this group
        species = Species.objects.filter(group=group)

        # Get task batches for this group
        batches = TaskBatch.objects.filter(group=group)

        context = {
            "group": group,
            "projects": projects,
            "species": species,
            "batches": batches,
        }

        return render(request, "groups/group_detail.html", context)
    else:
        messages.error(request, "You do not have permission to view this group.")
        return redirect("battycoda_app:group_list")


@login_required
def create_group_view(request):
    """Handle creation of a group"""
    # Any authenticated user can create a group
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create the group
                group = form.save()

                # Get the current user's profile
                user_profile = request.user.profile

                # Store the user's current group and admin status
                old_group = user_profile.group
                was_admin = user_profile.is_admin

                # Create GroupMembership record for the new group
                print(f"Creating GroupMembership: User={request.user.username}, Group={group.name} (ID: {group.id})")
                membership, created = GroupMembership.objects.get_or_create(
                    user=request.user, group=group, defaults={"is_admin": True}  # Group creator is always admin
                )
                print(f"GroupMembership created: {created}, ID: {membership.id if membership else 'None'}")

                # Always make the creator a member and admin of the new group
                user_profile.group = group
                user_profile.is_admin = True
                user_profile.save()

            messages.success(request, "Group created successfully! You have been added as an admin.")
            return redirect("battycoda_app:group_detail", group_id=group.id)
    else:
        form = GroupForm()

    context = {
        "form": form,
    }

    return render(request, "groups/create_group.html", context)


@login_required
def edit_group_view(request, group_id):
    """Handle editing of a group (group admin only)"""
    # Only group admins can edit their group
    group = get_object_or_404(Group, id=group_id)

    # Check if user is admin of this group
    if not request.user.profile.is_admin or request.user.profile.group != group:
        messages.error(request, "You do not have permission to edit this group.")
        return redirect("battycoda_app:group_list")

    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()

            messages.success(request, "Group updated successfully.")
            return redirect("battycoda_app:group_detail", group_id=group.id)
    else:
        form = GroupForm(instance=group)

    context = {
        "form": form,
        "group": group,
    }

    return render(request, "groups/edit_group.html", context)


@login_required
def manage_group_members_view(request, group_id):
    """Handle assigning users to groups (group admin only)"""
    # Only group admins can manage their group members
    group = get_object_or_404(Group, id=group_id)

    # Get the current user's GroupMembership for this group
    try:
        user_membership = GroupMembership.objects.get(user=request.user, group=group)
        is_admin = user_membership.is_admin
    except GroupMembership.DoesNotExist:
        is_admin = False

    # Check if user is admin of this group
    if not is_admin:
        messages.error(request, "You do not have permission to manage group members.")
        return redirect("battycoda_app:group_list")

    # Get all members of this group via GroupMembership
    group_memberships = GroupMembership.objects.filter(group=group).select_related("user", "user__profile")

    # Get all users not in this group
    users_in_group = group_memberships.values_list("user__id", flat=True)
    non_group_users = User.objects.exclude(id__in=users_in_group)

    if request.method == "POST":
        # Handle adding a user to the group
        if "add_user" in request.POST:
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)
                # Create group membership
                membership, created = GroupMembership.objects.get_or_create(
                    user=user, group=group, defaults={"is_admin": False}
                )

                # Update active group if the user doesn't have one
                if not user.profile.group:
                    user.profile.group = group
                    user.profile.save()

                messages.success(request, f"User {user.username} added to the group.")

        # Handle removing a user from the group
        elif "remove_user" in request.POST:
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)

                # Don't allow removing the last admin
                if GroupMembership.objects.filter(group=group, is_admin=True).count() <= 1:
                    membership = GroupMembership.objects.get(user=user, group=group)
                    if membership.is_admin:
                        messages.error(request, f"Cannot remove the last admin from the group.")
                        return redirect("battycoda_app:manage_group_members", group_id=group.id)

                # Delete the membership
                GroupMembership.objects.filter(user=user, group=group).delete()

                # If this was the user's active group, set to None
                if user.profile.group == group:
                    user.profile.group = None
                    user.profile.is_admin = False
                    user.profile.save()

                messages.success(request, f"User {user.username} removed from the group.")

        # Handle toggling admin status
        elif "toggle_admin" in request.POST:
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)
                membership = get_object_or_404(GroupMembership, user=user, group=group)

                # Check if we're trying to demote the last admin
                if membership.is_admin and GroupMembership.objects.filter(group=group, is_admin=True).count() <= 1:
                    messages.error(request, f"Cannot remove admin status from the last admin.")
                    return redirect("battycoda_app:manage_group_members", group_id=group.id)

                # Toggle admin status
                membership.is_admin = not membership.is_admin
                membership.save()

                # If this is the user's active group, also update profile
                if user.profile.group == group:
                    user.profile.is_admin = membership.is_admin
                    user.profile.save()

                status = "granted" if membership.is_admin else "revoked"
                messages.success(request, f"Admin status {status} for user {user.username}.")

        return redirect("battycoda_app:manage_group_members", group_id=group.id)

    context = {
        "group": group,
        "group_memberships": group_memberships,
        "non_group_users": non_group_users,
    }

    return render(request, "groups/manage_members.html", context)


@login_required
def switch_group_view(request, group_id):
    """Allow a user to switch their active group"""
    # Get the group
    group = get_object_or_404(Group, id=group_id)

    # Get user profile
    user_profile = request.user.profile

    # Try to get membership
    try:
        membership = GroupMembership.objects.get(user=request.user, group=group)
    except GroupMembership.DoesNotExist:
        # Create membership if not exists (fallback for legacy users)
        is_admin = group.name.startswith(f"{request.user.username}'s Group")
        membership = GroupMembership.objects.create(user=request.user, group=group, is_admin=is_admin)

    # Update the user's active group
    user_profile.group = group

    # Set admin status based on membership
    user_profile.is_admin = membership.is_admin
    user_profile.save()

    messages.success(request, f'You are now working in the "{group.name}" group.')

    # Redirect back to referring page or index
    next_page = request.META.get("HTTP_REFERER", reverse("battycoda_app:index"))
    return redirect(next_page)


@login_required
def debug_groups_view(request):
    """Debug view to inspect group membership and available groups"""
    # Get all groups in the database with their memberships
    all_groups = Group.objects.all().prefetch_related("group_memberships", "group_memberships__user")

    # Get user's memberships
    user_memberships = GroupMembership.objects.filter(user=request.user).select_related("group")

    # Group consistency check - verify that we have correct group memberships
    # Get all user profiles and count their groups
    total_profiles = UserProfile.objects.filter(group__isnull=False).count()
    total_memberships = GroupMembership.objects.count()

    # Find profiles without matching memberships
    profiles_without_membership = UserProfile.objects.filter(group__isnull=False).exclude(
        user__in=GroupMembership.objects.filter(group=models.F("user__profile__group")).values_list("user", flat=True)
    )

    # Find users with memberships but no active group
    users_with_memberships_no_group = UserProfile.objects.filter(
        user__in=GroupMembership.objects.values_list("user", flat=True), group__isnull=True
    )

    context = {
        "all_groups": all_groups,
        "user_memberships": user_memberships,
        "total_profiles_with_groups": total_profiles,
        "total_memberships": total_memberships,
        "profiles_without_membership": profiles_without_membership,
        "users_with_memberships_no_group": users_with_memberships_no_group,
    }

    # If the sync parameter is provided, fix any inconsistencies
    if request.GET.get("sync") == "true" and request.user.is_superuser:
        # For each profile without a membership, create one
        for profile in profiles_without_membership:
            GroupMembership.objects.get_or_create(
                user=profile.user, group=profile.group, defaults={"is_admin": profile.is_admin}
            )

        # For each user with memberships but no active group, set their active group
        for profile in users_with_memberships_no_group:
            # Get first membership
            membership = GroupMembership.objects.filter(user=profile.user).first()
            if membership:
                profile.group = membership.group
                profile.is_admin = membership.is_admin
                profile.save()

        messages.success(request, "Group memberships synchronized successfully.")
        return redirect("battycoda_app:debug_groups")

    return render(request, "groups/debug_groups.html", context)
