from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from core import audit
from core.notifications import notify

from .models import Complaint, InternalStatus, StatusHistory, next_reference


@transaction.atomic
def create_complaint(data, *, channel, registered_by=None, request=None):
    """Create a complaint with a unique, sequential reference number."""
    complaint = Complaint(
        **data,
        channel=channel,
        registered_by=registered_by,
        internal_status=InternalStatus.SUBMITTED,
        reference=next_reference(timezone.now()),
    )
    complaint.save()
    StatusHistory.objects.create(
        complaint=complaint, previous_status="", new_status=InternalStatus.SUBMITTED,
        actor=registered_by, reason=f"Complaint registered via {channel}",
    )
    audit.log(
        request, "complaint.create", actor=registered_by, entity_type="complaint", entity_id=complaint.pk,
        detail={"reference": complaint.reference, "channel": channel},
    )
    recipients = User.objects.filter(role=Role.SUPER_ADMIN, is_active=True)
    if registered_by:
        recipients = recipients.exclude(pk=registered_by.pk)
    notify(recipients, f"New complaint {complaint.reference} received via {channel.replace('_', ' ')}", f"/staff/complaints/{complaint.pk}")
    return complaint
