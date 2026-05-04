import sys
sys.path.insert(0, '.')
import json, time
from analytics import get_analytics, AnalyticsClient

with open('config.json') as f:
    c = json.load(f)

AnalyticsClient.initialise(
    measurement_id="G-XXXXXXXXXX",
    api_secret="YOUR_API_SECRET",
    client_id=c.get('ga4_client_id'),
    mixpanel_token=c.get('mixpanel_token')
)

print('Mixpanel token:', c.get('mixpanel_token'))
analytics = get_analytics()
print('Client ID:', analytics.client_id)
analytics.track('test_event', {'from': 'script'})
print('Event sent! Waiting 5s...')
time.sleep(5)
