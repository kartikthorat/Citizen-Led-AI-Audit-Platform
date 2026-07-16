import requests

# Test browser preview URL directly
browser_preview_url = "http://127.0.0.1:56521"
backend_url = "http://127.0.0.1:8000/api/auth/token"

print("=== Testing browser preview CORS ===")
print(f"Browser preview URL: {browser_preview_url}")
print(f"Backend URL: {backend_url}")

# Test CORS with browser preview origin
try:
    response = requests.options(backend_url, headers={
        "Origin": browser_preview_url,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"
    })
    print(f"OPTIONS Status: {response.status_code}")
    print(f"Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'NOT SET')}")
    print(f"Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'NOT SET')}")
except Exception as e:
    print(f"CORS test failed: {e}")

# Test direct login from browser preview origin
print("\n=== Direct login test ===")
try:
    response = requests.post(backend_url, 
        data={"username": "admin", "password": "adminpassword"},
        headers={"Origin": browser_preview_url}
    )
    print(f"POST Status: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print(f"Direct login failed: {e}")
