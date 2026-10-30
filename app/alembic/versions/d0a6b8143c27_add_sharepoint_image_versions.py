"""Store downloaded SharePoint equipment images and revision history."""

from alembic import op
import sqlalchemy as sa


revision = "d0a6b8143c27"
down_revision = "b72f4d0c91a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sharepoint_image_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sharepoint_item_id", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_url_sha256", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sharepoint_item_id",
            "source_url_sha256",
            "version_number",
            name="uq_sharepoint_image_version",
        ),
    )
    op.create_index(
        "ix_sharepoint_image_versions_sharepoint_item_id",
        "sharepoint_image_versions",
        ["sharepoint_item_id"],
    )
    op.create_table(
        "sharepoint_image_sync_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("links_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_versions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sharepoint_image_sync_history_started_at",
        "sharepoint_image_sync_history",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sharepoint_image_sync_history_started_at",
        table_name="sharepoint_image_sync_history",
    )
    op.drop_table("sharepoint_image_sync_history")
    op.drop_index(
        "ix_sharepoint_image_versions_sharepoint_item_id",
        table_name="sharepoint_image_versions",
    )
    op.drop_table("sharepoint_image_versions")
