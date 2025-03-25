import logging

from django.conf import settings
from django.core.mail import send_mail as django_send_mail
from django.template.loader import render_to_string

logger = logging.getLogger("battycoda.email")


def send_mail(subject, message, recipient_list, html_message=None, from_email=None):
    """
    Send an email using AWS SES with better error handling and logging.

    Args:
        subject (str): Email subject
        message (str): Plain text message
        recipient_list (list): List of recipient email addresses
        html_message (str, optional): HTML message. Defaults to None.
        from_email (str, optional): Sender email address. Defaults to settings.DEFAULT_FROM_EMAIL.

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    logger.info(f"Sending email to {recipient_list} with subject: {subject}")

    try:
        # Send email using Django's send_mail which will use AWS SES backend
        django_send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Successfully sent email to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}: {str(e)}")
        return False


def send_invitation_email(group_name, inviter_name, recipient_email, invitation_link, expires_at):
    """
    Send a group invitation email.

    Args:
        group_name (str): Name of the group 
        inviter_name (str): Name of the person who sent the invitation
        recipient_email (str): Email address of the recipient
        invitation_link (str): Link to accept the invitation
        expires_at (datetime): Expiration date of the invitation

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    subject = f"Invitation to join {group_name} on BattyCoda"

    # Create plain text message
    message = (
        f"You have been invited to join {group_name} on BattyCoda by {inviter_name}. "
        f"Visit {invitation_link} to accept. "
        f"This invitation will expire on {expires_at.strftime('%Y-%m-%d %H:%M')}."
    )

    # Create HTML message
    html_message = render_to_string(
        "emails/invitation_email.html",
        {
            "group_name": group_name,
            "inviter_name": inviter_name,
            "invitation_link": invitation_link,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M"),
        },
    )

    # Send the email
    return send_mail(subject=subject, message=message, recipient_list=[recipient_email], html_message=html_message)
