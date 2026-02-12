from fastapi.testclient import TestClient

from tests.helpers import auth_user


def test_full_dispatch_camera_payment_flow(client: TestClient) -> None:
    parent_token, _ = auth_user(client, "+15550002001", "Parent")
    admin_token, _ = auth_user(client, "+15550002002", "Admin", ["admin"])
    driver_token, driver_id = auth_user(client, "+15550002003", "Driver", ["driver"])

    client.post(
        "/auth/switch-role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()

    dog = client.post(
        "/dogs",
        json={"name": "Buddy", "size": "large", "special_needs": "crate"},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    dog.raise_for_status()
    dog_id = dog.json()["id"]

    client.post(
        "/drivers/become-driver",
        json={"create_profile_if_missing": True},
        headers={"Authorization": f"Bearer {driver_token}"},
    ).raise_for_status()
    client.put(
        "/drivers/me/profile",
        json={
            "vehicle_make": "Honda",
            "vehicle_model": "CRV",
            "has_crate": True,
            "max_dog_size": "xlarge",
            "max_dogs_per_ride": 2,
        },
        headers={"Authorization": f"Bearer {driver_token}"},
    ).raise_for_status()
    client.post(
        f"/admin/drivers/{driver_id}/approval",
        json={"approval_status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()
    client.post(
        "/drivers/me/online",
        json={"is_online": True},
        headers={"Authorization": f"Bearer {driver_token}"},
    ).raise_for_status()

    with client.websocket_connect(f"/ws/drivers/{driver_id}/location?token={driver_token}") as ws:
        ws.send_json({"latitude": 37.775, "longitude": -122.419, "heading": 90, "speed_kph": 30})

    ride = client.post(
        "/rides",
        json={
            "dog_id": dog_id,
            "dog_count": 1,
            "pickup_address": "1 Market St",
            "pickup_latitude": 37.7749,
            "pickup_longitude": -122.4194,
            "dropoff_address": "200 Pine St",
            "dropoff_latitude": 37.792,
            "dropoff_longitude": -122.399,
            "dropoff_type": "daycare",
            "distance_km": 3.4,
            "duration_minutes": 14,
            "auto_dispatch": True,
        },
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    ride.raise_for_status()
    ride_id = ride.json()["id"]

    offers = client.get("/drivers/me/offers", headers={"Authorization": f"Bearer {driver_token}"})
    offers.raise_for_status()
    assert len(offers.json()) == 1

    respond = client.post(
        f"/rides/{ride_id}/dispatch/respond",
        json={"accept": True},
        headers={"Authorization": f"Bearer {driver_token}"},
    )
    respond.raise_for_status()
    assert respond.json()["action"] == "accepted"

    for status_value in [
        "driver_en_route",
        "arrived_at_pickup",
        "dog_picked_up",
        "in_transit",
        "arrived_at_dropoff",
        "dog_delivered",
        "completed",
    ]:
        update = client.post(
            f"/rides/{ride_id}/status",
            json={"status": status_value},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        update.raise_for_status()

    method = client.post(
        "/payments/methods",
        json={
            "provider_method_id": "pm_test_a",
            "brand": "visa",
            "last4": "4242",
            "exp_month": 12,
            "exp_year": 2030,
            "is_default": True,
        },
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    method.raise_for_status()
    method_id = method.json()["id"]

    charge = client.post(
        "/payments/charge",
        json={"ride_id": ride_id, "payment_method_id": method_id, "tip_amount": 4},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    charge.raise_for_status()
    assert charge.json()["status"] == "charged"

    payouts = client.get("/payments/payouts/me", headers={"Authorization": f"Bearer {driver_token}"})
    payouts.raise_for_status()
    assert len(payouts.json()) >= 1
