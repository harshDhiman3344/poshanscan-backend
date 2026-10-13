import io
import json


def test_offline_sync(client, worker_token):
    metadata = [
        {
            "client_scan_id": "offline-client-001",
            "child_id": "child-uuid-001",
            "worker_id": "worker-uuid-001",
            "captured_at": "2026-09-20T16:00:00Z",
            "reference_type": "aruco",
            "reference_size_mm": 50.0,
        },
        {
            "client_scan_id": "offline-client-002",
            "child_id": "child-uuid-001",
            "worker_id": "worker-uuid-001",
            "captured_at": "2026-09-20T16:05:00Z",
            "reference_type": "aruco",
            "reference_size_mm": 50.0,
        },
    ]

    files = [
        ("images", ("offline-client-001.jpg", io.BytesIO(b"img1"), "image/jpeg")),
        ("images", ("offline-client-002.jpg", io.BytesIO(b"img2"), "image/jpeg")),
    ]

    response = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["client_scan_id"] == "offline-client-001"
    assert results[1]["client_scan_id"] == "offline-client-002"
    assert results[0]["muac_estimate_mm"] > 0
    assert results[1]["muac_estimate_mm"] > 0


def test_offline_sync_idempotency(client, worker_token):
    metadata = [
        {
            "client_scan_id": "offline-client-001",
            "child_id": "child-uuid-001",
            "worker_id": "worker-uuid-001",
        }
    ]
    files = [
        ("images", ("offline-client-001.jpg", io.BytesIO(b"img1"), "image/jpeg")),
    ]

    # Post same scan twice
    res = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res.status_code == 200
    first_scan_id = res.json()[0]["scan_id"]

    res2 = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res2.status_code == 200
    # Should return existing scan ID (idempotency key preserved)
    assert res2.json()[0]["scan_id"] == first_scan_id


def test_offline_sync_age_category(client, worker_token):
    metadata = [
        {
            "client_scan_id": "sync-adult-101",
            "child_id": "child-uuid-001",
            "worker_id": "worker-uuid-001",
            "age_category": "adult",
        },
        {
            "client_scan_id": "sync-child-102",
            "child_id": "child-uuid-001",
            "worker_id": "worker-uuid-001",
            "age_category": "child_6_59m",
        },
    ]
    files = [
        ("images", ("sync-adult-101.jpg", io.BytesIO(b"adult"), "image/jpeg")),
        ("images", ("sync-child-102.jpg", io.BytesIO(b"child"), "image/jpeg")),
    ]

    res = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert items[0]["age_category"] == "adult"
    assert items[0]["muac_estimate_mm"] >= 195.0
    assert items[1]["age_category"] == "child_6_59m"
    assert items[1]["muac_estimate_mm"] < 150.0
