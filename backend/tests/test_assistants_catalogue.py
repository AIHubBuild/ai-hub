from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_catalogue_returns_ok_with_envelope():
    response = client.get("/api/v1/assistants")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["message"], str)
    assert isinstance(body["data"], list)


def test_catalogue_lists_two_assistants_in_expected_order():
    body = client.get("/api/v1/assistants").json()

    ids = [entry["id"] for entry in body["data"]]
    assert ids == ["resume-ats", "it-support-copilot"]


def test_testing_framework_is_not_in_public_catalogue():
    body = client.get("/api/v1/assistants").json()

    ids = [entry["id"] for entry in body["data"]]
    assert "ai-testing-framework" not in ids


def test_catalogue_entry_structure():
    body = client.get("/api/v1/assistants").json()

    for entry in body["data"]:
        assert set(entry.keys()) == {
            "id",
            "name",
            "description",
            "status",
            "capabilities",
            "launch_url",
            "repository_url",
        }
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["description"], str) and entry["description"]
        assert entry["status"] in {"available", "in_development"}
        assert isinstance(entry["capabilities"], list)


def test_no_assistant_has_an_unverified_launch_url():
    body = client.get("/api/v1/assistants").json()

    for entry in body["data"]:
        assert entry["launch_url"] is None


def test_every_assistant_has_a_repository_reference():
    body = client.get("/api/v1/assistants").json()

    for entry in body["data"]:
        assert entry["repository_url"].startswith(
            "https://github.com/akinselureabiola/"
        )


def test_existing_assistants_are_available_with_capabilities():
    body = client.get("/api/v1/assistants").json()

    for entry in body["data"]:
        if entry["status"] == "available":
            assert len(entry["capabilities"]) > 0


def test_health_endpoints_still_work():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
