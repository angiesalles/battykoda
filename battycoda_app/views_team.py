import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import TeamForm
from .models import Project, Species, TaskBatch, Team, TeamMembership, UserProfile

# Set up logging
logger = logging.getLogger("battycoda.views_team")


@login_required
def team_list_view(request):
    """Display list of teams"""
    # Get all teams the user is a member of through TeamMembership

    # Get user's memberships and related teams
    user_teams = Team.objects.filter(team_memberships__user=request.user).select_related().distinct().order_by("name")

    # Debug output
    print(f"Found {user_teams.count()} teams for user {request.user.username}")
    for team in user_teams:
        print(f" - Team: {team.name} (ID: {team.id})")

    context = {
        "teams": user_teams,
    }

    return render(request, "teams/team_list.html", context)


@login_required
def team_detail_view(request, team_id):
    """Display details of a team"""
    # Get the team
    team = get_object_or_404(Team, id=team_id)

    # Check if the user is a member of this team via TeamMembership
    membership_exists = TeamMembership.objects.filter(user=request.user, team=team).exists()

    # Debug output
    print(
        f"TeamMembership check: User {request.user.username}, Team {team.name} (ID: {team.id}), Membership exists: {membership_exists}"
    )
    if not membership_exists:
        print(f"  - User's active team: {request.user.profile.team.name if request.user.profile.team else 'None'}")
        print(
            f"  - User's memberships: {list(TeamMembership.objects.filter(user=request.user).values_list('team__name', flat=True))}"
        )

    if membership_exists:
        # Get team with members preloaded
        team = Team.objects.prefetch_related("team_memberships", "team_memberships__user").get(id=team_id)

        # Get projects for this team
        projects = Project.objects.filter(team=team)

        # Get species for this team
        species = Species.objects.filter(team=team)

        # Get task batches for this team
        batches = TaskBatch.objects.filter(team=team)

        context = {
            "team": team,
            "projects": projects,
            "species": species,
            "batches": batches,
        }

        return render(request, "teams/team_detail.html", context)
    else:
        messages.error(request, "You do not have permission to view this team.")
        return redirect("battycoda_app:team_list")


@login_required
def create_team_view(request):
    """Handle creation of a team"""
    # Any authenticated user can create a team
    if request.method == "POST":
        form = TeamForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create the team
                team = form.save()

                # Get the current user's profile
                user_profile = request.user.profile

                # Store the user's current team and admin status
                old_team = user_profile.team
                was_admin = user_profile.is_admin

                # Create TeamMembership record for the new team
                print(f"Creating TeamMembership: User={request.user.username}, Team={team.name} (ID: {team.id})")
                membership, created = TeamMembership.objects.get_or_create(
                    user=request.user, team=team, defaults={"is_admin": True}  # Team creator is always admin
                )
                print(f"TeamMembership created: {created}, ID: {membership.id if membership else 'None'}")

                # Always make the creator a member and admin of the new team
                user_profile.team = team
                user_profile.is_admin = True
                user_profile.save()

            messages.success(request, "Team created successfully! You have been added as an admin.")
            return redirect("battycoda_app:team_detail", team_id=team.id)
    else:
        form = TeamForm()

    context = {
        "form": form,
    }

    return render(request, "teams/create_team.html", context)


@login_required
def edit_team_view(request, team_id):
    """Handle editing of a team (team admin only)"""
    # Only team admins can edit their team
    team = get_object_or_404(Team, id=team_id)

    # Check if user is admin of this team
    if not request.user.profile.is_admin or request.user.profile.team != team:
        messages.error(request, "You do not have permission to edit this team.")
        return redirect("battycoda_app:team_list")

    if request.method == "POST":
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()

            messages.success(request, "Team updated successfully.")
            return redirect("battycoda_app:team_detail", team_id=team.id)
    else:
        form = TeamForm(instance=team)

    context = {
        "form": form,
        "team": team,
    }

    return render(request, "teams/edit_team.html", context)


