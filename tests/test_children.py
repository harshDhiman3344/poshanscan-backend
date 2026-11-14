def test_search_children(client, worker_token):
    response = client.get(
        "/children/search?q=Aarav",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert items[0]["name"] == "Aarav Kumar"
    assert items[0]["village"] == "Rampur"
    assert "id" in items[0]
    assert "child_id" in items[0]
    assert items[0]["id"] == items[0]["child_id"]
    assert "has_child_scan" in items[0]
    assert "has_adult_scan" in items[0]
    assert "scans" in items[0]


def test_register_child(client, worker_token):
    new_child_payload = {
        "name": "Diya Sharma",
        "dob": "2024-05-10",
        "gender": "F",
        "guardian_name": "Meena Sharma",
        "village": "Rampur",
    }
    response = client.post(
        "/children",
        json=new_child_payload,
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Diya Sharma"
    assert "child_id" in data
    assert "id" in data
    assert data["id"] == data["child_id"]
    assert data["has_child_scan"] is False
    assert data["has_adult_scan"] is False
    assert data["scans"] == []


def test_child_scan_status_endpoint(client, worker_token):
    # Check scan status for child before scanning
    response = client.get(
        "/children/child-uuid-001/scan-status?age_category=child_6_59m",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["child_id"] == "child-uuid-001"
    assert "has_scanned" in res
    assert "already_scanned" in res
    assert "scans" in res
