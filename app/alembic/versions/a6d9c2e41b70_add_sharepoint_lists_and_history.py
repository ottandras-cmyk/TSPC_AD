"""Add local SharePoint list copies and synchronization history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a6d9c2e41b70"
down_revision = "4f2c8a9d1b73"
branch_labels = None
depends_on = None


SHAREPOINT_TABLES = (
    "SP_eszkozleltar_nonIT",
    "SP_O365LicenceInfo",
    "SP_Atadas_atvetel",
    "SP_IT_Inventory",
)


def _create_sharepoint_copy(table_name: str) -> None:
    if sa.inspect(op.get_bind()).has_table(table_name):
        return
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sharepoint_item_id", sa.String(length=100), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_modified_at", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sharepoint_item_id"),
    )
    op.create_index(
        f"ix_{table_name}_sharepoint_item_id",
        table_name,
        ["sharepoint_item_id"],
    )


def upgrade() -> None:
    for table_name in SHAREPOINT_TABLES:
        _create_sharepoint_copy(table_name)

    if not sa.inspect(op.get_bind()).has_table("sharepoint_sync_history"):
        op.create_table(
            "sharepoint_sync_history",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("list_name", sa.String(length=255), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Float(), nullable=True),
            sa.Column("trigger_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("items_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sharepoint_sync_history_list_name", "sharepoint_sync_history", ["list_name"])
        op.create_index("ix_sharepoint_sync_history_started_at", "sharepoint_sync_history", ["started_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("sharepoint_sync_history"):
        op.drop_index("ix_sharepoint_sync_history_started_at", table_name="sharepoint_sync_history")
        op.drop_index("ix_sharepoint_sync_history_list_name", table_name="sharepoint_sync_history")
        op.drop_table("sharepoint_sync_history")

    for table_name in reversed(SHAREPOINT_TABLES):
        if inspector.has_table(table_name):
            op.drop_index(f"ix_{table_name}_sharepoint_item_id", table_name=table_name)
            op.drop_table(table_name)
