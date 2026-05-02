"""
analytics.py — Dual analytics integration for The Redactor.

Sends events to TWO backends simultaneously:
  1. GA4 Measurement Protocol  — landing page funnel continuity
  2. Mixpanel Python SDK        — real-time desktop app event visibility

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
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

try:
    from mixpanel import Mixpanel as _MixpanelSDK
    _MIXPANEL_AVAILABLE = True
except ImportError:
    _MIXPANEL_AVAILABLE = False

# ─── Configuration ────────────────────────────────────────────────────────────
# Replace these placeholders after you create your GA4 property.
# You can also override them via config.json keys:
#   "ga4_measurement_id" and "ga4_api_secret"
GA4_MEASUREMENT_ID = "G-XXXXXXXXXX"   # e.g. G-ABC123DEF4
GA4_API_SECRET = "YOUR_API_SECRET"    # from GA4 → Admin → Measurement Protocol secrets

GA4_ENDPOINT = (
    "https://www.google-analytics.com/mp/collect"
    "?measurement_id={measurement_id}&api_secret={api_secret}"
)

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
        mixpanel_token: Optional[str] = None,
    ):
        self.measurement_id = measurement_id
        self.api_secret = api_secret
        # Persistent anonymous client ID (stored in config.json as "ga4_client_id")
        self.client_id = client_id or str(uuid.uuid4())
        self._enabled = (
            ANALYTICS_ENABLED
            and self.measurement_id != "G-XXXXXXXXXX"
            and self.api_secret != "YOUR_API_SECRET"
        )
        # Mixpanel — real-time event visibility for desktop app
        self._mp = None
        if _MIXPANEL_AVAILABLE and mixpanel_token:
            self._mp = _MixpanelSDK(mixpanel_token)

    @classmethod
    def get_instance(cls) -> "AnalyticsClient":
        if cls._instance is None:
            cls._instance = AnalyticsClient()
        return cls._instance

    @classmethod
    def initialise(
        cls,
        measurement_id: str,
        api_secret: str,
        client_id: Optional[str] = None,
        mixpanel_token: Optional[str] = None,
    ) -> "AnalyticsClient":
        """Call once at app startup with values from config.json."""
        cls._instance = AnalyticsClient(
            measurement_id, api_secret, client_id, mixpanel_token
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
                target=self._send, args=(payload,),
                daemon=True, name=f"ga4-{event_name}"
            ).start()
        # Mixpanel — real-time visibility
        if self._mp is not None:
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

    def _send(self, payload: bytes) -> None:
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
        """Send event to Mixpanel. Shows instantly in Mixpanel Live View."""
        try:
            self._mp.track(self.client_id, event_name, params)
        except Exception:
            pass  # Fail silently — never block the UI


# ─── Module-level convenience accessor ────────────────────────────────────────

def get_analytics() -> AnalyticsClient:
    """Return the singleton analytics client. Always safe to call."""
    return AnalyticsClient.get_instance()
