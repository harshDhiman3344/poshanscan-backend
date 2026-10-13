import io


def test_submit_scan(client, worker_token):
    # Mock image bytes
    fake_image = io.BytesIO(b"fake image bytes for testing")

    data = {
        "child_id": "child-uuid-001",
        "worker_id": "worker-uuid-001",
        "client_scan_id": "client-scan-12345",
        "captured_at": "2026-09-20T17:00:00Z",
        "reference_type": "aruco",
        "reference_size_mm": "50.0",
    }
    files = {
        "image": ("test_scan.jpg", fake_image, "image/jpeg"),
    }

    response = client.post(
        "/scans",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    res = response.json()
    assert "scan_id" in res
    assert res["child_id"] == "child-uuid-001"
    assert res["muac_estimate_mm"] > 0
    assert res["risk_band"] in ["NORMAL", "MAM", "SAM"]
    assert 0.0 <= res["confidence_score"] <= 1.0


def test_submit_scan_missing_child(client, worker_token):
    fake_image = io.BytesIO(b"fake image bytes")
    data = {
        "child_id": "non-existent-child-uuid",
        "worker_id": "worker-uuid-001",
    }
    files = {
        "image": ("test_scan.jpg", fake_image, "image/jpeg"),
    }
    response = client.post(
        "/scans",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 404


def test_submit_scan_adult(client, worker_token):
    fake_image = io.BytesIO(b"adult image bytes")
    data = {
        "child_id": "child-uuid-001",
        "worker_id": "worker-uuid-001",
        "client_scan_id": "client-scan-adult-001",
        "age_category": "adult",
    }
    files = {
        "image": ("test_adult.jpg", fake_image, "image/jpeg"),
    }
    response = client.post(
        "/scans",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["age_category"] == "adult"
    # Adult mock scale generates MUAC between 200mm and 260mm
    assert res["muac_estimate_mm"] >= 195.0
    assert res["risk_band"] in ["NORMAL", "MAM", "SAM"]


def test_submit_scan_default_child(client, worker_token):
    fake_image = io.BytesIO(b"child image bytes")
    data = {
        "child_id": "child-uuid-001",
        "worker_id": "worker-uuid-001",
        "client_scan_id": "client-scan-child-002",
        # age_category omitted -> should default to child_6_59m
    }
    files = {
        "image": ("test_child.jpg", fake_image, "image/jpeg"),
    }
    response = client.post(
        "/scans",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["age_category"] == "child_6_59m"
    # Child scale MUAC between 105mm and 135mm
    assert res["muac_estimate_mm"] < 150.0
