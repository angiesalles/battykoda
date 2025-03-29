import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .email_utils import send_invitation_email
from .forms import GroupInvitationForm
from .models import Group, GroupInvitation, GroupMembership, UserProfile

logger = logging.getLogger("battycoda.invitations")


@login_required
def group_users_view(request):
    """Display users in the current group with invitation capability for admins"""
    # Check if the user is an admin of their current group
    if not request.user.profile.is_admin or not request.user.profile.group:
        messages.error(request, "You must be a group admin to manage users.")
        return redirect("battycoda_app:index")

    # Get current group
    group = request.user.profile.group

    # Get group members based on GroupMembership and filter by group
    group_memberships = GroupMembership.objects.filter(group=group).select_related("user", "user__profile")

    # Get active invitations for this group
    active_invitations = GroupInvitation.objects.filter(group=group, accepted=False).exclude(
        expires_at__lt=timezone.now()
    )

    context = {
        "group": group,
        "group_memberships": group_memberships,
        "active_invitations": active_invitations,
    }

    return render(request, "groups/group_users.html", context)


@login_required
def invite_user_view(request):
    """Send an invitation to join the group to a user by email"""
    # Check if the user is an admin of their current group
    if not request.user.profile.is_admin or not request.user.profile.group:
        messages.error(request, "You must be a group admin to invite users.")
        return redirect("battycoda_app:group_users")

    # Get current group
    group = request.user.profile.group

    if request.method == "POST":
        form = GroupInvitationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            # Check if there's already an active invitation for this email
            existing_invitation = (
                GroupInvitation.objects.filter(group=group, email=email, accepted=False)
                .exclude(expires_at__lt=timezone.now())
                .first()
            )

            if existing_invitation:
                messages.info(
                    request,
                    f"An active invitation already exists for {email}. "
                    f"It will expire on {existing_invitation.expires_at.strftime('%Y-%m-%d %H:%M')}.",
                )
                return redirect("battycoda_app:group_users")

            # Check if the user is already a member of this group
            try:
                user = User.objects.get(email=email)
                if GroupMembership.objects.filter(user=user, group=group).exists():
                    messages.info(request, f"{email} is already a member of this group.")
                    return redirect("battycoda_app:group_users")
            except User.DoesNotExist:
                # No existing user with this email, which is fine for invitation
                pass

            # Create a new invitation
            token = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(days=7)  # invitation expires in 7 days

            invitation = GroupInvitation.objects.create(
                group=group, email=email, invited_by=request.user, token=token, expires_at=expires_at
            )

            # Create the invitation link
            invitation_link = request.build_absolute_uri(
                reverse("battycoda_app:accept_invitation", kwargs={"token": token})
            )

            # Send the invitation email using the utility function
            email_sent = send_invitation_email(
                group_name=group.name,
                inviter_name=request.user.username,
                recipient_email=email,
                invitation_link=invitation_link,
                expires_at=expires_at,
            )

            if email_sent:
                messages.success(request, f"Invitation sent successfully to {email}.")
                logger.info(f"Invitation sent to {email} for group {group.name} by {request.user.username}")
            else:
                # If email sending fails, delete the invitation and show error
                invitation.delete()
                logger.error(f"Failed to send invitation email to {email}")
                messages.error(request, "Failed to send invitation email. Check the email settings.")

            return redirect("battycoda_app:group_users")
    else:
        form = GroupInvitationForm()

    context = {
        "form": form,
        "group": group,
    }

    return render(request, "groups/invite_user.html", context)


def accept_invitation_view(request, token):
    """Accept a group invitation using the token from the email"""
    # Try to find the invitation
    invitation = get_object_or_404(GroupInvitation, token=token)

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
        # Add the user to the group using the GroupMembership model
        # First check if membership already exists
        membership, created = GroupMembership.objects.get_or_create(
            user=request.user,
            group=invitation.group,
            defaults={"is_admin": False},  # New members are not admins by default
        )

        # Update the current active group
        profile = request.user.profile
        profile.group = invitation.group
        profile.save()

        # Mark the invitation as accepted
        invitation.accepted = True
        invitation.save()

        messages.success(request, f"You have been added to the group '{invitation.group.name}'.")
        return redirect("battycoda_app:index")
    else:
        # Store the token in session for use after registration/login
        request.session["invitation_token"] = token

        messages.info(request, "Please register or log in to accept your group invitation.")

        # If the invitation email matches an existing user, suggest login
        if User.objects.filter(email=invitation.email).exists():
            return redirect("battycoda_app:login")
        else:
            # Otherwise, suggest registration with the email pre-filled
            return redirect("battycoda_app:register")
