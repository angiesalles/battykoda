import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .email_utils import send_invitation_email
from .forms import TeamInvitationForm
from .models import Team, TeamInvitation, TeamMembership, User, UserProfile

logger = logging.getLogger("battycoda.invitations")


@login_required
def team_users_view(request):
    """Display users in the current team with invitation capability for admins"""
    # Check if the user is an admin of their current team
    if not request.user.profile.is_admin or not request.user.profile.team:
        messages.error(request, "You must be a team admin to manage users.")
        return redirect("battycoda_app:index")

    # Get current team
    team = request.user.profile.team

    # Get team members based on TeamMembership and filter by team
    team_memberships = TeamMembership.objects.filter(team=team).select_related("user", "user__profile")

    # Get active invitations for this team
    active_invitations = TeamInvitation.objects.filter(team=team, accepted=False).exclude(expires_at__lt=timezone.now())

    context = {
        "team": team,
        "team_memberships": team_memberships,
        "active_invitations": active_invitations,
    }

    return render(request, "teams/team_users.html", context)


@login_required
def invite_user_view(request):
    """Send an invitation to join the team to a user by email"""
    # Check if the user is an admin of their current team
    if not request.user.profile.is_admin or not request.user.profile.team:
        messages.error(request, "You must be a team admin to invite users.")
        return redirect("battycoda_app:team_users")

    # Get current team
    team = request.user.profile.team

    if request.method == "POST":
        form = TeamInvitationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            # Check if there's already an active invitation for this email
            existing_invitation = (
                TeamInvitation.objects.filter(team=team, email=email, accepted=False)
                .exclude(expires_at__lt=timezone.now())
                .first()
            )

            if existing_invitation:
                messages.info(
                    request,
                    f"An active invitation already exists for {email}. "
                    f"It will expire on {existing_invitation.expires_at.strftime('%Y-%m-%d %H:%M')}.",
                )
                return redirect("battycoda_app:team_users")

            # Check if the user is already a member of this team
            try:
                user = User.objects.get(email=email)
                if TeamMembership.objects.filter(user=user, team=team).exists():
                    messages.info(request, f"{email} is already a member of this team.")
                    return redirect("battycoda_app:team_users")
            except User.DoesNotExist:
                # No existing user with this email, which is fine for invitation
                pass

            # Create a new invitation
            token = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(days=7)  # invitation expires in 7 days

            invitation = TeamInvitation.objects.create(
                team=team, email=email, invited_by=request.user, token=token, expires_at=expires_at
            )

            # Create the invitation link
            invitation_link = request.build_absolute_uri(
                reverse("battycoda_app:accept_invitation", kwargs={"token": token})
            )

            # Send the invitation email using the utility function
            email_sent = send_invitation_email(
                team_name=team.name,
                inviter_name=request.user.username,
                recipient_email=email,
                invitation_link=invitation_link,
                expires_at=expires_at,
            )

            if email_sent:
                messages.success(request, f"Invitation sent successfully to {email}.")
                logger.info(f"Invitation sent to {email} for team {team.name} by {request.user.username}")
            else:
                # If email sending fails, delete the invitation and show error
                invitation.delete()
                logger.error(f"Failed to send invitation email to {email}")
                messages.error(request, "Failed to send invitation email. Check the email settings.")

            return redirect("battycoda_app:team_users")
    else:
        form = TeamInvitationForm()

    context = {
        "form": form,
        "team": team,
    }

    return render(request, "teams/invite_user.html", context)


def accept_invitation_view(request, token):
    """Accept a team invitation using the token from the email"""
    # Try to find the invitation
    invitation = get_object_or_404(TeamInvitation, token=token)

    # Check if invitation is already accepted
    if invitation.accepted:
        messages.info(request, "This invitation has already been accepted.")
        if request.user.is_authenticated:
            return redirect("battycoda_app:index")
        else:
            return redirect("battycoda_app:login")

    # Check if invitation is expired
    if invitation.is_expired:
        messages.error(request, "This invitation has expired.")
        return redirect("battycoda_app:index")

    # If user is logged in
    if request.user.is_authenticated:
        # Add the user to the team using the TeamMembership model
        # First check if membership already exists
        membership, created = TeamMembership.objects.get_or_create(
            user=request.user,
            team=invitation.team,
            defaults={"is_admin": False},  # New members are not admins by default
        )

        # Update the current active team
        profile = request.user.profile
        profile.team = invitation.team
        profile.save()

        # Mark the invitation as accepted
        invitation.accepted = True
        invitation.save()

        messages.success(request, f"You have been added to the team '{invitation.team.name}'.")
        return redirect("battycoda_app:index")
    else:
        # Store the token in session for use after registration/login
        request.session["invitation_token"] = token

        messages.info(request, "Please register or log in to accept your team invitation.")

        # If the invitation email matches an existing user, suggest login
        from django.contrib.auth.models import User

        if User.objects.filter(email=invitation.email).exists():
            return redirect("battycoda_app:login")
        else:
            # Otherwise, suggest registration with the email pre-filled
            return redirect("battycoda_app:register")
