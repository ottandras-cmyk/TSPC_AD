"""Track nested Active Directory group memberships."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e4a91d62c830"
down_revision = "d0a6b8143c27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ad_group_group_members"):
        return

    op.create_table(
        "ad_group_group_members",
        sa.Column("parent_group_guid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_group_guid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_group_guid"],
            ["ad_groups.object_guid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_group_guid"],
            ["ad_groups.object_guid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "parent_group_guid",
            "member_group_guid",
            name="pk_ad_group_group_members",
        ),
        sa.CheckConstraint(
            "parent_group_guid <> member_group_guid",
            name="ck_ad_group_group_members_not_self",
        ),
    )
    op.create_index(
        "ix_ad_group_group_members_member_group_guid",
        "ad_group_group_members",
        ["member_group_guid"],
    )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ad_group_group_members"):
        op.drop_index(
            "ix_ad_group_group_members_member_group_guid",
            table_name="ad_group_group_members",
        )
        op.drop_table("ad_group_group_members")
