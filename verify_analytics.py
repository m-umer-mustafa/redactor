import sys
sys.path.insert(0, '.')
import json
import time
from analytics import get_analytics, AnalyticsClient

with open('config.json') as f:
    c = json.load(f)

AnalyticsClient.initialise(
    measurement_id=c.get('ga4_measurement_id'),
    api_secret=c.get('ga4_api_secret'),
    client_id=c.get('ga4_client_id'),
    mixpanel_token=c.get('mixpanel_token')
)

analytics = get_analytics()
print(f"Tracking event to Mixpanel (Token: {analytics.mixpanel_token[:4]}...)")
analytics.track('Direct_Urllib_Test', {'platform': sys.platform, 'type': 'verification'})

print("Event fired. Waiting 5s for background threads to complete...")
time.sleep(5)
print("Done.")
