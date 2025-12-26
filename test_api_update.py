import requests
import json

def update_keys():
    url = "http://localhost:8080/api/settings"
    # Get current settings first
    current = requests.get(url).json()
    
    # Update with new dummy key to see if it changes
    current['real_app_key'] = 'UPDATED_KEY_TEST_123'
    
    res = requests.post(url, json=current)
    print(f"Update Result: {res.status_code}")
    print(f"Body: {res.text}")

    # Verify
    verified = requests.get(url).json()
    print(f"Verified Key: {verified.get('real_app_key')}")

if __name__ == "__main__":
    update_keys()
