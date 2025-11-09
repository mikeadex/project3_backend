"""
Custom email backend for Resend HTTP API
This bypasses SMTP port blocking on Render free tier
"""

import logging
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendHTTPBackend(BaseEmailBackend):
    """
    Email backend that uses Resend HTTP API instead of SMTP.
    This works on Render free tier which blocks SMTP ports.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = settings.EMAIL_HOST_PASSWORD or settings.RESEND_API_KEY
        self.api_url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        """
        Send emails using Resend HTTP API
        """
        if not email_messages:
            return 0

        num_sent = 0
        for message in email_messages:
            try:
                # Prepare email data for Resend API
                email_data = {
                    "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                    "to": message.to,
                    "subject": message.subject,
                }

                # Handle HTML and plain text - Check for alternatives first
                has_html = False
                if hasattr(message, 'alternatives') and message.alternatives:
                    # EmailMultiAlternatives with HTML
                    for content, mimetype in message.alternatives:
                        if mimetype == "text/html":
                            email_data["html"] = content
                            has_html = True
                            break
                
                if not has_html and message.content_subtype == "html":
                    # Direct HTML message
                    email_data["html"] = message.body
                elif not has_html:
                    # Plain text only
                    email_data["text"] = message.body
                else:
                    # Plain text version for multipart
                    email_data["text"] = message.body

                # Add CC and BCC if present
                if message.cc:
                    email_data["cc"] = message.cc
                if message.bcc:
                    email_data["bcc"] = message.bcc

                # Add reply-to if present
                if message.reply_to:
                    email_data["reply_to"] = message.reply_to[0]

                # Send via Resend HTTP API
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                logger.info(f"📧 Sending email via Resend HTTP API to {message.to}")

                response = requests.post(
                    self.api_url,
                    json=email_data,
                    headers=headers,
                    timeout=10,  # 10 second timeout
                )

                if response.status_code in [200, 201]:
                    logger.info(f"✅ Email sent successfully to {message.to}")
                    num_sent += 1
                else:
                    logger.error(
                        f"❌ Resend API error: {response.status_code} - {response.text}"
                    )

            except Exception as e:
                logger.error(f"❌ Failed to send email via Resend HTTP API: {str(e)}")
                if not self.fail_silently:
                    raise

        return num_sent
