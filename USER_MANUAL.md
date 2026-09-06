# DocuSync AI User Manual

DocuSync AI is a multi-tenant document processing and audit platform for CA firms. It accepts invoices and bank statements, extracts structured accounting data, applies deterministic and AI-assisted checks, tracks payments, and produces accounting exports.

## 1. Operating Model

DocuSync has two application surfaces:

- **FastAPI:** authenticated REST API for integrations, uploads, documents, payments, exports, and health checks.
- **Streamlit dashboard:** browser workflow for CA administrators and client users.

The application supports two roles:

- **CA_ADMIN:** manages users, views all tenant records, reviews audits, edits document decisions, reconciles payments, and exports accounting data.
- **CLIENT:** views and manages only records assigned to that client account.

A document belongs to a tenant through `DocumentRecord.client_id`. Connector imports must also have an enabled `ConnectorBinding` for that tenant.

## 2. Installation

### System packages

On Ubuntu or WSL2:

```bash
sudo apt update
sudo apt install -y poppler-utils tesseract-ocr
```

### Python environment

This repository uses `uv`:

```bash
uv sync
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
```

The project targets Python 3.10 or newer. Python 3.12 is the development baseline.

## 3. Configuration

Create a local `.env` file. Never commit it or place production secrets in it.

Required production settings:

```env
DEBUG=false
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///storage/docusync.db
REDIS_URL=redis://localhost:6379/0
```

AI extraction is optional but requires at least one provider key:

```env
GROQ_API_KEY=your-groq-key
GEMINI_API_KEY=your-gemini-key
PRIMARY_EXTRACTION_MODEL=llama-3.3-70b-versatile
VISION_EXTRACTION_MODEL=gemini-2.5-flash
```

Optional Supabase Storage settings:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
SUPABASE_STORAGE_BUCKET=docusync-uploads
```

If Supabase settings are absent or unavailable, files use local storage under `storage/uploads/`.

Connector development placeholders are documented in `.env` as comments. OAuth tokens and service-account JSON must be stored in a secret manager, not in source control.

## 4. Start the Application

### API

```bash
uv run uvicorn app.main:app --reload
```

API documentation is available at `http://127.0.0.1:8000/docs`.

### Dashboard

```bash
uv run streamlit run app/dashboard.py
```

Open `http://127.0.0.1:8501`.

### Worker

For asynchronous processing, start Redis and the Celery worker:

```bash
uv run celery -A app.core.celery_app.celery_app worker --loglevel=INFO
```

The repository also provides `start.sh` for the deployment process, which starts the worker and foreground web process using the configured port.

## 5. First-Time Setup

1. Start the API and dashboard.
2. In development, the default CA account is available only when `DEBUG=true` and no initial account is configured. Change it immediately.
3. In production, set `INITIAL_CA_USERNAME`, `INITIAL_CA_PASSWORD`, and `INITIAL_CA_FULL_NAME` before first startup, or create the first CA account through the protected deployment process.
4. Sign in as a CA administrator.
5. Create client accounts.
6. Upload documents or configure a connector binding.
7. Review extraction results and audit flags before exporting.

## 6. Dashboard Workflows

### Upload and process a document

1. Sign in.
2. Open the upload workflow.
3. Select a PDF, PNG, or JPEG file.
4. Submit the upload.
5. Wait for extraction and audit processing.
6. Open the document in the ledger to inspect vendor, invoice number, totals, GST fields, payment status, and audit flags.

Uploads are checked by file signature, not just filename extension. Path traversal names are sanitized before storage.

### Review audit results

A document can be `VERIFIED`, `NEEDS_REVIEW`, `REJECTED`, or `FAILED` during processing. CA administrators can edit supported fields, add auditor notes, and override the final status. Review critical flags before export.

### Record payments

Use the payment workflow to enter a positive payment amount. The system calculates the outstanding amount and assigns `UNPAID`, `PARTIAL`, or `PAID`. Duplicate invoice and overpayment rules are validated by the API.

### Export accounting data

Only CA administrators can export verified records:

- Zoho Books CSV: `/api/documents/export/zoho`
- Tally XML: `/api/documents/export/tally`

CSV formula prefixes are escaped before output.

## 7. REST API Quick Reference

