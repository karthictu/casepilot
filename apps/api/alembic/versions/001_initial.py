"""Initial schema: cases, hitl_items, audit_events (append-only on Postgres).

Revision ID: 001
Revises:
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(64), nullable=False, unique=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("from_address", sa.String(320), nullable=False, server_default=""),
        sa.Column("reason", sa.String(100), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("intent", sa.String(64)),
        sa.Column("confidence", sa.Float),
        sa.Column("booking_ref", sa.String(64)),
        sa.Column("hitl_item_id", sa.String(36)),
        sa.Column("result", JSON),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_cases_external_id", "cases", ["external_id"])
    op.create_index("ix_cases_reason", "cases", ["reason"])
    op.create_index("ix_cases_status", "cases", ["status"])

    op.create_table(
        "hitl_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("customer_id", sa.String(128)),
        sa.Column("reviewer", sa.String(128)),
        sa.Column("reviewer_note", sa.Text),
        sa.Column("result", JSON),
        sa.Column("workflow_id", sa.String(128)),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("reviewed_at", TS),
    )
    op.create_index("ix_hitl_items_source_ref", "hitl_items", ["source_ref"])
    op.create_index("ix_hitl_items_status", "hitl_items", ["status"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("surface", sa.String(16), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION audit_events_immutable() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            "CREATE TRIGGER audit_events_no_update_delete BEFORE UPDATE OR DELETE ON audit_events "
            "FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_update_delete ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS audit_events_immutable()")
    op.drop_table("audit_events")
    op.drop_table("hitl_items")
    op.drop_table("cases")
