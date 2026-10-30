"""Create the SharePoint inventory import table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "4f2c8a9d1b73"
down_revision = "8c6ae5c02b69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("tspc_it_inventory"):
        return

    op.create_table(
        "tspc_it_inventory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sharepoint_item_id", sa.String(length=100), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_modified_at", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sharepoint_item_id"),
    )
    op.create_index(
        "ix_tspc_it_inventory_sharepoint_item_id",
        "tspc_it_inventory",
        ["sharepoint_item_id"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("tspc_it_inventory"):
        return
    index_names = {index["name"] for index in inspector.get_indexes("tspc_it_inventory")}
    if "ix_tspc_it_inventory_sharepoint_item_id" in index_names:
        op.drop_index("ix_tspc_it_inventory_sharepoint_item_id", table_name="tspc_it_inventory")
    op.drop_table("tspc_it_inventory")