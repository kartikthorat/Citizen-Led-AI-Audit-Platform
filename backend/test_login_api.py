import requests
import json

# Test admin login API directly
url = "http://127.0.0.1:8000/api/auth/token"
data = {
    "username": "admin",
    "password": "adminpassword"
}

print("Testing admin login API...")
print(f"URL: {url}")
print(f"Data: {data}")

try:
    response = requests.post(url, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Success! Token: {result.get('access_token', 'N/A')[:50]}...")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        
except Exception as e:
    print(f"Exception: {e}")
