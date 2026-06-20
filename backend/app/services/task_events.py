from typing import Any

from sqlalchemy.orm import Session

from app.models.generation import GenerationTask, GenerationTaskEvent


def log_task_event(
    db: Session,
    task: GenerationTask,
    stage: str,
    message: str,
    *,
    level: str = "info",
    progress: int | None = None,
    account_id: int | None = None,
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    event = GenerationTaskEvent(
        task_id=task.id,
        stage=stage,
        message=message,
        level=level,
        progress=progress,
        account_id=account_id or task.account_id,
        request=request,
        response=response,
        meta=meta or {},
    )
    db.add(event)
    if commit:
        db.commit()
