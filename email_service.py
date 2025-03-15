"""
Email service for BattyCoda application.
This module provides email functionality without requiring API keys.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os
from email.utils import formataddr

# Configure logging
logger = logging.getLogger('battykoda.email')

class EmailService:
    """
    Email service using public SMTP relays that don't require authentication.
    Tries multiple providers in case one fails.
    """
    
    def __init__(self):
        # List of free/anonymous SMTP relays to try
        # These are just examples - real-world reliability varies
        self.smtp_servers = [
            {'host': 'smtp.mail.yahoo.com', 'port': 587},  # For when OAuth is set up
            {'host': 'relay.appriver.com', 'port': 2525},  # Anonymous relay
            {'host': 'mail.smtpbucket.com', 'port': 8025}  # For testing
        ]
        
        # For testing environments, we can use a mock system
        self.is_testing = os.environ.get('TESTING', 'False').lower() == 'true'
        if self.is_testing:
            # For tests, save emails to a file instead of sending
            self.test_emails = []
    
    def send_email(self, recipient_email, subject, html_content, text_content=None,
                   sender_name="BattyCoda", sender_email="no-reply@battycoda.org"):
        """
        Send an email to the specified recipient.
        
        Args:
            recipient_email: Email address of the recipient
            subject: Email subject
            html_content: HTML body of the email
            text_content: Plain text alternative (optional)
            sender_name: Name to display in the From field
            sender_email: Email address to show in the From field
            
        Returns:
            success: True if email was sent, False otherwise
            message: Details about the result
        """
        # For testing, save the email instead of sending
        if self.is_testing:
            self.test_emails.append({
                'to': recipient_email,
                'subject': subject,
                'html': html_content,
                'text': text_content,
                'from': f"{sender_name} <{sender_email}>"
            })
            logger.info(f"Test mode: Email to {recipient_email} stored (not sent)")
            return True, "Test email stored"
        
        # Create the email message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = formataddr((sender_name, sender_email))
        message["To"] = recipient_email
        
        # Add text content if provided, otherwise create a simple version from the HTML
        if text_content is None:
            text_content = self._html_to_text(html_content)
        
        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Try sending with all available servers
        last_error = None
        for server in self.smtp_servers:
            try:
                self._send_with_server(server, message, sender_email, recipient_email)
                logger.info(f"Email sent to {recipient_email} via {server['host']}")
                return True, f"Email sent via {server['host']}"
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Failed to send email via {server['host']}: {str(e)}")
                continue
        
        # If we got here, all servers failed
        logger.error(f"Failed to send email to {recipient_email}: {last_error}")
        return False, f"Failed to send email: {last_error}"
    
    def _send_with_server(self, server, message, sender_email, recipient_email):
        """Send an email using a specific SMTP server."""
        context = ssl.create_default_context()
        
        # Connect to server
        with smtplib.SMTP(server['host'], server['port']) as smtp:
            smtp.ehlo()
            
            # Start TLS if available
            try:
                smtp.starttls(context=context)
                smtp.ehlo()
            except smtplib.SMTPNotSupportedError:
                logger.info(f"TLS not supported by {server['host']}")
            
            # Some relays allow anonymous sending
            try:
                # Send the email
                smtp.sendmail(sender_email, recipient_email, message.as_string())
            except smtplib.SMTPSenderRefused:
                # If the server requires authentication, raise an error
                raise Exception(f"Server {server['host']} requires authentication")
    
    def _html_to_text(self, html):
        """Create a simple text version from an HTML email."""
        # Very basic conversion - in a real app, use a proper HTML-to-text converter
        import re
        text = re.sub('<.*?>', ' ', html)
        text = re.sub('\\s+', ' ', text)
        return text.strip()

    def send_login_code_email(self, user_email, username, login_code):
        """Send a one-time login code to a user."""
        subject = "Your BattyCoda Login Code"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #e57373; color: black; padding: 15px; text-align: center;">
                    <h1>BattyCoda Login Code</h1>
                </div>
                
                <div style="padding: 20px; background-color: #f9f9f9;">
                    <p>Hello <strong>{username}</strong>,</p>
                    
                    <p>You requested a one-time login code for BattyCoda. Here is your code:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <div style="font-size: 24px; letter-spacing: 4px; font-weight: bold; background-color: #eeeeee; padding: 15px; border-radius: 5px;">{login_code}</div>
                    </div>
                    
                    <p>This code will expire in 15 minutes.</p>
                    
                    <p>If you did not request this code, you can safely ignore this email.</p>
                    
                    <p>Thank you for using BattyCoda!</p>
                </div>
                
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #666666;">
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(recipient_email=user_email, subject=subject, html_content=html_content)
    
    def send_welcome_email(self, user_email, username):
        """Send a welcome email to a new user."""
        subject = "Welcome to BattyCoda!"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #e57373; color: black; padding: 15px; text-align: center;">
                    <h1>Welcome to BattyCoda!</h1>
                </div>
                
                <div style="padding: 20px; background-color: #f9f9f9;">
                    <p>Hello <strong>{username}</strong>,</p>
                    
                    <p>Thank you for creating an account with BattyCoda, your new tool for analyzing animal vocalizations.</p>
                    
                    <p>With BattyCoda, you can:</p>
                    <ul>
                        <li>Analyze bat echolocation calls</li>
                        <li>Study bird songs</li>
                        <li>Classify frog vocalizations</li>
                        <li>And much more!</li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>
                    
                    <p>Happy analyzing!</p>
                    <p>The BattyCoda Team</p>
                </div>
                
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #666666;">
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(recipient_email=user_email, subject=subject, html_content=html_content)
    
    def send_password_reset_email(self, user_email, username, reset_link):
        """Send a password reset email."""
        subject = "Reset Your BattyCoda Password"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #e57373; color: black; padding: 15px; text-align: center;">
                    <h1>Password Reset Request</h1>
                </div>
                
                <div style="padding: 20px; background-color: #f9f9f9;">
                    <p>Hello <strong>{username}</strong>,</p>
                    
                    <p>We received a request to reset your BattyCoda password. If you didn't make this request, you can safely ignore this email.</p>
                    
                    <p>To reset your password, please click the button below:</p>
                    
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="background-color: #e57373; color: black; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-weight: bold;">Reset Password</a>
                    </p>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="background-color: #eeeeee; padding: 10px; word-break: break-all;">{reset_link}</p>
                    
                    <p>This link will expire in 24 hours.</p>
                    
                    <p>If you have any issues, please contact support.</p>
                </div>
                
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #666666;">
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(recipient_email=user_email, subject=subject, html_content=html_content)

# Create a singleton instance
email_service = EmailService()