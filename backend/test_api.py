
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_admin_api():
    # 1. Login
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/api/auth/token", data={
        "username": "admin",
        "password": "adminpassword"
    })
    
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Fetch Analytics
    print("\nFetching Analytics...")
    resp = requests.get(f"{BASE_URL}/api/admin/analytics", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Data: {resp.text[:500]}") # Print first 500 chars

    # 3. Fetch Users
    print("\nFetching Users...")
    resp = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Data: {resp.text[:500]}")

if __name__ == "__main__":
    test_admin_api()
