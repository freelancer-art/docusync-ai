"""Add tenant connector bindings and imported-file deduplication tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "001_add_connector_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table("user"):
        op.create_table(
            "user",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
        op.create_index("ix_user_username", "user", ["username"], unique=False)

    if not inspector.has_table("documentrecord"):
        op.create_table(
            "documentrecord",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("document_type", sa.String(), nullable=False),
            sa.Column("extraction_method", sa.String(), nullable=False),
            sa.Column("overall_status", sa.String(), nullable=False),
            sa.Column("classification_confidence", sa.Float(), nullable=True),
            sa.Column("classification_reasoning", sa.String(), nullable=True),
            sa.Column("vendor_name", sa.String(), nullable=True),
            sa.Column("invoice_number", sa.String(), nullable=True),
            sa.Column("total_amount", sa.Float(), nullable=True),
            sa.Column("amount_paid", sa.Float(), nullable=True),
            sa.Column("payment_status", sa.String(), nullable=False),
            sa.Column("audit_flags_json", sa.String(), nullable=True),
            sa.Column("raw_json_data", sa.String(), nullable=True),
            sa.Column("auditor_notes", sa.String(), nullable=True),
            sa.Column("client_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["client_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_documentrecord_client_id", "documentrecord", ["client_id"])

    op.create_table(
        "connectorbinding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_account_id", sa.String(), nullable=False),
        sa.Column("credential_ref", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_account_id", name="uq_connector_binding_account"
        ),
    )
    op.create_index("ix_connectorbinding_tenant_id", "connectorbinding", ["tenant_id"])
    op.create_index("ix_connectorbinding_provider", "connectorbinding", ["provider"])

    op.create_table(
        "importedfile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("source_file_id", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documentrecord.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "source_file_id", name="uq_imported_source_file"
        ),
        sa.UniqueConstraint(
            "tenant_id", "provider", "content_hash", name="uq_imported_content_hash"
        ),
    )
    op.create_index("ix_importedfile_tenant_id", "importedfile", ["tenant_id"])
    op.create_index("ix_importedfile_provider", "importedfile", ["provider"])
    op.create_index("ix_importedfile_content_hash", "importedfile", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_importedfile_content_hash", table_name="importedfile")
    op.drop_index("ix_importedfile_provider", table_name="importedfile")
    op.drop_index("ix_importedfile_tenant_id", table_name="importedfile")
    op.drop_table("importedfile")
    op.drop_index("ix_connectorbinding_provider", table_name="connectorbinding")
    op.drop_index("ix_connectorbinding_tenant_id", table_name="connectorbinding")
    op.drop_table("connectorbinding")
