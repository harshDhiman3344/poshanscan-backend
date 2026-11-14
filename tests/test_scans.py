import io
import concurrent.futures
from app.models.child import Child
from app.models.scan import Scan


def test_submit_scan(client, worker_token):
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
    assert res["age_category"] == "child_6_59m"
    assert res["muac_estimate_mm"] > 0
    assert res["risk_band"] in ["NORMAL", "MAM", "SAM"]
    assert 0.0 <= res["confidence_score"] <= 1.0


def test_submit_scan_duplicate_conflict(client, worker_token):
    """
    Submitting a second scan for the same person and same age category must be rejected
    with HTTP 409 Conflict and error code 'scan_already_exists'.
    """
    fake_image = io.BytesIO(b"second image bytes")

    data = {
        "child_id": "child-uuid-001",
        "worker_id": "worker-uuid-001",
        "client_scan_id": "client-scan-dup-9999",
        "age_category": "child_6_59m",
    }
    files = {
        "image": ("test_scan_dup.jpg", fake_image, "image/jpeg"),
    }

    response = client.post(
        "/scans",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 409
    res = response.json()
    assert res["error"] == "scan_already_exists"
    assert res["child_id"] == "child-uuid-001"
    assert res["age_category"] == "child_6_59m"
    assert "scan_id" in res
    assert "status" in res
    assert "created_at" in res
    # Ensure sensitive details and raw photo path are NOT exposed
    assert "image_path" not in res
    assert "muac_estimate_mm" not in res
    assert "quality_flags" not in res


def test_submit_scan_adult(client, worker_token):
    """
    Separate age category (adult) for the same person is allowed.
    """
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
    assert res["muac_estimate_mm"] >= 195.0
    assert res["risk_band"] in ["NORMAL", "MAM", "SAM"]


def test_submit_scan_adult_duplicate_conflict(client, worker_token):
    """
    Submitting a duplicate adult scan for the same person must also be rejected with 409.
    """
    fake_image = io.BytesIO(b"another adult image bytes")
    data = {
        "child_id": "child-uuid-001",
        "worker_id": "worker-uuid-001",
        "client_scan_id": "client-scan-adult-002",
        "age_category": "adult",
    }
    files = {
        "image": ("test_adult_dup.jpg", fake_image, "image/jpeg"),
    }
    response = client.post(
        "/scans",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 409
    res = response.json()
    assert res["error"] == "scan_already_exists"
    assert res["age_category"] == "adult"


def test_separate_age_categories_for_new_person(client, worker_token):
    """
    Verify that a single person can have exactly one child scan and one adult scan,
    and neither allows a second duplicate.
    """
    # 1. Register a dedicated child
    reg_res = client.post(
        "/children",
        json={
            "name": "Karan Dual",
            "dob": "2023-08-15",
            "gender": "M",
            "guardian_name": "Sita Dual",
            "village": "Rampur",
        },
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert reg_res.status_code == 201
    dual_id = reg_res.json()["id"]

    # 2. Submit child scan -> 200
    f1 = io.BytesIO(b"dual child img")
    r_child = client.post(
        "/scans",
        data={"child_id": dual_id, "worker_id": "worker-uuid-001", "age_category": "child_6_59m"},
        files={"image": ("c.jpg", f1, "image/jpeg")},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert r_child.status_code == 200

    # 3. Submit adult scan -> 200
    f2 = io.BytesIO(b"dual adult img")
    r_adult = client.post(
        "/scans",
        data={"child_id": dual_id, "worker_id": "worker-uuid-001", "age_category": "adult"},
        files={"image": ("a.jpg", f2, "image/jpeg")},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert r_adult.status_code == 200

    # 4. Duplicate child scan -> 409
    f3 = io.BytesIO(b"dual child img 2")
    r_child_dup = client.post(
        "/scans",
        data={"child_id": dual_id, "worker_id": "worker-uuid-001", "age_category": "child_6_59m"},
        files={"image": ("c2.jpg", f3, "image/jpeg")},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert r_child_dup.status_code == 409
    assert r_child_dup.json()["error"] == "scan_already_exists"

    # 5. Duplicate adult scan -> 409
    f4 = io.BytesIO(b"dual adult img 2")
    r_adult_dup = client.post(
        "/scans",
        data={"child_id": dual_id, "worker_id": "worker-uuid-001", "age_category": "adult"},
        files={"image": ("a2.jpg", f4, "image/jpeg")},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert r_adult_dup.status_code == 409
    assert r_adult_dup.json()["error"] == "scan_already_exists"


def test_concurrent_scan_submissions(client, worker_token):
    """
    Verify atomic enforcement: when two concurrent submissions arrive for the same child
    and age category, exactly one succeeds (200) and the other is rejected (409 Conflict).
    """
    # Register dedicated child
    reg = client.post(
        "/children",
        json={"name": "Race Child", "dob": "2024-02-01", "gender": "F", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert reg.status_code == 201
    race_child_id = reg.json()["id"]

    def submit_race(idx):
        img = io.BytesIO(f"race image {idx}".encode("utf-8"))
        return client.post(
            "/scans",
            data={
                "child_id": race_child_id,
                "worker_id": "worker-uuid-001",
                "client_scan_id": f"race-scan-{idx}",
                "age_category": "child_6_59m",
            },
            files={"image": (f"race_{idx}.jpg", img, "image/jpeg")},
            headers={"Authorization": f"Bearer {worker_token}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futs = [executor.submit(submit_race, 1), executor.submit(submit_race, 2)]
        responses = [f.result() for f in futs]

    status_codes = sorted([r.status_code for r in responses])
    assert status_codes == [200, 409], f"Expected exactly one 200 and one 409, got {status_codes}"

    conflict_res = next(r.json() for r in responses if r.status_code == 409)
    assert conflict_res["error"] == "scan_already_exists"
    assert conflict_res["child_id"] == race_child_id


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


def test_submit_scan_fallback_undefined_child(client, worker_token):
    # Register dedicated child for undefined fallback test so it has no existing scan
    reg = client.post(
        "/children",
        json={"name": "Fallback Child", "dob": "2024-03-01", "gender": "M", "village": "Rampur"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert reg.status_code == 201

    fake_image = io.BytesIO(b"fallback child image bytes")
    data = {
        "child_id": "undefined",
        "worker_id": "worker-uuid-001",
        "client_scan_id": "client-scan-fallback-001",
    }
    files = {
        "image": ("test_fallback.jpg", fake_image, "image/jpeg"),
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
    assert "id" in res
    assert res["id"] == res["scan_id"]
    assert res["child_id"] is not None
    assert len(res["child_id"]) > 0


def test_get_scan_by_id(client, worker_token):
    response = client.get(
        "/scans/client-scan-fallback-001",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["client_scan_id"] == "client-scan-fallback-001"
    assert "id" in res
    assert "scan_id" in res
    assert res["age_category"] == "child_6_59m"


def test_scan_status_after_scanning(client, worker_token):
    # Aarav Kumar (child-uuid-001) has both child and adult scans now
    response = client.get(
        "/children/child-uuid-001/scan-status?age_category=child_6_59m",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["child_id"] == "child-uuid-001"
    assert res["has_scanned"] is True
    assert res["already_scanned"] is True
    assert res["existing_scan_id"] is not None
    assert res["age_category"] == "child_6_59m"
    assert res["status"] == "synced"
    assert len(res["scans"]) >= 1
