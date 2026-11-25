"""Encrypted database fields for personal data (email, phone, CID, employee ID).

The database stores only ciphertext ("enc1:" + base64). Python code still sees the normal plain value, so views,
serializers and the admin keep working. Encryption is AES-SIV (RFC 5297), which is *deterministic*: the same value always
gives the same ciphertext, so exact lookups (`email=...`, `email__iexact=...`, `__in`) and unique constraints still work.
The price is that partial matches (`__icontains`, `__startswith`, ordering by the value) cannot work on these fields.

The key comes from the FIELD_ENCRYPTION_KEY setting. How to read the data back: see docs/ENCRYPTION.md.
"""
import base64
import hashlib

from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.lookups import Exact

PREFIX = "enc1:"
_NORMALISE = {"email": lambda v: v.strip().lower(), "eid": lambda v: v.strip().upper(), "cid": str.strip, "ref": lambda v: v.strip().upper(), "phone": str.strip}


def get_key():
    """The 32 or 64 byte key from FIELD_ENCRYPTION_KEY (urlsafe base64). Development without one derives a key from SECRET_KEY."""
    raw = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if raw:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(key) not in (32, 48, 64):
            raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be 32, 48 or 64 random bytes, urlsafe-base64 encoded.")
        return key
    if not settings.DEBUG:
        raise ImproperlyConfigured("Set FIELD_ENCRYPTION_KEY. It protects the encrypted personal data and must be kept safe and backed up.")
    return hashlib.sha256(b"dev-field-encryption:" + settings.SECRET_KEY.encode()).digest()


def encrypt(value, purpose):
    value = _NORMALISE[purpose](value)
    if not value or value.startswith(PREFIX):
        return value
    token = AESSIV(get_key()).encrypt(value.encode(), [purpose.encode()])
    return PREFIX + base64.urlsafe_b64encode(token).decode()


def decrypt(value, purpose):
    if not value or not value.startswith(PREFIX):  # blank, or a row not encrypted yet
        return value
    token = base64.urlsafe_b64decode(value[len(PREFIX):])
    return AESSIV(get_key()).decrypt(token, [purpose.encode()]).decode()


class _EncryptedMixin:
    def __init__(self, *args, purpose, **kwargs):
        self.purpose = purpose
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["purpose"] = self.purpose
        return name, path, args, kwargs

    def get_internal_type(self):
        return "TextField"  # ciphertext is longer than max_length, which still limits the plain value

    def from_db_value(self, value, expression, connection):
        return decrypt(value, self.purpose)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt(value, self.purpose) if isinstance(value, str) else value


class _EncryptedIExact(Exact):
    """Values are stored case-normalised, so a case-insensitive match is an exact match on the ciphertext."""
    lookup_name = "iexact"


class EncryptedCharField(_EncryptedMixin, models.CharField):
    pass


class EncryptedEmailField(_EncryptedMixin, models.EmailField):
    pass


for _cls in (EncryptedCharField, EncryptedEmailField):
    _cls.register_lookup(_EncryptedIExact)


def encrypt_existing(apps, app_label, model_name, field_names):
    """Used by the migrations that switch a column to encryption: turn the plain values already stored into ciphertext."""
    Model = apps.get_model(app_label, model_name)
    for name in field_names:
        for pk, value in Model.objects.exclude(**{name: None}).exclude(**{name: ""}).values_list("pk", name):
            Model.objects.filter(pk=pk).update(**{name: value})  # saving through the field encrypts it
