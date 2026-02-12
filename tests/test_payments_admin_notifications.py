from fastapi.testclient import TestClient

from tests.helpers import auth_user


def _complete_ride(client: TestClient, ride_id: str, driver_token: str) -> None:
    for status_value in [
        "driver_en_route",
        "arrived_at_pickup",
        "dog_picked_up",
        "in_transit",
        "arrived_at_dropoff",
        "dog_delivered",
        "completed",
    ]:
        client.post(
            f"/rides/{ride_id}/status",
            json={"status": status_value},
            headers={"Authorization": f"Bearer {driver_token}"},
        ).raise_for_status()


def test_subscription_discount_disputes_and_admin_settings(client: TestClient) -> None:
    parent_token, _ = auth_user(client, "+15550002201", "Parent")
    admin_token, _ = auth_user(client, "+15550002202", "Admin", ["admin"])
    driver_token, driver_id = auth_user(client, "+15550002203", "Driver", ["driver"])

    client.post(
        "/auth/switch-role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()

    dog = client.post(
        "/dogs",
        json={"name": "Milo", "size": "small"},
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
        json={"has_crate": True, "max_dog_size": "xlarge", "max_dogs_per_ride": 3},
        headers={"Authorization": f"Bearer {driver_token}"},
    ).raise_for_status()
    client.post(
        f"/admin/drivers/{driver_id}/approval",
        json={"approval_status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()

    payment_method = client.post(
        "/payments/methods",
        json={
            "provider_method_id": "pm_test_b",
            "brand": "visa",
            "last4": "1111",
            "exp_month": 10,
            "exp_year": 2031,
            "is_default": True,
        },
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    payment_method.raise_for_status()
    method_id = payment_method.json()["id"]

    ride_1 = client.post(
        "/rides",
        json={
            "dog_id": dog_id,
            "pickup_address": "100 Main St",
            "dropoff_address": "200 Main St",
            "dropoff_type": "daycare",
            "distance_km": 4,
            "duration_minutes": 16,
            "auto_dispatch": False,
        },
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    ride_1.raise_for_status()
    ride_id_1 = ride_1.json()["id"]

    client.post(
        f"/rides/{ride_id_1}/assign-driver",
        json={"driver_user_id": driver_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()
    _complete_ride(client, ride_id_1, driver_token)

    charge_1 = client.post(
        "/payments/charge",
        json={"ride_id": ride_id_1, "payment_method_id": method_id},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    charge_1.raise_for_status()
    first_discount = charge_1.json()["discount_amount"]

    subscribe = client.post(
        "/payments/subscription/subscribe",
        json={"plan_code": "PAWRIDE_PASS"},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    subscribe.raise_for_status()

    ride_2 = client.post(
        "/rides",
        json={
            "dog_id": dog_id,
            "pickup_address": "300 Main St",
            "dropoff_address": "400 Main St",
            "dropoff_type": "daycare",
            "distance_km": 4,
            "duration_minutes": 16,
            "auto_dispatch": False,
        },
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    ride_2.raise_for_status()
    ride_id_2 = ride_2.json()["id"]

    client.post(
        f"/rides/{ride_id_2}/assign-driver",
        json={"driver_user_id": driver_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).raise_for_status()
    _complete_ride(client, ride_id_2, driver_token)

    charge_2 = client.post(
        "/payments/charge",
        json={"ride_id": ride_id_2, "payment_method_id": method_id},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    charge_2.raise_for_status()
    second_discount = charge_2.json()["discount_amount"]

    assert second_discount > first_discount

    dispute = client.post(
        "/disputes",
        json={"ride_id": ride_id_1, "reason": "route_issue", "details": "Driver route was longer than expected"},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    dispute.raise_for_status()
    dispute_id = dispute.json()["id"]

    resolved = client.post(
        f"/admin/disputes/{dispute_id}/resolve",
        json={"status": "resolved", "resolution_note": "Reviewed and resolved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolved.raise_for_status()
    assert resolved.json()["status"] == "resolved"

    setting = client.post(
        "/admin/settings",
        json={"key": "commission_rate", "value": "0.25"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    setting.raise_for_status()
    assert setting.json()["key"] == "commission_rate"

    notifications = client.get("/notifications/me", headers={"Authorization": f"Bearer {parent_token}"})
    notifications.raise_for_status()
    assert len(notifications.json()) > 0
