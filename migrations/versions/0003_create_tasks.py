"""Create tasks table.

Promoted from docs/features/memento-task-core/migrations/02_create_tasks.up.sql

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("assignee_id", sa.UUID(), nullable=False),
        sa.Column("overseer_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.Column("extension_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extension_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'pending', 'done', 'failed')",
            name="tasks_status_check",
        ),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["overseer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tasks_assignee_status", "tasks", ["assignee_id", "status"])
    op.create_index("idx_tasks_overseer_id", "tasks", ["overseer_id"])


def downgrade() -> None:
    op.drop_index("idx_tasks_overseer_id", table_name="tasks")
    op.drop_index("idx_tasks_assignee_status", table_name="tasks")
    op.drop_table("tasks")
