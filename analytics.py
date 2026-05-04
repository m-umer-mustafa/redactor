"""
analytics.py — Dual analytics integration for The Redactor.

Sends events to TWO backends simultaneously:
  1. GA4 Measurement Protocol  — landing page funnel continuity
  2. Mixpanel Direct API       — real-time desktop app event visibility (Zero Dependencies)

All calls fire in background threads and fail silently.
Offline use is fully preserved.

Event catalogue (mapped to Phase 4B KPIs):
  app_opened          — session start (retention / DAU signal)
  onboarding_complete — user completed first-run setup
  file_added          — file dropped into batch queue
  analysis_complete   — ML engine finished PII detection
  review_opened       — user opened the review page (engagement signal)
  export_saved        — ★ PRIMARY KPI: user completed full workflow
  export_failed       — redaction save failed
  settings_saved      — user changed configuration
"""

import json
import threading
import uuid
import base64
import time
import sys
from typing import Optional
from urllib import request as urllib_request
from urllib import parse as urllib_parse
from urllib.error import URLError

# ─── Configuration ────────────────────────────────────────────────────────────
# Default properties. Can be overridden via config.json keys:
#   "ga4_measurement_id", "ga4_api_secret", and "mixpanel_token"
GA4_MEASUREMENT_ID = "G-S1MR2W37VM"
GA4_API_SECRET = "aMG4hFD9T7WvKZo6DEckSA"
MIXPANEL_TOKEN = "8f0e92980afd4b99f70e4e2a2b3f0839"

GA4_ENDPOINT = (
    "https://www.google-analytics.com/mp/collect"
    "?measurement_id={measurement_id}&api_secret={api_secret}"
)
MIXPANEL_ENDPOINT = "https://api.mixpanel.com/track"

# Set to False to disable all analytics (e.g. in CI / testing)
ANALYTICS_ENABLED = True

# Network timeout in seconds — keep short so offline use is unaffected
REQUEST_TIMEOUT = 3


# ─── Client ───────────────────────────────────────────────────────────────────

