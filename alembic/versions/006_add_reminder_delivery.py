"""Add reminder approval, scheduling, delivery state, and user email addresses."""

import sqlalchemy as sa

from alembic import op

revision = "006_add_reminder_delivery"
down_revision = "005_add_compliance_calendar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    user_columns = {
        column["name"] for column in sa.inspect(connection).get_columns("user")
    }
    if "email" not in user_columns:
        with op.batch_alter_table("user") as batch_op:
            batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
            batch_op.create_index("ix_user_email", ["email"], unique=False)

    draft_columns = {
        column["name"] for column in sa.inspect(connection).get_columns("reminderdraft")
    }
    additions = {
        "approved_by": sa.Column("approved_by", sa.Integer(), nullable=True),
        "approved_at": sa.Column("approved_at", sa.DateTime(), nullable=True),
        "scheduled_for": sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        "sent_at": sa.Column("sent_at", sa.DateTime(), nullable=True),
        "delivery_attempts": sa.Column(
            "delivery_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        "last_error": sa.Column("last_error", sa.String(), nullable=True),
    }
    missing = [name for name in additions if name not in draft_columns]
    if missing:
        with op.batch_alter_table("reminderdraft") as batch_op:
            for name in missing:
                batch_op.add_column(additions[name])
            if "approved_by" in missing:
                batch_op.create_foreign_key(
                    "fk_reminderdraft_approved_by", "user", ["approved_by"], ["id"]
                )


def downgrade() -> None:
    with op.batch_alter_table("reminderdraft") as batch_op:
        batch_op.drop_constraint("fk_reminderdraft_approved_by", type_="foreignkey")
        for column in (
            "last_error",
            "delivery_attempts",
            "sent_at",
            "scheduled_for",
            "approved_at",
            "approved_by",
        ):
            batch_op.drop_column(column)
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_email")
        batch_op.drop_column("email")
