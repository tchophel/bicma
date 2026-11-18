from .models import Notification


def notify(users, message, link=""):
    """Create an in-app notification for each user. Keep `message` free of personal data."""
    Notification.objects.bulk_create([Notification(user=u, message=message[:300], link=link) for u in users])
