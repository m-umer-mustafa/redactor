import requests
import json
import base64

token = "8f0e92980afd4b99f70e4e2a2b3f0839"
event = {
    "event": "Raw_POST_Requests_Test",
    "properties": {
        "distinct_id": "test_id_123",
        "token": token,
        "test": True
    }
}

data = base64.b64encode(json.dumps(event).encode()).decode()
data_payload = {
    'data': data,
    'verbose': 1,
    'ip': 0
}
url = "https://api.mixpanel.com/track"

try:
    print(f"Sending POST request to: {url}")
    response = requests.post(url, data=data_payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
