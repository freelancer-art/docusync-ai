Here are the updated `README.md` and `FILE_USAGE.md` files reflecting the updated security hardening, payment reconciliation features, background worker test isolation fixes, environment config resiliency, and CI pipeline setup.

---

### `README.md`

```markdown
# DocuSync AI 📄🤖

**DocuSync AI** is an enterprise-grade, multi-document extraction, classification, verification, and payment reconciliation platform built for Chartered Accountants (CAs), tax consultants, and financial advisory practices[cite: 14].

It automates file ingestion, document type classification, OCR fallback processing, structured JSON extraction, deterministic verification auditing, and payment status tracking for financial documents (Tax Invoices, Bank Statements)—flagging compliance discrepancies before accounting exports or tax filings[cite: 14].

---

## 🌟 Key Features & Hardening

* **Multi-Document Auto-Routing:** Automatically classifies incoming uploads into supported document schemas (`TAX_INVOICE`, `BANK_STATEMENT`)[cite: 14].
* **Hybrid OCR Fallback Engine:** Extracts digital PDF text via `pdfplumber` with automatic fallback to **Tesseract OCR** for scanned images and low-quality PDFs[cite: 14].
* **Deterministic Rule-Based Auditor:** Evaluates extracted metadata against Indian GSTIN regex rules, line-item mathematical sums, and tax balance logic to assign severity flags (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`)[cite: 14].
* **Payment Reconciliation:** Tracks `payment_status` (`UNPAID`, `PARTIAL`, `PAID`), `amount_paid`, and `due_date` directly within the schema and user portal[cite: 10, 14].
* **Multi-Tenant Database Persistence & RBAC:** Saves files, structured JSON, and audit summaries into SQLite via **SQLModel**, enforcing Role-Based Access Control (RBAC) separating `CA_ADMIN` and `CLIENT` access[cite: 10, 14].
* **Thread-Safe Background Workers:** Decoupled asynchronous background tasks allow tests and execution workers to run cleanly over bound session engines without DB context mismatches.
* **Security Hardened File Uploads & Exports:** 
  * **Magic Byte Signature Check:** Validates raw headers (`b"%PDF"`, `b"\x89PNG"`, `b"\xff\xd8\xff"`) to block executable payloads disguised as PDFs[cite: 14].
  * **Path Traversal Protection:** Strips directory traversal sequences (`../../`) using model-level field validators[cite: 10, 14].
  * **CSV Injection Escaping:** Escapes formula prefixes (`=`, `+`, `-`, `@`) before generating Zoho Books CSV outputs[cite: 14].
* **Accounting System Exporters:** Native export modules generate Zoho Books CSVs and Tally XML vouchers ready for direct accounting software imports[cite: 14].
* **Model Context Protocol (MCP) Server:** Native `FastMCP` tools enabling AI assistants (like Claude Desktop or Cursor) to query client document statuses and metrics using natural language[cite: 14].

---

## 🏗️ Architecture & Stack

* **Language Runtime:** Python 3.12 (managed via `uv`)[cite: 10, 14]
* **Web Framework:** FastAPI (REST API) & Streamlit (UI Dashboard)[cite: 14]
* **LLM Engine & Schemas:** Groq API / OpenRouter API with `instructor` for strict Pydantic JSON schema generation[cite: 14]
* **Document Processing:** `pdfplumber` (native PDFs) & `pytesseract` / `poppler-utils` (scanned PDFs)[cite: 14]
* **Database ORM:** SQLModel (SQLite)[cite: 10, 14]
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
│   │   ├── groq_client.py          # Structured LLM extractor wrapper
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
│   │   ├── extractor_service.py     # High-level OCR + LLM parsing orchestrator
│   │   ├── gstin_validator.py        # GSTIN checksum & regex validator
│   │   ├── parser.py                # Text parsing utility helpers
│   │   ├── tally_exporter.py        # Tally XML voucher exporter
│   │   ├── verification_service.py   # Rule-based validation logic
│   │   └── zoho_exporter.py         # CSV injection-safe Zoho exporter
│   ├── config.py                    # Pydantic environment configuration (graceful CI fallbacks)
│   ├── dashboard.py                 # Streamlit CA & Client Web Portal
│   └── main.py                      # FastAPI application entrypoint
├── storage/                         # Local SQLite DB and upload storage directory
├── tests/                           # Automated test suite (26 passing tests)
│   ├── test_api_endpoints.py       # API, upload security, and RBAC tests
│   ├── test_audit_engine.py        # Audit verification rule tests
│   ├── test_auth_and_exports.py    # Exporter and auth helper tests
│   ├── test_client_portal.py       # Multi-tenant view tests
│   ├── test_reconciliation.py      # Payment reconciliation tests
│   └── test_security_hardening.py  # Security, path traversal & payload resilience tests
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
SECRET_KEY="your_custom_secure_jwt_secret_key"
PRIMARY_EXTRACTION_MODEL="llama-3.3-70b-versatile"
DATABASE_URL="sqlite:///storage/docusync.db"

```

---

## 🧪 Running Tests & Quality Gates

Run the automated test suite locally:

```bash
uv run pytest -v

```

### Test Coverage Highlights (26/26 Passing):

* **Upload Security & Magic Bytes:** Rejects disguised executable payloads by checking file byte signatures.


* **Path Traversal Shielding:** Strips relative path markers (`../`) from uploaded filenames.


* **Multi-Tenant Isolation (RBAC):** Restricts client access to authorized client IDs while allowing broad CA admin oversight.


* **Payment Reconciliation:** Verifies accuracy of amount updates and status changes (`UNPAID`, `PARTIAL`, `PAID`).


* **Export Escaping:** Prevents CSV formula injection attacks (`=`, `+`, `-`, `@`) in exported financial streams.



---

## 📖 Usage Options

### Option 1: FastAPI REST API

Start the backend server:

```bash
uv run uvicorn app.main:app --reload

```

Access Swagger API docs at **`http://127.0.0.1:8000/docs`**.

* **`POST /api/documents/upload`**: Validates magic bytes, sanitizes filename, creates `DocumentRecord`, and queues background processing.


* **`GET /api/documents/{id}`**: RBAC-protected document detail retrieval.


* **`GET /api/documents/export/zoho`**: Streams Zoho Books-compatible CSV file.


* **`GET /api/documents/export/tally`**: Streams Tally XML accounting voucher file.



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

---

## 📋 Project Roadmap

* [x] **Phase 1:** Core FastAPI setup, Pydantic schemas, and LLM extraction engine.


* [x] **Phase 2:** OCR Fallback Pipeline (Tesseract) & Auto-Classification Router.


* [x] **Phase 3:** Deterministic Rule Audit Engine (GSTIN regex & math verification).


* [x] **Phase 4:** SQLModel Database Persistence & FastMCP Server integration.


* [x] **Phase 5:** Payment Reconciliation Tracking (`payment_status`, `amount_paid`, `due_date`).


* [x] **Phase 6:** API Security Hardening (Magic Bytes, Path Traversal, CSV Escaping, Pytest & GitHub Actions CI).


* [ ] **Phase 7:** Live Vision Fallback Pipelines & Webhook Processing Notifications.
* [ ] **Phase 8:** Async Queue Workers (Celery/Redis) & Production Docker Packaging.

```

---