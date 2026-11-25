# Encrypted personal data

These columns are stored **encrypted** in the database, so a database dump, a backup or someone with read access to
PostgreSQL sees only unreadable text (`enc1:...`):

| Table | Columns |
|---|---|
| `accounts_user` | `email`, `phone`, `employee_id` (EID), `cid` |
| `complaints_complaint` | `reference` (the generated complaint number), `cid`, `phone`, `email` |
| `core_emaillog`, `core_smslog` | `reference` |
| `core_ndiverification` | `cid` |

The application decrypts them automatically for signed-in users who are allowed to see them. Nothing in the web
interface shows how to decrypt, and the key is never sent to the browser.

Not encrypted: the audit log, the notification and API logs and the service-provider contact addresses. The audit log is
append-only (a database trigger blocks changes), so it cannot be rewritten.

## How it works

* Algorithm: **AES-SIV** (RFC 5297, `cryptography` library), 256-bit key. It is *deterministic*: the same value gives the
  same ciphertext. That is what lets the system still find a user by email or CID and still enforce "one account per
  email / CID / EID".
* Each column kind (`email`, `phone`, `cid`, `eid`, `ref`) is bound to the ciphertext, so the same number in two different kinds
  of column looks different.
* Values are normalised before encryption: emails are lower-case, employee IDs and complaint references upper-case, all are trimmed.
* Blank values stay blank.
* Stored format: `enc1:` + URL-safe base64 of the AES-SIV output. `enc1` is the format version.
* Code: `backend/core/fields.py`. Models use `EncryptedCharField` / `EncryptedEmailField`.

What this means in practice: exact searches work (`email=`, `email__iexact=`, `cid=`, `__in`). Partial searches
(`icontains`, `startswith`; for example typing half of a reference number) and sorting by these columns do **not** work on the database. Users are sorted by name.

## The key

`FIELD_ENCRYPTION_KEY` (environment variable / Kubernetes secret `cms-secrets`): 32 random bytes, URL-safe base64.

Make one:

    python3 -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

* It is **required** when `DJANGO_DEBUG=0`; the server refuses to start without it.
* Keep it in the secret store, **separate from the database and its backups**, and keep an offline copy. **If the key
  is lost the data cannot be recovered.** If it changes, existing rows become unreadable.
* In development (`DJANGO_DEBUG=1`) with no key set, a key is derived from `DJANGO_SECRET_KEY`. Do not change
  `DJANGO_SECRET_KEY` in development after data was created, or set `FIELD_ENCRYPTION_KEY` before the first run.

## How to decrypt (for administrators only)

### A. Through the application (normal)

Use the CMS. The models return plain values. From a Django shell on the server:

    docker compose exec backend python manage.py shell
    >>> from accounts.models import User
    >>> User.objects.get(email="someone@example.org").phone

### B. A single value from a database dump

On a machine that has the key, with `pip install cryptography`:

    # decrypt.py  usage:  FIELD_ENCRYPTION_KEY=... python3 decrypt.py <purpose> <enc1:value>
    # purpose is email, phone, cid, eid or ref (complaint reference), according to the column (see the table above:
    # accounts_user.employee_id is "eid", every cid column is "cid")
    import base64, os, sys
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV

    key = os.environ["FIELD_ENCRYPTION_KEY"]
    key = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    purpose, value = sys.argv[1], sys.argv[2]
    assert value.startswith("enc1:"), "not an encrypted value"
    token = base64.urlsafe_b64decode(value[5:])
    print(AESSIV(key).decrypt(token, [purpose.encode()]).decode())

If the key was derived in development (no `FIELD_ENCRYPTION_KEY`), the key is
`hashlib.sha256(b"dev-field-encryption:" + DJANGO_SECRET_KEY.encode()).digest()`.

### C. To encrypt a value for a search in SQL

    docker compose exec backend python manage.py shell -c "from core.fields import encrypt; print(encrypt('someone@example.org', 'email'))"

Then: `select id from accounts_user where email = '<that output>';`

## Moving or restoring

* Restore a database backup together with the **same** `FIELD_ENCRYPTION_KEY`.
* The migration `accounts/0015`, `complaints/0018`, `core/0020` encrypted the rows that existed. New rows are encrypted when saved.

## Changing the key (rotation)

There is no automatic rotation yet. To rotate: with the old key set, run a script that reads every row through the model
and keeps a copy of the plain values in memory, switch `FIELD_ENCRYPTION_KEY` to the new key, and save them again
(`Model.objects.filter(pk=...).update(field=value)`). Back up the database first.
