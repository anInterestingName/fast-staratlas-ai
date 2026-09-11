from fastapi.testclient import TestClient


def test_list_demo_items(client: TestClient) -> None:
    response = client.get("/api/v1/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "star-atlas"


def test_list_demo_items_with_filter(client: TestClient) -> None:
    response = client.get("/api/v1/demo", params={"q": "missing"})
    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": []}


def test_get_demo_item(client: TestClient) -> None:
    response = client.get("/api/v1/demo/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_demo_item_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/demo/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Demo item not found"


def test_create_demo_item(client: TestClient) -> None:
    response = client.post(
        "/api/v1/demo",
        json={"name": "nebula", "message": "Created by the demo API"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 2
    assert body["name"] == "nebula"
    assert body["message"] == "Created by the demo API"

    listed = client.get("/api/v1/demo")
    assert listed.json()["total"] == 2
