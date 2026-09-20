def test_login_success(client):
    response = client.post(
        "/auth/login",
        json={"phone": "9876543210", "password": "worker123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "worker"
    assert data["user_id"] == "worker-uuid-001"


def test_login_invalid_password(client):
    response = client.post(
        "/auth/login",
        json={"phone": "9876543210", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Incorrect phone number or password" in response.json()["detail"]


def test_get_me(client, worker_token):
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "9876543210"
    assert data["role"] == "worker"