Authentication uses a bearer token returned by:

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=<username>&password=<password>
```

Important endpoints:

| Endpoint | Purpose | Access |
| --- | --- | --- |
| `GET /healthz` | Liveness | Public |
| `GET /ready` | Database and Redis readiness | Public |
| `POST /api/auth/login` | Obtain an access token | Public |
| `GET /api/documents/` | List tenant-scoped documents | Authenticated |
| `GET /api/documents/{id}` | Read one document | Owner or CA admin |
| `GET /api/documents/{id}/file-url` | Get signed or local file URL | Owner or CA admin |
| `PATCH /api/documents/{id}` | Update audit fields | CA admin |
| `POST /api/v1/upload` | Upload and queue a document | Authenticated |
| `POST /api/payments/{id}` | Record a payment | Authorized user |
| `GET /api/documents/export/zoho` | Download Zoho CSV | CA admin |
| `GET /api/documents/export/tally` | Download Tally XML | CA admin |

Use the generated OpenAPI page at `/docs` for exact request and response schemas.

## 8. Google Drive Intake

Google Drive is the supported real external connector. Dropbox and Gmail currently have deterministic mock adapters only.

### Service-account approach

1. Create or select a Google Cloud project.
2. Enable the Google Drive API.
3. Create a service account.
4. Grant the service account read access to the source Drive folder.
5. Store the service-account JSON in a secret manager.
6. Construct `GoogleDriveConnector.from_service_account_info(...)` in the integration layer.
7. Create an enabled `ConnectorBinding` for the tenant and Google account ID.
8. Call `ingest_connector_files(...)` for a manual sync.

### Access-token approach

Use `GoogleDriveConnector.from_access_token(...)` when an OAuth flow has produced a short-lived or refresh-managed token. The token lifecycle and secure persistence belong in the integration layer; do not put tokens in `ConnectorBinding` plaintext fields.

### Import guarantees

Connector ingestion:

- refuses an unbound or disabled tenant/provider/account combination;
- validates PDF, PNG, and JPEG magic bytes;
- sanitizes the source filename;
- stores the file through local or Supabase storage;
- creates a tenant-owned `DocumentRecord`;
- skips duplicate provider source IDs; and
- skips duplicate SHA-256 content within the same tenant and provider.

## 9. Storage and File URLs

Local mode writes to `UPLOAD_DIR`, normally `storage/uploads/`. Supabase mode writes to the configured bucket. The API file URL endpoint returns:

- a bounded, time-limited signed URL when Supabase is active; or
- the configured local storage prefix when using local fallback.

Signed URL expiry is constrained to 60 seconds through 24 hours. Access is checked against the document tenant before a URL is returned.

## 10. MCP Accounting Tools

Start the MCP server with:

```bash
uv run python app/mcp_server.py
```

Available tool categories include document lookup, GSTIN validation, safe document search, audit explanations, duplicate detection, tax summaries, accounting export previews, financial summaries, and validated tenant-scoped ledger queries.

Mutation tools require an explicit, short-lived, single-use confirmation token. Every tool invocation is recorded with actor, tool name, redacted arguments, outcome, and timestamp.

## 11. Debugging and Observability

Set the log level with:

```env
LOG_LEVEL=DEBUG
```

API logs are JSON and include an `X-Request-ID` correlation ID. Send an existing request ID in that header to trace a request across middleware and logs.

Useful checks:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/ready
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
```

A `503` from `/ready` means the API process is alive but either the database or Redis dependency is unavailable.

## 12. Security Rules

- Use `DEBUG=false` in production.
- Set a strong `SECRET_KEY`.
- Do not use the debug default administrator in production.
- Do not commit `.env`, OAuth tokens, service-account JSON, or Supabase service-role keys.
- Keep connector bindings tenant-specific.
- Use CA-admin privileges only for review, account management, mutations, and exports.
- Treat AI extraction as advisory and review flagged documents before filing or export.
- Keep uploaded file validation enabled; never bypass magic-byte checks.

## 13. Development Workflow

Before opening a change:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
uv run --extra dev ruff format --check app tests
 git diff --check
```

Add or update focused tests for behavior changes. Prefer dependency injection for provider clients and storage clients so tests never require live cloud credentials. Keep public APIs and tenant boundaries explicit, and update `README.md`, `FILES_USAGE.md`, `PROJECT_PLAN.MD`, and this manual when workflows change.

## 14. Known Deferred Work

- Production Dropbox and Gmail provider adapters.
- OAuth callback and refresh-token lifecycle management for Google Drive.
- Secret-manager integration for connector credentials.
- Central metrics, tracing export, and alerting.
- Incremental docstring coverage for older internal helpers.
