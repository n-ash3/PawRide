from fastapi.testclient import TestClient


def auth_user(client: TestClient, phone: str, name: str, roles: list[str] | None = None) -> tuple[str, str]:
    otp = client.post("/auth/request-otp", json={"phone_number": phone})
    otp.raise_for_status()
    code = otp.json()["dev_code"]
    payload = {"phone_number": phone, "code": code, "name": name}
    if roles:
        payload["requested_roles"] = roles
    verify = client.post("/auth/verify-otp", json=payload)
    verify.raise_for_status()
    body = verify.json()
    return body["access_token"], body["user"]["id"]
