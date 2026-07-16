import requests

# Test the exact same format as frontend (FormData)
url = "http://127.0.0.1:8000/api/auth/token"

# Test 1: Form data (like frontend)
print("=== Test 1: FormData (like frontend) ===")
formData = {
    "username": "admin",
    "password": "adminpassword"
}

try:
    response = requests.post(url, data=formData)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: JSON (alternative)
print("\n=== Test 2: JSON ===")
jsonData = {
    "username": "admin", 
    "password": "adminpassword"
}

try:
    response = requests.post(url, json=jsonData)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Check CORS headers
print("\n=== Test 3: Check CORS ===")
try:
    response = requests.options(url, headers={"Origin": "http://localhost:3000"})
    print(f"OPTIONS Status: {response.status_code}")
    print(f"CORS Headers: {dict(response.headers)}")
except Exception as e:
    print(f"CORS Error: {e}")
