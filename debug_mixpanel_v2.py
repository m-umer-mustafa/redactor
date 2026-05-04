import sys
sys.path.insert(0, '.')
import json
import threading
import time
from analytics import get_analytics, AnalyticsClient, _MIXPANEL_AVAILABLE

print(f"Mixpanel available: {_MIXPANEL_AVAILABLE}")

# Mocking the _send_mixpanel to see errors
original_send_mixpanel = AnalyticsClient._send_mixpanel

def debug_send_mixpanel(self, event_name, params):
    print(f"Attempting to send Mixpanel event: {event_name}")
    try:
        self._mp.track(self.client_id, event_name, params)
        print(f"Mixpanel track() called for {event_name}")
    except Exception as e:
        print(f"MIX_PANEL_ERROR: {e}")

AnalyticsClient._send_mixpanel = debug_send_mixpanel

with open('config.json') as f:
    c = json.load(f)

AnalyticsClient.initialise(
    measurement_id=c.get('ga4_measurement_id'),
    api_secret=c.get('ga4_api_secret'),
    client_id=c.get('ga4_client_id'),
    mixpanel_token=c.get('mixpanel_token')
)

analytics = get_analytics()
analytics.track('debug_event', {'test': True})

# Wait for threads
time.sleep(5)
print("Done waiting.")
