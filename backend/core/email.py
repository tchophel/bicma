"""Shared BICMA email presentation with an embedded logo and plain-text fallback."""
from email.mime.image import MIMEImage
from pathlib import Path

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


LOGO = Path(__file__).resolve().parent / "assets" / "bicma-logo.png"


def send_mail(subject, message, from_email, recipient_list, fail_silently=False, *, verification_code=None):
    html = render_to_string("emails/branded.html", {"subject": subject, "message": message, "verification_code": verification_code})
    email = EmailMultiAlternatives(subject, message, from_email, recipient_list)
    email.mixed_subtype = "related"
    email.attach_alternative(html, "text/html")
    logo = MIMEImage(LOGO.read_bytes(), _subtype="png")
    logo.add_header("Content-ID", "<bicma-logo>")
    logo.add_header("Content-Disposition", "inline", filename="bicma-logo.png")
    email.attach(logo)
    return email.send(fail_silently=fail_silently)
