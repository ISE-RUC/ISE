import requests
import os

os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""

session = requests.Session()
session.trust_env = False

# Login
login_url = "http://127.0.0.1:8000/api/users/login"
resp = session.post(login_url, json={"username": "leader_demo", "password": "party1234"})
print("Login:", resp.status_code, resp.text)

# Fetch CSRF token
resp = session.get("http://127.0.0.1:8000/certificate/new/")
csrf_token = session.cookies.get("csrftoken")

# Post to certificate
cert_url = "http://127.0.0.1:8000/api/certificate/"
headers = {"X-CSRFToken": csrf_token}
payload = {
    "certificate_type": "party-member",
    "purpose": "test purpose",
    "attachment_note": "test attachment"
}

resp = session.post(cert_url, json=payload, headers=headers)
print("Create Cert Status:", resp.status_code)
print("Create Cert Response:", resp.text)
