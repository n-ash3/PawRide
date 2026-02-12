from fastapi.testclient import TestClient

from tests.helpers import auth_user


def test_matching_respects_crate_requirement_and_recurring_plan_created(client: TestClient) -> None:
    parent_token, _ = auth_user(client, "+15550002101", "Parent")
    admin_token, _ = auth_user(client, "+15550002102", "Admin", ["admin"])
    driver_a_token, driver_a_id = auth_user(client, "+15550002103", "Driver A", ["driver"])
    driver_b_token, driver_b_id = auth_user(client, "+15550002104", "Driver B", ["driver"])

    client.post(
        "/auth/switch-role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()

    dog = client.post(
        "/dogs",
        json={"name": "Crate Pup", "size": "medium", "special_needs": "crate needed"},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    dog.raise_for_status()
    dog_id = dog.json()["id"]

    for token, has_crate, driver_id in [
        (driver_a_token, False, driver_a_id),
        (driver_b_token, True, driver_b_id),
    ]:
        client.post(
            "/drivers/become-driver",
            json={"create_profile_if_missing": True},
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()
        client.put(
            "/drivers/me/profile",
            json={"has_crate": has_crate, "max_dog_size": "xlarge", "max_dogs_per_ride": 2},
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()
        client.post(
            f"/admin/drivers/{driver_id}/approval",
            json={"approval_status": "approved"},
            headers={"Authorization": f"Bearer {admin_token}"},
        ).raise_for_status()
        client.post(
            "/drivers/me/online",
            json={"is_online": True},
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()

    with client.websocket_connect(f"/ws/drivers/{driver_a_id}/location?token={driver_a_token}") as ws_a:
        ws_a.send_json({"latitude": 37.775, "longitude": -122.419})
    with client.websocket_connect(f"/ws/drivers/{driver_b_id}/location?token={driver_b_token}") as ws_b:
        ws_b.send_json({"latitude": 37.7751, "longitude": -122.4191})

    ride = client.post(
        "/rides",
        json={
            "dog_id": dog_id,
            "pickup_address": "1 A St",
            "pickup_latitude": 37.7749,
            "pickup_longitude": -122.4194,
            "dropoff_address": "2 B St",
            "dropoff_type": "daycare",
            "distance_km": 2.2,
            "duration_minutes": 10,
            "recurring_rule": "daily",
            "auto_dispatch": True,
        },
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    ride.raise_for_status()
    ride_id = ride.json()["id"]

    offers_a = client.get("/drivers/me/offers", headers={"Authorization": f"Bearer {driver_a_token}"})
    offers_b = client.get("/drivers/me/offers", headers={"Authorization": f"Bearer {driver_b_token}"})
    offers_a.raise_for_status()
    offers_b.raise_for_status()
    assert offers_a.json() == []
    assert len(offers_b.json()) == 1

    plans = client.get("/rides/recurring/plans", headers={"Authorization": f"Bearer {parent_token}"})
    plans.raise_for_status()
    assert len(plans.json()) == 1

    attempts = client.get(f"/rides/{ride_id}/dispatch/attempts", headers={"Authorization": f"Bearer {parent_token}"})
    attempts.raise_for_status()
    assert attempts.json()[0]["driver_user_id"] == driver_b_id
