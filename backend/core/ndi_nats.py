"""Background NATS listener for Bhutan NDI proof results.

For each proof request we know its thread id; NDI publishes the verification result on a NATS subject named after
it. One long-lived connection runs on a daemon thread; `watch(thread_id)` subscribes. When a result arrives the
disclosed attributes are written to the matching NdiVerification row, which the sign-in status endpoint polls.
If NATS cannot be reached the listener stays dormant and logs; sign-in then simply times out.
"""
import asyncio
import base64
import json
import logging
import threading

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger("ndi.nats")


def _server_url():
    n = settings.NDI
    host = n["NATS_HOST"].replace("https://", "").replace("http://", "").rstrip("/")
    return f"tls://{host}:{n['NATS_PORT']}"


def _decode(raw):
    """NATS message body -> presentation-result dict. NDI wraps it as {"pattern": thid, "data": {...}}."""
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        try:
            obj = json.loads(base64.b64decode(raw).decode("utf-8"))
        except Exception:
            return {}
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, dict):
            obj = data
        elif isinstance(data, str):
            try:
                obj = json.loads(base64.b64decode(data).decode("utf-8"))
            except Exception:
                pass
    return obj if isinstance(obj, dict) else {}


def _attr_value(val):
    """Scalar out of a revealed attribute: a list of {"value": ...}, a dict, or a plain string."""
    if isinstance(val, list):
        val = val[0] if val else None
    if isinstance(val, dict):
        return val.get("value") or val.get("raw") or val.get("raw_value")
    return val


def _find_attr(obj, name):
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == name:
                v = _attr_value(val)
                if v is not None:
                    return v
            found = _find_attr(val, name)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_attr(item, name)
            if found is not None:
                return found
    return None


def _is_validated(payload):
    blob = json.dumps(payload).lower()
    if any(s in blob for s in ("proofvalidated", "presentation_acked", '"verified":true', '"verified": true', 'verification_result":"true"')):
        return True
    return str(payload.get("verification_result", "")).lower() in ("proofvalidated", "true", "verified")


def normalize_payload(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def persist(thread_id, payload):
    """Write a parsed result onto the NdiVerification row. Only a pending row can change."""
    from .models import NdiVerification
    payload = normalize_payload(payload)
    rec = NdiVerification.objects.filter(pk=thread_id, status="pending").first()
    if not rec:
        return
    if _is_validated(payload):
        rec.status = "verified"
        rec.cid = str(_find_attr(payload, "ID Number") or "")[:64]
        rec.full_name = str(_find_attr(payload, "Full Name") or "")[:200]
        rec.holder_did = str(payload.get("relationship_did") or payload.get("connection_id") or payload.get("holder_did") or "")[:200]
    elif any(s in json.dumps(payload).lower() for s in ("abandoned", "rejected", "declined", "failed")):
        rec.status = "failed"
    else:
        return
    rec.save()
    logger.info("NDI result stored for %s -> %s", thread_id[:8], rec.status)


def _persist_in_worker(thread_id, payload):
    """Runs on an executor thread: manage that thread's own database connection."""
    close_old_connections()
    try:
        persist(thread_id, payload)
    finally:
        close_old_connections()


class _Listener:
    def __init__(self):
        self._loop = None
        self._nc = None
        self._thread = None
        self._ready = threading.Event()
        self._watching = set()
        self._lock = threading.Lock()

    def ensure_started(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(target=self._run, name="ndi-nats", daemon=True)
            self._thread.start()

    def watch(self, thread_id):
        self.ensure_started()
        if not self._ready.wait(timeout=8):
            logger.warning("NDI NATS not ready; cannot watch %s", thread_id[:8])
            return False
        fut = asyncio.run_coroutine_threadsafe(self._subscribe(thread_id), self._loop)
        try:
            fut.result(timeout=8)
            return True
        except Exception as exc:
            logger.warning("NDI NATS subscribe failed for %s: %s", thread_id[:8], exc)
            return False

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
            self._loop.run_forever()
        except Exception as exc:
            logger.error("NDI NATS listener stopped: %s", exc)

    async def _connect(self):
        import nats
        try:
            self._nc = await nats.connect(servers=[_server_url()], nkeys_seed_str=settings.NDI["NATS_SEED"], connect_timeout=15,
                                          max_reconnect_attempts=-1, reconnect_time_wait=2, name="bicma-cms-ndi")
            logger.info("NDI NATS connected")
            self._ready.set()
        except Exception as exc:
            logger.error("NDI NATS connection failed: %s", exc)

    async def _subscribe(self, thread_id):
        async def handler(msg):
            payload = _decode(msg.data)
            if payload:
                await self._loop.run_in_executor(None, _persist_in_worker, thread_id, payload)  # the ORM is synchronous
        await self._nc.subscribe(thread_id, cb=handler)
        logger.info("NDI NATS watching %s", thread_id[:8])


listener = _Listener()


def watch(thread_id):
    return listener.watch(thread_id)
