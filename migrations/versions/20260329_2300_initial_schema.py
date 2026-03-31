"""initial schema

Revision ID: 20260329_2300
Revises:
Create Date: 2026-03-29 23:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_2300"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("working_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_services_agent_key"), "agent_services", ["agent_key"], unique=True)
    op.create_index(op.f("ix_agent_services_id"), "agent_services", ["id"], unique=False)

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=100), nullable=False),
        sa.Column("agent_key", sa.String(length=100), nullable=False),
        sa.Column("instance_id", sa.String(length=100), nullable=True),
        sa.Column("task_content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="queued"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_logs_agent_key"), "task_logs", ["agent_key"], unique=False)
    op.create_index(op.f("ix_task_logs_id"), "task_logs", ["id"], unique=False)
    op.create_index(op.f("ix_task_logs_task_id"), "task_logs", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_logs_task_id"), table_name="task_logs")
    op.drop_index(op.f("ix_task_logs_id"), table_name="task_logs")
    op.drop_index(op.f("ix_task_logs_agent_key"), table_name="task_logs")
    op.drop_table("task_logs")

    op.drop_index(op.f("ix_agent_services_id"), table_name="agent_services")
    op.drop_index(op.f("ix_agent_services_agent_key"), table_name="agent_services")
    op.drop_table("agent_services")
