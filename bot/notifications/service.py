import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.tasks.models import Task


def _fmt_deadline(deadline: datetime, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    return deadline.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")


def build_reminder_text(task: Task, worker_name: str, timezone: str) -> str:
    return (
        f"⏰ Reminder: your task \"{task.title}\" is due at "
        f"{_fmt_deadline(task.deadline, timezone)}."
    )


def build_outcome_prompt_text(task: Task, worker_name: str, timezone: str) -> str:
    return (
        f"Task deadline reached!\n"
        f"Worker: {worker_name}\n"
        f"Task: {task.title}\n"
        f"Deadline: {_fmt_deadline(task.deadline, timezone)}\n\n"
        f"Please record the outcome:"
    )


def build_outcome_keyboard(task_id: uuid.UUID) -> InlineKeyboardMarkup:
    tid = str(task_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Done", callback_data=f"done:{tid}"),
                InlineKeyboardButton(text="❌ Failed", callback_data=f"failed:{tid}"),
                InlineKeyboardButton(text="⏳ Extended", callback_data=f"extended:{tid}"),
            ]
        ]
    )


def build_failed_notification_text(task: Task) -> str:
    return f"Your task \"{task.title}\" was marked as failed by the Master."


def build_extended_notification_text(task: Task, new_deadline: datetime, timezone: str) -> str:
    return (
        f"Your task \"{task.title}\" deadline has been extended to "
        f"{_fmt_deadline(new_deadline, timezone)}."
    )
