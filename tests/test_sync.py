import io
import json


def test_offline_sync(client, worker_token):
    # Register two distinct children for batch sync
    r1 = client.post(
        "/children",
        json={"name": "Sync Child 1", "dob": "2024-01-01", "gender": "F", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    r2 = client.post(
        "/children",
        json={"name": "Sync Child 2", "dob": "2024-01-02", "gender": "M", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    c1_id = r1.json()["id"]
    c2_id = r2.json()["id"]

    metadata = [
        {
            "client_scan_id": "offline-client-001",
            "child_id": c1_id,
            "worker_id": "worker-uuid-001",
            "captured_at": "2026-09-20T16:00:00Z",
            "reference_type": "aruco",
            "reference_size_mm": 50.0,
            "age_category": "child_6_59m",
        },
        {
            "client_scan_id": "offline-client-002",
            "child_id": c2_id,
            "worker_id": "worker-uuid-001",
            "captured_at": "2026-09-20T16:05:00Z",
            "reference_type": "aruco",
            "reference_size_mm": 50.0,
            "age_category": "child_6_59m",
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
    assert results[0].get("error") is None
    assert results[1].get("error") is None


def test_offline_sync_duplicate_rejected(client, worker_token):
    """
    If a child already has an online scan in DB, offline sync for the same person
    and age category must return error='scan_already_exists'.
    """
    metadata = [
        {
            "client_scan_id": "offline-dup-already-scanned",
            "child_id": "child-uuid-001",
            "worker_id": "worker-uuid-001",
            "age_category": "child_6_59m",
        }
    ]
    files = [
        ("images", ("offline-dup-already-scanned.jpg", io.BytesIO(b"img_dup"), "image/jpeg")),
    ]

    res = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res.status_code == 200
    item = res.json()[0]
    assert item["error"] == "scan_already_exists"
    assert item["client_scan_id"] == "offline-dup-already-scanned"
    assert item["child_id"] == "child-uuid-001"
    assert item["age_category"] == "child_6_59m"
    assert item["scan_id"] is not None


def test_offline_sync_batch_duplicate_items(client, worker_token):
    """
    If a batch contains two scans for the SAME child and age category,
    the first must succeed and the second must be rejected with scan_already_exists.
    """
    reg = client.post(
        "/children",
        json={"name": "Batch Dup Child", "dob": "2024-04-01", "gender": "F", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    b_id = reg.json()["id"]

    metadata = [
        {
            "client_scan_id": "batch-dup-001",
            "child_id": b_id,
            "worker_id": "worker-uuid-001",
            "age_category": "child_6_59m",
        },
        {
            "client_scan_id": "batch-dup-002",
            "child_id": b_id,
            "worker_id": "worker-uuid-001",
            "age_category": "child_6_59m",
        },
    ]
    files = [
        ("images", ("batch-dup-001.jpg", io.BytesIO(b"img1"), "image/jpeg")),
        ("images", ("batch-dup-002.jpg", io.BytesIO(b"img2"), "image/jpeg")),
    ]

    res = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 2
    # First item succeeds
    assert results[0]["client_scan_id"] == "batch-dup-001"
    assert results[0].get("error") is None
    assert results[0]["scan_id"] is not None

    # Second item gets scan_already_exists error
    assert results[1]["client_scan_id"] == "batch-dup-002"
    assert results[1]["error"] == "scan_already_exists"
    assert results[1]["scan_id"] == results[0]["scan_id"]


def test_offline_sync_idempotency(client, worker_token):
    reg = client.post(
        "/children",
        json={"name": "Idempotent Child", "dob": "2024-05-01", "gender": "M", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    idemp_child_id = reg.json()["id"]

    metadata = [
        {
            "client_scan_id": "offline-client-idemp-001",
            "child_id": idemp_child_id,
            "worker_id": "worker-uuid-001",
        }
    ]
    files = [
        ("images", ("offline-client-idemp-001.jpg", io.BytesIO(b"img1"), "image/jpeg")),
    ]

    # Post scan first time
    res = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res.status_code == 200
    first_scan_id = res.json()[0]["scan_id"]

    # Post exact same client_scan_id again (network retry)
    res2 = client.post(
        "/sync",
        data={"metadata": json.dumps(metadata)},
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert res2.status_code == 200
    # Should return existing scan ID (idempotency key preserved, no duplicate created)
    assert res2.json()[0]["scan_id"] == first_scan_id
    assert res2.json()[0].get("error") is None


def test_offline_sync_separate_age_categories(client, worker_token):
    reg = client.post(
        "/children",
        json={"name": "Dual Sync Child", "dob": "2024-06-01", "gender": "F", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    dual_id = reg.json()["id"]

    metadata = [
        {
            "client_scan_id": "sync-adult-101",
            "child_id": dual_id,
            "worker_id": "worker-uuid-001",
            "age_category": "adult",
        },
        {
            "client_scan_id": "sync-child-102",
            "child_id": dual_id,
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
    assert items[0].get("error") is None
    assert items[1]["age_category"] == "child_6_59m"
    assert items[1].get("error") is None
