"""Store explainable document classification metadata."""

import sqlalchemy as sa

from alembic import op

revision = "002_add_classification_metadata"
down_revision = "001_add_connector_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("documentrecord")
    }
    if "classification_confidence" not in columns:
        op.add_column(
            "documentrecord",
            sa.Column("classification_confidence", sa.Float(), nullable=True),
        )
    if "classification_reasoning" not in columns:
        op.add_column(
            "documentrecord",
            sa.Column("classification_reasoning", sa.String(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("documentrecord", "classification_reasoning")
    op.drop_column("documentrecord", "classification_confidence")
