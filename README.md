# DocuSync AI 📄🤖

**DocuSync AI** is an enterprise-grade, multi-document extraction, classification, verification, and payment reconciliation platform built for Chartered Accountants (CAs), tax consultants, and financial advisory practices[cite: 14].

For the complete operator, user, integration, troubleshooting, and development guide, see [USER_MANUAL.md](USER_MANUAL.md).

Contributors should follow [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) and the pull request checklist in `.github/pull_request_template.md` for every implementation.

It automates file ingestion, document type classification, OCR fallback processing, structured JSON extraction, deterministic verification auditing, and payment status tracking for financial documents (Tax Invoices, Bank Statements)—flagging compliance discrepancies before accounting exports or tax filings[cite: 14].

---

## 🌟 Key Features & Hardening

* **Multi-Document Auto-Routing:** Automatically classifies incoming uploads into supported document schemas (`TAX_INVOICE`, `BANK_STATEMENT`)[cite: 14].
* **Confidence-Aware Categorization:** Rules classify invoices and bank statements, retain keyword reasoning, and route unknown or low-confidence files to `NEEDS_REVIEW`; UTF-8 CSV bank statements are accepted alongside PDF and image files.
* **Categorization Review Queue:** CA administrators can inspect classification confidence/reasoning and rerun classification without allowing clients to mutate document categorization.
* **Hybrid OCR & Vision Engine:** Extracts digital PDF text via `pdfplumber` with automatic fallback to **Tesseract OCR** and `pypdfium2`-based Gemini/Groq vision parsing[cite: 13, 14].
* **Deterministic Rule-Based Auditor:** Evaluates extracted metadata against Indian GSTIN regex rules, line-item mathematical sums, and tax balance logic to assign severity flags (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`)[cite: 13, 14].
* **Payment Reconciliation:** Tracks `payment_status` (`UNPAID`, `PARTIAL`, `PAID`) and `amount_paid` directly within the schema and user portal[cite: 10, 14].
* **Multi-Tenant Database Persistence & RBAC:** Saves files, structured JSON, and audit summaries into SQLite via **SQLModel**, enforcing Role-Based Access Control (RBAC) separating `CA_ADMIN` and `CLIENT` access[cite: 10, 14].
* **Thread-Safe Background Workers:** Decoupled asynchronous background tasks allow tests and execution workers to run cleanly over bound session engines without DB context mismatches.
* **Security Hardened File Uploads & Exports:** 
  * **Magic Byte Signature Check:** Validates raw headers (`b"%PDF"`, `b"\x89PNG"`, `b"\xff\xd8\xff"`) to block executable payloads disguised as PDFs[cite: 14].
  * **Path Traversal Protection:** Strips directory traversal sequences (`../../`) using model-level field validators[cite: 10, 14].
  * **CSV Injection Escaping:** Escapes formula prefixes (`=`, `+`, `-`, `@`) before generating Zoho Books CSV outputs[cite: 14].
* **Accounting System Exporters:** Native export modules generate Zoho Books CSVs and Tally XML vouchers ready for direct accounting software imports[cite: 13, 14].
* **External Document Intake:** A provider-neutral connector contract supports Google Drive, Dropbox, and Gmail adapters; Google Drive is implemented with tenant-bound, source-ID and content-hash deduplication.
* **Cloud File Storage:** Supabase Storage is supported with local-disk fallback and tenant-authorized signed file URLs through the document API.
* **Model Context Protocol (MCP) Server:** Native `FastMCP` tools enabling AI assistants (like Claude Desktop or Cursor) to query client document statuses and metrics using natural language[cite: 14].

---

## 🏗️ Architecture & Stack

* **Language Runtime:** Python 3.12 (managed via `uv`)[cite: 10, 14]
* **Web Framework:** FastAPI (REST API) & Streamlit (UI Dashboard)[cite: 14]
* **LLM Engine & Schemas:** Groq API / Google Gemini API with `instructor` for strict Pydantic JSON schema generation[cite: 14]
* **Document Processing:** `pdfplumber` (native PDFs), `pypdfium2` (rendering), & `pytesseract` / `poppler-utils` (scanned PDFs)[cite: 13, 14]
* **Database ORM:** SQLModel (SQLite)[cite: 10, 14]
* **External APIs:** Google Drive API with read-only service-account or access-token credentials
* **Object Storage:** Supabase Storage (optional) with local `storage/uploads/` fallback
* **Testing & Quality Gates:** Pytest & GitHub Actions CI[cite: 10, 14]

---

## 📁 Project Structure

```text
docusync-ai/
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI workflow with uv & Pytest
├── app/
│   ├── api/                         # REST API routes
│   │   ├── v1/                      # Extraction engine endpoints
│   │   │   ├── extraction.py        # Process & auto-classify router
│   │   │   └── router.py            # API v1 router aggregator
│   │   └── documents.py             # Document upload, RBAC, background worker & export routes
│   ├── core/                        # Core infrastructure & engines
│   │   ├── database.py              # SQLModel schemas (User, DocumentRecord) & engine init
│   │   ├── groq_client.py           # Structured LLM extractor wrapper (Groq & Gemini)
│   │   ├── ocr_engine.py            # Tesseract & pdfplumber extraction engine
│   │   └── security.py              # Magic byte file validation & security rules
│   ├── schemas/                     # Pydantic JSON schemas
│   │   ├── bank_statement.py        # Bank transaction schema
│   │   ├── base.py                  # Base schema definitions
│   │   ├── document.py              # Generic request/response schemas
│   │   ├── document_type.py         # Document type enum definitions
│   │   ├── tax_invoice.py           # GST Invoice schema
│   │   └── verification.py          # Audit verification flag schema
│   ├── services/                    # Business logic & export services
│   │   ├── audit_engine.py          # Process audit flags & updates
│   │   ├── connector_ingestion.py   # Tenant mapping, download, and deduplication
│   │   ├── extractor_service.py     # High-level OCR + LLM parsing orchestrator
│   │   ├── gstin_validator.py       # GSTIN checksum & regex validator
│   │   ├── parser.py                # Text parsing utility helpers
│   │   ├── tally_exporter.py        # Tally XML voucher exporter
│   │   ├── verification_service.py  # Rule-based validation logic
│   │   └── zoho_exporter.py         # CSV injection-safe Zoho exporter
│   ├── connectors/                   # Provider-neutral intake & Google Drive adapter
│   ├── config.py                    # Pydantic environment configuration (graceful CI fallbacks)
│   ├── dashboard.py                 # Streamlit CA & Client Web Portal
│   └── main.py                      # FastAPI application entrypoint
├── storage/                         # Local SQLite DB and upload storage directory
├── tests/                           # Automated test suite
│   ├── test_api_endpoints.py        # API, upload security, and RBAC tests
│   ├── test_audit_engine.py         # Audit verification rule tests
│   ├── test_auth_and_exports.py     # Exporter and auth helper tests
│   ├── test_client_portal.py        # Multi-tenant view tests
│   ├── test_extractor_service.py    # Multi-modal extraction and fallback unit tests
│   ├── test_reconciliation.py       # Payment reconciliation tests
│   ├── test_connectors.py            # Google Drive auth, ingestion, and deduplication
│   └── test_security_hardening.py   # Security, path traversal & payload resilience tests
├── conftest.py                      # Global Pytest fixtures & isolated in-memory DB configuration
├── generate_test_pdf.py             # Helper utility generating sample synthetic PDFs
├── mcp_server.py                    # Model Context Protocol server entrypoint
├── pyproject.toml                   # Project configuration & dependencies
├── seed_test_data.py                # CLI script to populate database with demo users & documents
└── README.md

```

---

## 🚀 Quickstart & Installation

### 1. System Prerequisites (Ubuntu / WSL2)

Install system dependencies required for PDF rendering and OCR extraction:

```bash
sudo apt update && sudo apt install -y poppler-utils tesseract-ocr

```

### 2. Environment Setup

Sync virtual environment and dependencies using `uv`:

```bash
uv sync

```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
APP_NAME="DocuSync AI"
DEBUG=True
GROQ_API_KEY="your_actual_groq_api_key_here"
GEMINI_API_KEY="your_actual_gemini_api_key_here"
SECRET_KEY="your_custom_secure_jwt_secret_key"
PRIMARY_EXTRACTION_MODEL="llama-3.3-70b-versatile"
VISION_EXTRACTION_MODEL="gemini-2.5-flash"
DATABASE_URL="sqlite:///storage/docusync.db"
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your_supabase_key"
SUPABASE_STORAGE_BUCKET="docusync-uploads"
# Local mock connector settings; keep real OAuth tokens out of .env.
# MOCK_CONNECTORS_ENABLED=false
# MOCK_CONNECTOR_ACCOUNT_ID=mock-account
# DROPBOX_ACCESS_TOKEN=
# GMAIL_ACCESS_TOKEN=
# CONNECTOR_TOKEN_STORE=supabase_vault

```

---

## 🧪 Running Tests & Quality Gates

Run the automated test suite locally:

```bash
uv run --extra dev pytest -v

```

### Test Coverage Highlights:

* **Upload Security & Magic Bytes:** Rejects disguised executable payloads by checking file byte signatures.
* **Path Traversal Shielding:** Strips relative path markers (`../`) from uploaded filenames.
* **Multi-Tenant Isolation (RBAC):** Restricts client access to authorized client IDs while allowing broad CA admin oversight.
* **Payment Reconciliation:** Verifies accuracy of amount updates and status changes (`UNPAID`, `PARTIAL`, `PAID`).
* **Export Escaping:** Prevents CSV formula injection attacks (`=`, `+`, `-`, `@`) in exported financial streams.
* **Extractor & Vision Pipelines:** Verifies fallback handling, structured schema conversions, and multi-modal array inputs.
* **Connector Intake:** Verifies Google Drive authentication construction, tenant-safe bindings, source/content deduplication, imported file ownership, and Dropbox/Gmail mock adapters.
* **Supabase Signed URLs:** Verifies cloud signed URL generation and local fallback behavior.

---

## 📖 Usage Options

### Option 1: FastAPI REST API

Start the backend server:

```bash
uv run uvicorn app.main:app --reload

```

Access Swagger API docs at **`http://127.0.0.1:8000/docs`**.

---

### Option 2: Streamlit Web Dashboard

Launch the web application:

```bash
uv run streamlit run app/dashboard.py

```

Navigate to **`http://localhost:8501`**.

---

### Option 3: Model Context Protocol (MCP) Server

Connect your backend database to AI clients (like Claude Desktop or Cursor):

```bash
uv run python mcp_server.py

```

### Option 4: External Connector Ingestion

Connector ingestion is credential-injected so access tokens and service-account keys stay outside the database. Bind an external account to a tenant, construct a `GoogleDriveConnector`, and call `ingest_connector_files(...)`. The service stores files through `StorageService`, creates tenant-owned `DocumentRecord` entries, and skips duplicate source IDs or content hashes.

Dropbox and Gmail use the same `DocumentConnector` protocol but do not yet have provider adapters.

External connector intake and scheduled sync are optional and disabled by default. Enable `CONNECTOR_SYNC_ENABLED` only after registering authenticated connector clients in the Celery worker process.

---

## 📋 Project Roadmap

* [x] **Phase 1:** Core FastAPI setup, Pydantic schemas, and LLM extraction engine.
* [x] **Phase 2:** OCR Fallback Pipeline (Tesseract) & Auto-Classification Router.
* [x] **Phase 3:** Vision Extraction & Structured Output Pipeline (`extractor_service.py`, `pypdfium2`, Gemini fallback).


* [x] **Phase 4:** Deterministic Rule Audit Engine & Anomaly Inspector.


* [x] **Phase 5:** SQLModel Database Persistence, FastMCP accounting tools, guarded mutations, and MCP-routed RAG.


* [x] **Phase 6:** Payment Reconciliation Tracking (`payment_status`, `amount_paid`, `due_date`).


* [x] **Phase 7:** API Security Hardening (Magic Bytes, Path Traversal, CSV Escaping, Pytest & GitHub Actions CI).


* [x] **Phase 8:** Async Queue Workers (Celery/Redis) & Production Docker Packaging.
* [x] **Phase 9:** Supabase storage mode, signed URLs, and Google Drive intake foundation.
* [ ] **Phase 10:** Dropbox and Gmail provider adapters.
