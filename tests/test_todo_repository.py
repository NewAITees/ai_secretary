from datetime import date

from src.todo.repository import TodoRepository, TodoStatus


def test_todo_repository_crud_cycle(tmp_path):
    repo = TodoRepository(db_path=tmp_path / "todo.db")

    created = repo.create(
        title="Write report",
        description="Quarterly numbers",
        due_date="2025-12-01",
        status=TodoStatus.IN_PROGRESS,
    )
    assert created.title == "Write report"
    assert created.status is TodoStatus.IN_PROGRESS

    items = repo.list()
    assert len(items) == 1

    updated = repo.update(
        created.id,
        status=TodoStatus.DONE,
        due_date=None,
        description="Finished and sent",
    )
    assert updated is not None
    assert updated.status is TodoStatus.DONE
    assert updated.due_date is None
    assert "Finished" in updated.description

    assert repo.delete(created.id) is True
    assert repo.list() == []
