"""Persist normalized bank transactions for reconciliation."""

import sqlalchemy as sa

from alembic import op

revision = "003_add_bank_transaction_records"
down_revision = "002_add_classification_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "banktransactionrecord" in inspector.get_table_names():
        return

    op.create_table(
        "banktransactionrecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("debit", sa.Float(), nullable=True),
        sa.Column("credit", sa.Float(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=True),
        sa.Column(
            "reconciliation_status",
            sa.String(),
            nullable=False,
            server_default="UNMATCHED",
        ),
        sa.Column("matched_document_id", sa.Integer(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("match_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documentrecord.id"]),
        sa.ForeignKeyConstraint(["matched_document_id"], ["documentrecord.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "source_row"),
    )
    op.create_index(
        "ix_banktransactionrecord_tenant_id",
        "banktransactionrecord",
        ["tenant_id"],
    )
    op.create_index(
        "ix_banktransactionrecord_document_id",
        "banktransactionrecord",
        ["document_id"],
    )
    op.create_index(
        "ix_banktransactionrecord_source_row",
        "banktransactionrecord",
        ["source_row"],
    )
    op.create_index(
        "ix_banktransactionrecord_matched_document_id",
        "banktransactionrecord",
        ["matched_document_id"],
    )


def downgrade() -> None:
    op.drop_table("banktransactionrecord")