@login_required
def manage_team_members_view(request, team_id):
    """Handle assigning users to teams (team admin only)"""
    # Only team admins can manage their team members
    team = get_object_or_404(Team, id=team_id)

    # Get the current user's TeamMembership for this team
    try:
        user_membership = TeamMembership.objects.get(user=request.user, team=team)
        is_admin = user_membership.is_admin
    except TeamMembership.DoesNotExist:
        is_admin = False

    # Check if user is admin of this team
    if not is_admin:
        messages.error(request, "You do not have permission to manage team members.")
        return redirect("battycoda_app:team_list")

    # Get all members of this team via TeamMembership
    team_memberships = TeamMembership.objects.filter(team=team).select_related("user", "user__profile")

    # Get all users not in this team
    users_in_team = team_memberships.values_list("user__id", flat=True)
    non_team_users = User.objects.exclude(id__in=users_in_team)

    if request.method == "POST":
        # Handle adding a user to the team
        if "add_user" in request.POST:
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)
                # Create team membership
                membership, created = TeamMembership.objects.get_or_create(
                    user=user, team=team, defaults={"is_admin": False}
                )

                # Update active team if the user doesn't have one
                if not user.profile.team:
                    user.profile.team = team
                    user.profile.save()

                messages.success(request, f"User {user.username} added to the team.")

        # Handle removing a user from the team
        elif "remove_user" in request.POST:
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)

                # Don't allow removing the last admin
                if TeamMembership.objects.filter(team=team, is_admin=True).count() <= 1:
                    membership = TeamMembership.objects.get(user=user, team=team)
                    if membership.is_admin:
                        messages.error(request, f"Cannot remove the last admin from the team.")
                        return redirect("battycoda_app:manage_team_members", team_id=team.id)

                # Delete the membership
                TeamMembership.objects.filter(user=user, team=team).delete()

                # If this was the user's active team, set to None
                if user.profile.team == team:
                    user.profile.team = None
                    user.profile.is_admin = False
                    user.profile.save()

                messages.success(request, f"User {user.username} removed from the team.")

        # Handle toggling admin status
        elif "toggle_admin" in request.POST:
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)
                membership = get_object_or_404(TeamMembership, user=user, team=team)

                # Check if we're trying to demote the last admin
                if membership.is_admin and TeamMembership.objects.filter(team=team, is_admin=True).count() <= 1:
                    messages.error(request, f"Cannot remove admin status from the last admin.")
                    return redirect("battycoda_app:manage_team_members", team_id=team.id)

                # Toggle admin status
                membership.is_admin = not membership.is_admin
                membership.save()

                # If this is the user's active team, also update profile
                if user.profile.team == team:
                    user.profile.is_admin = membership.is_admin
                    user.profile.save()

                status = "granted" if membership.is_admin else "revoked"
                messages.success(request, f"Admin status {status} for user {user.username}.")

        return redirect("battycoda_app:manage_team_members", team_id=team.id)

    context = {
        "team": team,
        "team_memberships": team_memberships,
        "non_team_users": non_team_users,
    }

    return render(request, "teams/manage_members.html", context)


@login_required
def switch_team_view(request, team_id):
    """Allow a user to switch their active team"""
    # Get the team
    team = get_object_or_404(Team, id=team_id)

    # Get user profile
    user_profile = request.user.profile

    # Try to get membership
    try:
        membership = TeamMembership.objects.get(user=request.user, team=team)
    except TeamMembership.DoesNotExist:
        # Create membership if not exists (fallback for legacy users)
        is_admin = team.name.startswith(f"{request.user.username}'s Team")
        membership = TeamMembership.objects.create(user=request.user, team=team, is_admin=is_admin)

    # Update the user's active team
    user_profile.team = team

    # Set admin status based on membership
    user_profile.is_admin = membership.is_admin
    user_profile.save()

    messages.success(request, f'You are now working in the "{team.name}" team.')

    # Redirect back to referring page or index
    next_page = request.META.get("HTTP_REFERER", reverse("battycoda_app:index"))
    return redirect(next_page)


@login_required
def debug_teams_view(request):
    """Debug view to inspect team membership and available teams"""
    # Get all teams in the database with their memberships
    all_teams = Team.objects.all().prefetch_related("team_memberships", "team_memberships__user")

    # Get user's memberships
    user_memberships = TeamMembership.objects.filter(user=request.user).select_related("team")

    # Team consistency check - verify that we have correct team memberships
    # Get all user profiles and count their teams
    total_profiles = UserProfile.objects.filter(team__isnull=False).count()
    total_memberships = TeamMembership.objects.count()

    # Find profiles without matching memberships
    profiles_without_membership = UserProfile.objects.filter(team__isnull=False).exclude(
        user__in=TeamMembership.objects.filter(team=models.F("user__profile__team")).values_list("user", flat=True)
    )

    # Find users with memberships but no active team
    users_with_memberships_no_team = UserProfile.objects.filter(
        user__in=TeamMembership.objects.values_list("user", flat=True), team__isnull=True
    )

    context = {
        "all_teams": all_teams,
        "user_memberships": user_memberships,
        "total_profiles_with_teams": total_profiles,
        "total_memberships": total_memberships,
        "profiles_without_membership": profiles_without_membership,
        "users_with_memberships_no_team": users_with_memberships_no_team,
    }

    # If the sync parameter is provided, fix any inconsistencies
    if request.GET.get("sync") == "true" and request.user.is_superuser:
        # For each profile without a membership, create one
        for profile in profiles_without_membership:
            TeamMembership.objects.get_or_create(
                user=profile.user, team=profile.team, defaults={"is_admin": profile.is_admin}
            )

        # For each user with memberships but no active team, set their active team
        for profile in users_with_memberships_no_team:
            # Get first membership
            membership = TeamMembership.objects.filter(user=profile.user).first()
            if membership:
                profile.team = membership.team
                profile.is_admin = membership.is_admin
                profile.save()

        messages.success(request, "Team memberships synchronized successfully.")
        return redirect("battycoda_app:debug_teams")

    return render(request, "teams/debug_teams.html", context)
