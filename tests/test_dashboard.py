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
    assert isinstance(response.json(), list)


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
