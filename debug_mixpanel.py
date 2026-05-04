import sys
sys.path.insert(0, '.')
import json
from mixpanel import Mixpanel

token = "8f0e92980afd4b99f70e4e2a2b3f0839"
mp = Mixpanel(token)

try:
    print(f"Sending test event to Mixpanel with token: {token}")
    mp.track('test_user_id', 'Direct_Test_Event', {'property': 'value'})
    print("Success: Event sent (buffered or sent).")
except Exception as e:
    print(f"Error sending to Mixpanel: {e}")
