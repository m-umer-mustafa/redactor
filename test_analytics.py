import sys
sys.path.insert(0, '.')
import json, time
from analytics import get_analytics, AnalyticsClient

with open('config.json') as f:
    c = json.load(f)

AnalyticsClient.initialise(
    measurement_id=c.get('ga4_measurement_id'),
    api_secret=c.get('ga4_api_secret'),
    client_id=c.get('ga4_client_id'),
    mixpanel_token=c.get('mixpanel_token')
)

print('Mixpanel token:', c.get('mixpanel_token'))
get_analytics().track('test_event', {'from': 'script'})
print('Event sent! Waiting 2s...')
time.sleep(2)
