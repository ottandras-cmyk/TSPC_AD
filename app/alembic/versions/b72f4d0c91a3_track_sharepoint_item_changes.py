"""Track SharePoint item revisions and removals."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b72f4d0c91a3"
down_revision = "a6d9c2e41b70"
branch_labels = None
depends_on = None


SHAREPOINT_TABLES = (
    "SP_eszkozleltar_nonIT",
    "SP_O365LicenceInfo",
    "SP_Atadas_atvetel",
    "SP_IT_Inventory",
)


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    for table_name in SHAREPOINT_TABLES:
        if "is_deleted" not in _column_names(table_name):
            op.add_column(
                table_name,
                sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
            )

    history_columns = _column_names("sharepoint_sync_history")
    for column_name in ("added_count", "updated_count", "deleted_count"):
        if column_name not in history_columns:
            op.add_column(
                "sharepoint_sync_history",
                sa.Column(column_name, sa.Integer(), server_default="0", nullable=False),
            )

    if not sa.inspect(op.get_bind()).has_table("sharepoint_item_changes"):
        op.create_table(
            "sharepoint_item_changes",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("list_name", sa.String(length=255), nullable=False),
            sa.Column("sharepoint_item_id", sa.String(length=100), nullable=False),
            sa.Column("change_type", sa.String(length=20), nullable=False),
            sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("previous_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("current_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("trigger_type", sa.String(length=50), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sharepoint_item_changes_list_name", "sharepoint_item_changes", ["list_name"])
        op.create_index(
            "ix_sharepoint_item_changes_sharepoint_item_id",
            "sharepoint_item_changes",
            ["sharepoint_item_id"],
        )
        op.create_index("ix_sharepoint_item_changes_changed_at", "sharepoint_item_changes", ["changed_at"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("sharepoint_item_changes"):
        op.drop_index("ix_sharepoint_item_changes_changed_at", table_name="sharepoint_item_changes")
        op.drop_index(
            "ix_sharepoint_item_changes_sharepoint_item_id",
            table_name="sharepoint_item_changes",
        )
        op.drop_index("ix_sharepoint_item_changes_list_name", table_name="sharepoint_item_changes")
        op.drop_table("sharepoint_item_changes")

    history_columns = _column_names("sharepoint_sync_history")
    for column_name in ("deleted_count", "updated_count", "added_count"):
        if column_name in history_columns:
            op.drop_column("sharepoint_sync_history", column_name)

    for table_name in SHAREPOINT_TABLES:
        if "is_deleted" in _column_names(table_name):
            op.drop_column(table_name, "is_deleted")
