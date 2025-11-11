import os

from fastapi.testclient import TestClient

from src.server.app import create_app, get_todo_repository


def create_test_client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "api_todos.db"
    monkeypatch.setenv("AI_SECRETARY_TODO_DB_PATH", str(db_path))
    get_todo_repository.cache_clear()
    app = create_app()
    return TestClient(app)


def test_todo_api_crud_flow(tmp_path, monkeypatch):
    client = create_test_client(tmp_path, monkeypatch)

    resp = client.get("/api/todos")
    assert resp.status_code == 200
    assert resp.json() == []

    create_payload = {
        "title": "Prepare slides",
        "description": "For Friday meeting",
        "due_date": "2025-12-10",
        "status": "pending",
    }
    resp = client.post("/api/todos", json=create_payload)
    assert resp.status_code == 200
    todo = resp.json()
    assert todo["title"] == create_payload["title"]
    todo_id = todo["id"]

    patch_payload = {"status": "done", "due_date": None}
    resp = client.patch(f"/api/todos/{todo_id}", json=patch_payload)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "done"
    assert updated["due_date"] is None

    resp = client.delete(f"/api/todos/{todo_id}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    resp = client.get("/api/todos")
    assert resp.status_code == 200
    assert resp.json() == []
