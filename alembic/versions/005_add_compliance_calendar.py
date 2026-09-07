"""Add tenant compliance deadlines and reminder drafts."""

import sqlalchemy as sa

from alembic import op

revision = "005_add_compliance_calendar"
down_revision = "004_add_reconciliation_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "compliancedeadline" not in tables:
        op.create_table(
            "compliancedeadline",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("form_type", sa.String(), nullable=True),
            sa.Column("period", sa.String(), nullable=False),
            sa.Column("due_date", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "title", "period"),
        )
        op.create_index(
            "ix_compliancedeadline_tenant_id",
            "compliancedeadline",
            ["tenant_id"],
        )
    if "reminderdraft" not in tables:
        op.create_table(
            "reminderdraft",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("deadline_id", sa.Integer(), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False),
            sa.Column("subject", sa.String(), nullable=False),
            sa.Column("body", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["deadline_id"], ["compliancedeadline.id"]),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_reminderdraft_tenant_id", "reminderdraft", ["tenant_id"])
        op.create_index(
            "ix_reminderdraft_deadline_id", "reminderdraft", ["deadline_id"]
        )
