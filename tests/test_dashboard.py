def test_dashboard_overview(client, supervisor_token):
    response = client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_screenings" in data
    assert "normal_count" in data
    assert "mam_count" in data
    assert "sam_count" in data
    assert "average_confidence" in data


def test_dashboard_rbac_forbidden_for_worker(client, worker_token):
    # Worker role should not be allowed to access supervisor dashboard
    response = client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 403
    assert "Operation not permitted" in response.json()["detail"]


def test_dashboard_trends(client, supervisor_token):
    response = client.get(
        "/dashboard/trends?days=14",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert response.status_code == 200
    assert "points" in response.json()
    assert isinstance(response.json()["points"], list)


def test_dashboard_locations(client, supervisor_token):
    response = client.get(
        "/dashboard/locations",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_dashboard_export_csv(client, supervisor_token):
    response = client.get(
        "/dashboard/export",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Scan ID,Created At,Child ID" in response.text
    assert "Age Category" in response.text


def test_dashboard_overview_age_filtering(client, supervisor_token, worker_token):
    import io
    # Submit an adult scan and a child scan
    client.post(
        "/scans",
        data={"child_id": "child-uuid-001", "worker_id": "worker-uuid-001", "age_category": "adult"},
        files={"image": ("adult.jpg", io.BytesIO(b"adult"), "image/jpeg")},
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    client.post(
        "/scans",
        data={"child_id": "child-uuid-001", "worker_id": "worker-uuid-001", "age_category": "child_6_59m"},
        files={"image": ("child.jpg", io.BytesIO(b"child"), "image/jpeg")},
        headers={"Authorization": f"Bearer {worker_token}"},
    )

    # Default overview (child only)
    res_default = client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert res_default.status_code == 200
    child_count = res_default.json()["total_screenings"]

    # Adult overview
    res_adult = client.get(
        "/dashboard/overview?age_category=adult",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert res_adult.status_code == 200
    adult_count = res_adult.json()["total_screenings"]
    assert adult_count >= 1

    # All overview
    res_all = client.get(
        "/dashboard/overview?age_category=all",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert res_all.status_code == 200
    all_count = res_all.json()["total_screenings"]
    assert all_count == child_count + adult_count


def test_dashboard_flagged_age_category(client, supervisor_token):
    response = client.get(
        "/dashboard/flagged",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    if len(records) > 0:
        assert "age_category" in records[0]
        assert records[0]["age_category"] in ["child_6_59m", "adult"]
