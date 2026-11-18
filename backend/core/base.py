import uuid

from django.db import models


class UUIDModel(models.Model):
    """Random UUID primary keys: ids in URLs/APIs reveal nothing about volume or ordering."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
