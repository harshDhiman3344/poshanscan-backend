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


def test_supervisor_login_success(client):
    response = client.post(
        "/supervisor/login",
        json={"phone": "9000000000", "password": "super123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token" in data
    assert data["role"] == "supervisor"


def test_supervisor_login_admin(client):
    response = client.post(
        "/supervisor/login",
        json={"phone": "admin", "password": "admin"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] in ["admin", "supervisor"]


def test_supervisor_login_worker_forbidden(client):
    # Frontline worker should be rejected with 403 on supervisor portal
    response = client.post(
        "/supervisor/login",
        json={"phone": "9876543210", "password": "worker123"},
    )
    assert response.status_code == 403
    assert "Only supervisors and administrators" in response.json()["detail"]