class AnalyticsClient:
    """
    Singleton analytics client. Initialise once with optional config overrides,
    then call .track(event_name, params) anywhere in the app.
    Sends to GA4 (Measurement Protocol) AND Mixpanel simultaneously.
    """

    _instance: Optional["AnalyticsClient"] = None

    def __init__(
        self,
        measurement_id: str = GA4_MEASUREMENT_ID,
        api_secret: str = GA4_API_SECRET,
        client_id: Optional[str] = None,
        mixpanel_token: Optional[str] = MIXPANEL_TOKEN,
    ):
        self.measurement_id = measurement_id
        self.api_secret = api_secret
        self.mixpanel_token = mixpanel_token
        # Persistent anonymous client ID (stored in config.json as "ga4_client_id")
        self.client_id = client_id or str(uuid.uuid4())
        self._enabled = (
            ANALYTICS_ENABLED
            and self.measurement_id != "G-XXXXXXXXXX"
            and self.api_secret != "YOUR_API_SECRET"
        )

    @classmethod
    def get_instance(cls) -> "AnalyticsClient":
        if cls._instance is None:
            cls._instance = AnalyticsClient()
        return cls._instance

    @classmethod
    def initialise(
        cls,
        measurement_id: Optional[str] = None,
        api_secret: Optional[str] = None,
        client_id: Optional[str] = None,
        mixpanel_token: Optional[str] = None,
    ) -> "AnalyticsClient":
        """Call once at app startup with values from config.json."""
        m_id = measurement_id if measurement_id else GA4_MEASUREMENT_ID
        secret = api_secret if api_secret else GA4_API_SECRET
        mp_token = mixpanel_token if mixpanel_token else MIXPANEL_TOKEN
        cls._instance = AnalyticsClient(
            m_id, secret, client_id, mp_token
        )
        return cls._instance

    # ── Public API ────────────────────────────────────────────────────────────

    def track(self, event_name: str, params: Optional[dict] = None) -> None:
        """
        Fire an event to GA4 + Mixpanel in background threads.
        Fails silently — never raises, never blocks the UI.
        """
        p = params or {}
        # GA4 Measurement Protocol
        if self._enabled:
            payload = self._build_payload(event_name, p)
            threading.Thread(
                target=self._send_ga4, args=(payload,),
                daemon=True, name=f"ga4-{event_name}"
            ).start()
        
        # Mixpanel Direct API Call
        if self.mixpanel_token:
            threading.Thread(
                target=self._send_mixpanel, args=(event_name, p),
                daemon=True, name=f"mp-{event_name}"
            ).start()

    # ── Convenience event methods (match Phase 4B KPIs) ───────────────────────

    def app_opened(self) -> None:
        """Fired once per session at startup. Measures DAU / retention."""
        self.track("app_opened", {"engagement_type": "session_start"})

    def onboarding_complete(self, user_name_length: int) -> None:
        """User finished first-run name entry."""
        self.track("onboarding_complete", {"name_length": user_name_length})

    def file_added(self, file_extension: str, file_count: int) -> None:
        """File(s) dropped into the batch queue."""
        self.track("file_added", {
            "file_extension": file_extension,
            "batch_size": file_count,
        })

    def analysis_complete(self, entity_count: int, file_extension: str) -> None:
        """ML engine finished PII detection — ready for review."""
        self.track("analysis_complete", {
            "entity_count": entity_count,
            "file_extension": file_extension,
        })

    def review_opened(self, entity_count: int) -> None:
        """User opened the Review page — strong engagement signal."""
        self.track("review_opened", {"entity_count": entity_count})

    def export_saved(
        self,
        approved_count: int,
        rejected_count: int,
        file_extension: str,
    ) -> None:
        """
        ★ PRIMARY KPI EVENT — user completed the full workflow.
        Fired when Apply & Save succeeds. This is the Task Completion Rate
        numerator for Phase 4B.
        """
        self.track("export_saved", {
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "file_extension": file_extension,
            "completion": 1,   # always 1 — used to count completions in GA4
        })

    def export_failed(self, file_extension: str) -> None:
        """Redaction save failed — helps identify drop-off cause."""
        self.track("export_failed", {"file_extension": file_extension})

    def settings_saved(self, entity_count: int, threshold: float) -> None:
        """User customised detection settings."""
        self.track("settings_saved", {
            "target_entity_count": entity_count,
            "confidence_threshold": threshold,
        })

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_payload(self, event_name: str, params: dict) -> bytes:
        body = {
            "client_id": self.client_id,
            # debug_mode makes events appear in GA4 DebugView
            # (Realtime does not reliably show Measurement Protocol events)
            "debug_mode": 1,
            "events": [
                {
                    "name": event_name,
                    "params": {
                        "engagement_time_msec": "100",
                        **params,
                    },
                }
            ],
        }
        return json.dumps(body).encode("utf-8")

    def _send_ga4(self, payload: bytes) -> None:
        try:
            url = GA4_ENDPOINT.format(
                measurement_id=self.measurement_id,
                api_secret=self.api_secret,
            )
            req = urllib_request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT):
                pass  # GA4 returns 204 No Content on success
        except (URLError, OSError):
            pass  # Network unavailable — fail silently

    def _send_mixpanel(self, event_name: str, params: dict) -> None:
        """Send event to Mixpanel using direct urllib for maximum reliability."""
        try:
            # Add Mixpanel special properties
            # Note: properties must include 'token' and 'distinct_id'
            properties = {
                "token": self.mixpanel_token,
                "distinct_id": self.client_id,
                "time": int(time.time()),
                "$insert_id": uuid.uuid4().hex,
                "mp_lib": "python-urllib",
            }
            properties.update(params)
            
            payload = {
                "event": event_name,
                "properties": properties
            }
            
            # Mixpanel prefers base64 encoded JSON for the 'data' parameter
            data_json = json.dumps(payload).encode("utf-8")
            encoded_data = base64.b64encode(data_json).decode("utf-8")
            
            # verbose=1 makes Mixpanel return a JSON object with status
            post_params = {
                "data": encoded_data,
                "verbose": 1,
                "ip": 0
            }
            encoded_params = urllib_parse.urlencode(post_params).encode("utf-8")
            
            req = urllib_request.Request(MIXPANEL_ENDPOINT, data=encoded_params, method="POST")
            with urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                resp_body = response.read().decode("utf-8")
                resp_json = json.loads(resp_body)
                if resp_json.get("status") != 1:
                    # In production, we fail silently, but we can print to stderr for debug
                    print(f"Mixpanel API Error: {resp_json.get('error')}", file=sys.stderr)
        except Exception:
            pass  # Fail silently — never block the UI


# ─── Module-level convenience accessor ────────────────────────────────────────

def get_analytics() -> AnalyticsClient:
    """Return the singleton analytics client. Always safe to call."""
    return AnalyticsClient.get_instance()
