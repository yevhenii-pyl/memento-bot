import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.tasks.models import Task


async def get_by_id(session: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def create_task(
    session: AsyncSession,
    assignee_id: uuid.UUID,
    overseer_id: uuid.UUID,
    title: str,
    deadline: datetime,
) -> Task:
    task = Task(
        id=uuid.uuid4(),
        assignee_id=assignee_id,
        overseer_id=overseer_id,
        title=title,
        deadline=deadline,
        status="open",
    )
    session.add(task)
    await session.flush()
    return task


async def set_pending(session: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_by_id(session, task_id)
    if task is not None:
        task.status = "pending"
        task.updated_at = datetime.now(UTC)
        await session.flush()


async def update_status(session: AsyncSession, task_id: uuid.UUID, status: str) -> None:
    task = await get_by_id(session, task_id)
    if task is not None:
        task.status = status
        task.resolved_at = datetime.now(UTC)
        task.updated_at = datetime.now(UTC)
        await session.flush()


async def record_extension(
    session: AsyncSession, task_id: uuid.UUID, new_deadline: datetime
) -> None:
    task = await get_by_id(session, task_id)
    if task is not None:
        task.deadline = new_deadline
        task.status = "open"
        task.extension_count += 1
        task.extension_timestamp = datetime.now(UTC)
        task.updated_at = datetime.now(UTC)
        await session.flush()


async def get_open_by_assignee(session: AsyncSession, assignee_id: uuid.UUID) -> list[Task]:
    result = await session.execute(
        select(Task).where(Task.assignee_id == assignee_id, Task.status == "open")
    )
    return list(result.scalars().all())
