import pytest

from app import app, init_database


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        "app.DATABASE",
        str(database_path)
    )

    init_database()

    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "healthy"


def test_add_service(client, monkeypatch):
    monkeypatch.setattr(
        "app.perform_health_check",
        lambda service_id: True
    )

    response = client.post(
        "/add",
        data={
            "name": "Google",
            "url": "https://www.google.com",
            "threshold": "1000"
        }
    )

    assert response.status_code == 302

    response = client.get("/api/services")

    assert response.status_code == 200

    data = response.get_json()

    assert len(data) == 1
    assert data[0]["name"] == "Google"


def test_invalid_service(client):
    response = client.post(
        "/add",
        data={
            "name": "",
            "url": "invalid-url",
            "threshold": "-100"
        }
    )

    assert response.status_code == 400


def test_api_services(client):
    response = client.get("/api/services")

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)
