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
