"""Track reconciliation approvals and applied payment amounts."""

import sqlalchemy as sa

from alembic import op

revision = "004_add_reconciliation_approval"
down_revision = "003_add_bank_transaction_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("banktransactionrecord")
    }
    if "approved_by" not in columns:
        with op.batch_alter_table("banktransactionrecord") as batch_op:
            batch_op.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_banktransactionrecord_approved_by",
                "user",
                ["approved_by"],
                ["id"],
            )
    if "approved_at" not in columns:
        with op.batch_alter_table("banktransactionrecord") as batch_op:
            batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
    if "applied_amount" not in columns:
        with op.batch_alter_table("banktransactionrecord") as batch_op:
            batch_op.add_column(sa.Column("applied_amount", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("banktransactionrecord") as batch_op:
        batch_op.drop_column("applied_amount")
        batch_op.drop_column("approved_at")
        batch_op.drop_constraint(
            "fk_banktransactionrecord_approved_by", type_="foreignkey"
        )
        batch_op.drop_column("approved_by")
